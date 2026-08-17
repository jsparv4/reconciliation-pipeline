"""Load the generated invoice and payment CSV files into PostgreSQL."""

import argparse
import csv
import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import LiteralString, TypeAlias, cast

import psycopg


PROJECT_DIR = Path(__file__).resolve().parent
INVOICE_FIELDS = (
    "invoice_id",
    "customer_id",
    "invoice_date",
    "due_date",
    "amount",
    "currency",
)
PAYMENT_FIELDS = (
    "payment_id",
    "invoice_id",
    "payment_date",
    "amount",
    "currency",
    "payment_method",
)
InvoiceRow: TypeAlias = tuple[str, str, date, date, Decimal, str]
PaymentRow: TypeAlias = tuple[str, str, date, Decimal, str, str]


def read_invoices(path: Path) -> tuple[list[InvoiceRow], Decimal]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if tuple(reader.fieldnames or ()) != INVOICE_FIELDS:
            raise ValueError(f"Unexpected columns in {path}: {reader.fieldnames}")

        rows = [
            (
                row["invoice_id"],
                row["customer_id"],
                date.fromisoformat(row["invoice_date"]),
                date.fromisoformat(row["due_date"]),
                Decimal(row["amount"]),
                row["currency"],
            )
            for row in reader
        ]

    return rows, sum((row[4] for row in rows), start=Decimal("0"))


def read_payments(path: Path) -> tuple[list[PaymentRow], Decimal]:
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if tuple(reader.fieldnames or ()) != PAYMENT_FIELDS:
            raise ValueError(f"Unexpected columns in {path}: {reader.fieldnames}")

        rows = [
            (
                row["payment_id"],
                row["invoice_id"],
                date.fromisoformat(row["payment_date"]),
                Decimal(row["amount"]),
                row["currency"],
                row["payment_method"],
            )
            for row in reader
        ]

    return rows, sum((row[3] for row in rows), start=Decimal("0"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL connection URL (defaults to DATABASE_URL)",
    )
    parser.add_argument(
        "--invoices",
        type=Path,
        default=PROJECT_DIR / "data" / "invoices.csv",
        help="path to invoices.csv",
    )
    parser.add_argument(
        "--payments",
        type=Path,
        default=PROJECT_DIR / "data" / "payments.csv",
        help="path to payments.csv",
    )
    args = parser.parse_args()

    if not args.database_url:
        parser.error("set DATABASE_URL or pass --database-url")

    invoices, source_invoice_total = read_invoices(args.invoices)
    payments, source_payment_total = read_payments(args.payments)
    schema_sql = (PROJECT_DIR / "schema.sql").read_text(encoding="utf-8")

    with psycopg.connect(args.database_url) as connection:
        with connection.cursor() as cursor:
            # schema.sql is a trusted project file, not user-provided SQL.
            cursor.execute(cast(LiteralString, schema_sql))
            cursor.execute("TRUNCATE TABLE raw_payments, raw_invoices")

            cursor.executemany(
                """
                INSERT INTO raw_invoices
                    (invoice_id, customer_id, invoice_date, due_date, amount, currency)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                invoices,
            )
            cursor.executemany(
                """
                INSERT INTO raw_payments
                    (payment_id, invoice_id, payment_date, amount, currency, payment_method)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                payments,
            )

            cursor.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM raw_invoices")
            invoice_result = cursor.fetchone()
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM raw_payments")
            payment_result = cursor.fetchone()

            if invoice_result is None or payment_result is None:
                raise RuntimeError("Database verification queries returned no result")

            database_invoice_count, database_invoice_total = invoice_result
            database_payment_count, database_payment_total = payment_result

    print("Load verification")
    print("dataset   source rows  database rows  source total  database total")
    print(
        f"invoices  {len(invoices):>11}  {database_invoice_count:>13}  "
        f"{source_invoice_total:>12.2f}  {database_invoice_total:>14.2f}"
    )
    print(
        f"payments  {len(payments):>11}  {database_payment_count:>13}  "
        f"{source_payment_total:>12.2f}  {database_payment_total:>14.2f}"
    )


if __name__ == "__main__":
    main()
