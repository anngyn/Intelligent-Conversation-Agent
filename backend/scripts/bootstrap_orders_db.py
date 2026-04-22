"""Bootstrap the PostgreSQL order store from the bundled mock dataset."""

from app.storage.orders import seed_order_store


def main() -> None:
    seeded = seed_order_store()
    print(f"Seeded {seeded} order records")


if __name__ == "__main__":
    main()
