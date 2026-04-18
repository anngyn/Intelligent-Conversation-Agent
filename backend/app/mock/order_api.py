"""Mock order status API for demonstration purposes."""

import json
from pathlib import Path
from typing import Optional


def load_mock_orders() -> dict[tuple[str, str, str], dict]:
    """Load mock orders from JSON and index by verification tuple."""
    orders_file = Path(__file__).parents[3] / "dataset" / "mock" / "orders.json"

    with open(orders_file) as f:
        orders_list = json.load(f)

    orders_dict = {}
    for order in orders_list:
        key = (
            order["full_name"].lower().strip(),
            order["last4_ssn"],
            order["date_of_birth"],
        )
        orders_dict[key] = order

    return orders_dict


MOCK_ORDERS = load_mock_orders()


def lookup_order(
    full_name: str,
    last4_ssn: str,
    date_of_birth: str,
) -> Optional[dict]:
    """
    Look up an order by customer verification information.

    Args:
        full_name: Customer's full name
        last4_ssn: Last 4 digits of SSN
        date_of_birth: Date of birth in YYYY-MM-DD format

    Returns:
        Order information dict if found, None otherwise
    """
    key = (full_name.lower().strip(), last4_ssn, date_of_birth)
    return MOCK_ORDERS.get(key)


def format_order_status(order: dict) -> str:
    """Format order information for display to user."""
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
