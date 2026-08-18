"""Generate synthetic invoice and payment CSV files."""

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path


DEFAULT_COUNT = 1_000
DEFAULT_SEED = 42
DEFAULT_ANOMALIES_PER_TYPE = 10


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def generate_records(
    count: int,
    seed: int,
    anomalies_per_type: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rng = random.Random(seed)
    start_date = date(2025, 1, 1)
    payment_methods = ("bank_transfer", "card", "check")

    invoices: list[dict[str, str]] = []
    payments: list[dict[str, str]] = []

    for number in range(1, count + 1):
        invoice_id = f"INV-{number:06d}"
        invoice_date = start_date + timedelta(days=rng.randint(0, 364))
        due_date = invoice_date + timedelta(days=30)
        amount_cents = rng.randint(1_000, 500_000)
        amount = f"{amount_cents / 100:.2f}"

        invoices.append(
            {
                "invoice_id": invoice_id,
                "customer_id": f"CUST-{rng.randint(1, 100):04d}",
                "invoice_date": invoice_date.isoformat(),
                "due_date": due_date.isoformat(),
                "amount": amount,
                "currency": "USD",
            }
        )

        payment_invoice_id = invoice_id
        payment_amount = amount
        payment_currency = "USD"

        if number <= anomalies_per_type:
            payment_invoice_id = f"INV-ORPHAN-{number:06d}"
        elif number <= anomalies_per_type * 2:
            payment_amount = f"{(amount_cents // 2) / 100:.2f}"
        elif number <= anomalies_per_type * 3:
            payment_currency = "EUR"

        payments.append(
            {
                "payment_id": f"PAY-{number:06d}",
                "invoice_id": payment_invoice_id,
                "payment_date": (invoice_date + timedelta(days=rng.randint(0, 45))).isoformat(),
                "amount": payment_amount,
                "currency": payment_currency,
                "payment_method": rng.choice(payment_methods),
            }
        )

    return invoices, payments


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help="rows per file (default: 1000)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="random seed (default: 42)")
    parser.add_argument(
        "--anomalies-per-type",
        type=int,
        default=DEFAULT_ANOMALIES_PER_TYPE,
        help="missing, amount, and currency anomalies to generate (default: 10 each)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data"),
        help="directory for generated CSV files (default: data)",
    )
    args = parser.parse_args()

    if args.count < 1:
        parser.error("--count must be at least 1")
    if args.anomalies_per_type < 0:
        parser.error("--anomalies-per-type cannot be negative")
    if args.anomalies_per_type * 3 > args.count:
        parser.error("--count must be at least three times --anomalies-per-type")

    invoices, payments = generate_records(args.count, args.seed, args.anomalies_per_type)
    write_csv(args.output_dir / "invoices.csv", list(invoices[0]), invoices)
    write_csv(args.output_dir / "payments.csv", list(payments[0]), payments)

    print(f"Generated {args.count} invoices and {args.count} payments in {args.output_dir}")


if __name__ == "__main__":
    main()
