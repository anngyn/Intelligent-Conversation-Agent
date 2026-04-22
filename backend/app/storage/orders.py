"""Operational order and customer storage backends."""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, selectinload, sessionmaker

from app.config import settings
from app.observability import emit_metrics

logger = logging.getLogger(__name__)

_warned_backends: set[str] = set()


def normalize_full_name(full_name: str) -> str:
    """Normalize customer name for consistent identity lookup."""
    return " ".join(full_name.strip().lower().split())


def hash_pii(value: str, salt: str) -> str:
    """Hash sensitive fields before storing or querying them."""
    return hashlib.sha256(f"{value.strip()}::{salt}".encode("utf-8")).hexdigest()


def format_order_status(order: dict[str, Any]) -> str:
    """Format order information for display to the customer."""
    lines = [
        f"Order ID: {order['order_id']}",
        f"Status: {order['status']}",
        f"Items: {', '.join(order['items'])}",
    ]

    if order.get("tracking_number"):
        lines.append(f"Tracking Number: {order['tracking_number']}")

    if order.get("estimated_delivery"):
        lines.append(f"Estimated Delivery: {order['estimated_delivery']}")

    if order.get("delivery_date"):
        lines.append(f"Delivered On: {order['delivery_date']}")

    if order.get("estimated_ship_date"):
        lines.append(f"Estimated Ship Date: {order['estimated_ship_date']}")

    return "\n".join(lines)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


class Customer(Base):
    """Customer identity record used for secure order lookup."""

    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint(
            "full_name_normalized",
            "last4_ssn_hash",
            "date_of_birth_hash",
            name="uq_customers_identity",
        ),
        Index(
            "ix_customers_identity_lookup",
            "full_name_normalized",
            "last4_ssn_hash",
            "date_of_birth_hash",
        ),
    )

    customer_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name_normalized: Mapped[str] = mapped_column(String(255), nullable=False)
    last4_ssn_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    date_of_birth_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer", cascade="all, delete-orphan")


class Order(Base):
    """Operational order record."""

    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_customer_updated", "customer_id", "updated_at"),
    )

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    tracking_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    estimated_delivery: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    estimated_ship_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    customer: Mapped[Customer] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    """Order line item."""

    __tablename__ = "order_items"

    item_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.order_id"), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False, default=1)

    order: Mapped[Order] = relationship(back_populates="items")


@dataclass(slots=True)
class SQLAlchemyOrderStore:
    """PostgreSQL-oriented order store implemented with SQLAlchemy."""

    database_url: str
    pii_hash_salt: str
    engine: Any = field(init=False, repr=False)
    session_factory: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        engine_kwargs: dict[str, Any] = {"future": True}
        if self.database_url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            engine_kwargs["pool_pre_ping"] = True

        self.engine = create_engine(self.database_url, **engine_kwargs)
        self.session_factory = sessionmaker(self.engine, future=True, expire_on_commit=False)

    def initialize_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def lookup_order(self, full_name: str, last4_ssn: str, date_of_birth: str) -> dict[str, Any] | None:
        start_time = time.perf_counter()
        full_name_normalized = normalize_full_name(full_name)
        ssn_hash = hash_pii(last4_ssn, self.pii_hash_salt)
        dob_hash = hash_pii(date_of_birth, self.pii_hash_salt)

        with self.session_factory() as session:
            stmt = (
                select(Order)
                .join(Customer)
                .options(selectinload(Order.items))
                .where(Customer.full_name_normalized == full_name_normalized)
                .where(Customer.last4_ssn_hash == ssn_hash)
                .where(Customer.date_of_birth_hash == dob_hash)
                .order_by(Order.updated_at.desc())
            )
            order = session.execute(stmt).scalars().first()
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            emit_metrics(
                metrics=[
                    {"Name": "OrderStoreLatency", "Unit": "Milliseconds", "Value": latency_ms},
                    {"Name": "OrderStoreLookup", "Unit": "Count", "Value": 1},
                ],
                dimensions={"Backend": "postgres"},
                properties={"result": "hit" if order is not None else "miss"},
            )
            if order is None:
                return None
            return self._serialize_order(order)

    def seed_from_json(self, source_path: str | Path) -> int:
        source = Path(source_path)
        with source.open(encoding="utf-8") as file:
            records = json.load(file)

        with self.session_factory() as session:
            for record in records:
                customer = self._upsert_customer(session, record)
                self._upsert_order(session, customer.customer_id, record)
            session.commit()

        return len(records)

    def _upsert_customer(self, session, record: dict[str, Any]) -> Customer:
        full_name_normalized = normalize_full_name(record["full_name"])
        ssn_hash = hash_pii(record["last4_ssn"], self.pii_hash_salt)
        dob_hash = hash_pii(record["date_of_birth"], self.pii_hash_salt)

        stmt = (
            select(Customer)
            .where(Customer.full_name_normalized == full_name_normalized)
            .where(Customer.last4_ssn_hash == ssn_hash)
            .where(Customer.date_of_birth_hash == dob_hash)
        )
        customer = session.execute(stmt).scalars().first()
        if customer is not None:
            return customer

        customer = Customer(
            customer_id=str(uuid.uuid4()),
            full_name=record["full_name"],
            full_name_normalized=full_name_normalized,
            last4_ssn_hash=ssn_hash,
            date_of_birth_hash=dob_hash,
        )
        session.add(customer)
        session.flush()
        return customer

    def _upsert_order(self, session, customer_id: str, record: dict[str, Any]) -> None:
        order = session.get(Order, record["order_id"])
        if order is None:
            order = Order(order_id=record["order_id"], customer_id=customer_id)
            session.add(order)

        order.customer_id = customer_id
        order.status = record["status"]
        order.tracking_number = record.get("tracking_number")
        order.estimated_delivery = _parse_optional_date(record.get("estimated_delivery"))
        order.delivery_date = _parse_optional_date(record.get("delivery_date"))
        order.estimated_ship_date = _parse_optional_date(record.get("estimated_ship_date"))
        order.updated_at = datetime.utcnow()

        for existing_item in list(order.items):
            session.delete(existing_item)

        for product_name in record.get("items", []):
            order.items.append(
                OrderItem(
                    item_id=str(uuid.uuid4()),
                    product_name=product_name,
                    quantity=1,
                )
            )

    @staticmethod
    def _serialize_order(order: Order) -> dict[str, Any]:
        return {
            "order_id": order.order_id,
            "status": order.status,
            "tracking_number": order.tracking_number,
            "estimated_delivery": _date_to_iso(order.estimated_delivery),
            "delivery_date": _date_to_iso(order.delivery_date),
            "estimated_ship_date": _date_to_iso(order.estimated_ship_date),
            "items": [item.product_name for item in order.items],
        }


