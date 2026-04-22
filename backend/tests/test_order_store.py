"""Tests for the SQL-backed order store."""

from pathlib import Path

from app.storage.orders import SQLAlchemyOrderStore


def test_sql_order_store_seed_and_lookup(tmp_path):
    """Seed a SQL store and retrieve an order using verified identity fields."""
    database_path = tmp_path / "orders.db"
    store = SQLAlchemyOrderStore(
        database_url=f"sqlite:///{database_path}",
        pii_hash_salt="unit-test-salt",
    )
    store.initialize_schema()

    source_path = Path("dataset/mock/orders.json")
    seeded = store.seed_from_json(source_path)
    assert seeded == 4

    order = store.lookup_order("John Smith", "1234", "1990-01-15")
    assert order is not None
    assert order["order_id"] == "ORD-98765"
    assert order["status"] == "Shipped"
    assert "Laptop Stand" in order["items"]


def test_sql_order_store_lookup_is_case_insensitive_for_name(tmp_path):
    """Name normalization should preserve case-insensitive identity lookup."""
    database_path = tmp_path / "orders.db"
    store = SQLAlchemyOrderStore(
        database_url=f"sqlite:///{database_path}",
        pii_hash_salt="unit-test-salt",
    )
    store.initialize_schema()
    store.seed_from_json(Path("dataset/mock/orders.json"))

    order = store.lookup_order("john smith", "1234", "1990-01-15")
    assert order is not None
    assert order["order_id"] == "ORD-98765"
