"""Tests for mock order API."""

from app.mock.order_api import lookup_order


def test_lookup_existing_order():
    """Test successful order lookup."""
    order = lookup_order("John Smith", "1234", "1990-01-15")
    assert order is not None
    assert order["order_id"] == "ORD-98765"
    assert order["status"] == "Shipped"


def test_lookup_case_insensitive():
    """Test that name matching is case-insensitive."""
    order1 = lookup_order("John Smith", "1234", "1990-01-15")
    order2 = lookup_order("JOHN SMITH", "1234", "1990-01-15")
    order3 = lookup_order("john smith", "1234", "1990-01-15")

    assert order1 == order2 == order3


def test_lookup_nonexistent_order():
    """Test lookup with invalid credentials."""
    order = lookup_order("Invalid Name", "0000", "2000-01-01")
    assert order is None


def test_lookup_wrong_ssn():
    """Test lookup with correct name but wrong SSN."""
    order = lookup_order("John Smith", "9999", "1990-01-15")
    assert order is None