class MockOrderStore:
    """JSON-backed fallback used when PostgreSQL is not configured."""

    def __init__(self, source_path: str | Path) -> None:
        self.source_path = Path(source_path)
        self.orders = self._load_orders()

    def lookup_order(self, full_name: str, last4_ssn: str, date_of_birth: str) -> dict[str, Any] | None:
        start_time = time.perf_counter()
        key = (
            normalize_full_name(full_name),
            last4_ssn.strip(),
            date_of_birth.strip(),
        )
        order = self.orders.get(key)
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        emit_metrics(
            metrics=[
                {"Name": "OrderStoreLatency", "Unit": "Milliseconds", "Value": latency_ms},
                {"Name": "OrderStoreLookup", "Unit": "Count", "Value": 1},
            ],
            dimensions={"Backend": "mock"},
            properties={"result": "hit" if order is not None else "miss"},
        )
        return order

    def _load_orders(self) -> dict[tuple[str, str, str], dict[str, Any]]:
        with self.source_path.open(encoding="utf-8") as file:
            records = json.load(file)

        indexed: dict[tuple[str, str, str], dict[str, Any]] = {}
        for record in records:
            indexed[
                (
                    normalize_full_name(record["full_name"]),
                    record["last4_ssn"],
                    record["date_of_birth"],
                )
            ] = record
        return indexed


def initialize_order_store() -> None:
    """Initialize the configured order store on application startup."""
    store = get_order_store()
    if isinstance(store, SQLAlchemyOrderStore):
        store.initialize_schema()
        logger.info("order_store_initialized", extra={"backend": "postgres"})
        if settings.order_seed_on_startup:
            seeded = store.seed_from_json(settings.order_seed_file_path)
            logger.info(
                "order_store_seeded",
                extra={"backend": "postgres", "records": seeded},
            )


def seed_order_store(source_path: str | Path | None = None) -> int:
    """Seed the configured SQL order store from the dataset file."""
    store = get_order_store()
    if not isinstance(store, SQLAlchemyOrderStore):
        return 0

    seed_path = source_path or settings.order_seed_file_path
    return store.seed_from_json(seed_path)


def lookup_order(full_name: str, last4_ssn: str, date_of_birth: str) -> dict[str, Any] | None:
    """Lookup an order from the active storage backend."""
    return get_order_store().lookup_order(full_name, last4_ssn, date_of_birth)


def get_order_store() -> SQLAlchemyOrderStore | MockOrderStore:
    """Return PostgreSQL store when configured, otherwise JSON fallback."""
    backend = settings.order_storage_backend.lower()
    if backend == "postgres":
        database_url = settings.order_database_url.strip()
        if database_url:
            return _get_sqlalchemy_order_store(database_url, settings.pii_hash_salt)

        _warn_once(
            "orders:postgres",
            "PostgreSQL order backend selected but order_database_url is empty; using JSON fallback.",
        )

    return _get_mock_order_store(settings.order_seed_file_path)


@lru_cache(maxsize=4)
def _get_sqlalchemy_order_store(database_url: str, pii_hash_salt: str) -> SQLAlchemyOrderStore:
    return SQLAlchemyOrderStore(database_url=database_url, pii_hash_salt=pii_hash_salt)


@lru_cache(maxsize=1)
def _get_mock_order_store(source_path: str) -> MockOrderStore:
    return MockOrderStore(source_path)


def _parse_optional_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _date_to_iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _warn_once(key: str, message: str) -> None:
    if key in _warned_backends:
        return
    logger.warning(message)
    _warned_backends.add(key)
