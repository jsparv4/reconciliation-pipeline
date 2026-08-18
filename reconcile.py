"""Create the reconciliation view and print a summary report."""

import argparse
import csv
import os
from pathlib import Path
from typing import LiteralString, cast

import psycopg


PROJECT_DIR = Path(__file__).resolve().parent
EXCEPTION_FIELDS = (
    "reconciliation_status",
    "invoice_id",
    "payment_id",
    "customer_id",
    "invoice_date",
    "due_date",
    "payment_date",
    "invoice_amount",
    "payment_amount",
    "invoice_currency",
    "payment_currency",
    "payment_method",
    "amount_difference",
)


def write_exceptions(path: Path, rows: list[tuple[object, ...]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(EXCEPTION_FIELDS)
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL connection URL (defaults to DATABASE_URL)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional path for a CSV containing non-matching records",
    )
    args = parser.parse_args()

    if not args.database_url:
        parser.error("set DATABASE_URL or pass --database-url")

    reconciliation_sql = (PROJECT_DIR / "reconciliation.sql").read_text(encoding="utf-8")

    with psycopg.connect(args.database_url) as connection:
        with connection.cursor() as cursor:
            # reconciliation.sql is a trusted project file, not user-provided SQL.
            cursor.execute(cast(LiteralString, reconciliation_sql))
            cursor.execute(
                """
                SELECT
                    reconciliation_status,
                    COUNT(*),
                    COALESCE(SUM(invoice_amount), 0),
                    COALESCE(SUM(payment_amount), 0),
                    COALESCE(SUM(payment_amount), 0)
                        - COALESCE(SUM(invoice_amount), 0) AS difference
                FROM reconciliation_results
                GROUP BY reconciliation_status
                ORDER BY CASE reconciliation_status
                    WHEN 'matched' THEN 1
                    WHEN 'missing_payment' THEN 2
                    WHEN 'missing_invoice' THEN 3
                    WHEN 'amount_mismatch' THEN 4
                    WHEN 'currency_mismatch' THEN 5
                END
                """
            )
            results = cursor.fetchall()

            exception_rows: list[tuple[object, ...]] = []
            if args.output:
                cursor.execute(
                    """
                    SELECT
                        reconciliation_status,
                        invoice_id,
                        payment_id,
                        customer_id,
                        invoice_date,
                        due_date,
                        payment_date,
                        invoice_amount,
                        payment_amount,
                        invoice_currency,
                        payment_currency,
                        payment_method,
                        COALESCE(payment_amount, 0)
                            - COALESCE(invoice_amount, 0) AS amount_difference
                    FROM reconciliation_results
                    WHERE reconciliation_status <> 'matched'
                    ORDER BY
                        CASE reconciliation_status
                            WHEN 'missing_payment' THEN 1
                            WHEN 'missing_invoice' THEN 2
                            WHEN 'amount_mismatch' THEN 3
                            WHEN 'currency_mismatch' THEN 4
                        END,
                        invoice_id,
                        payment_id
                    """
                )
                exception_rows = cursor.fetchall()

    print("Reconciliation summary")
    print("status               rows   invoice total   payment total      difference")
    for status, count, invoice_total, payment_total, difference in results:
        print(
            f"{status:<19} {count:>5}  {invoice_total:>14.2f}  "
            f"{payment_total:>14.2f}  {difference:>14.2f}"
        )

    if args.output:
        write_exceptions(args.output, exception_rows)
        print(f"\nExported {len(exception_rows)} exceptions to {args.output}")


if __name__ == "__main__":
    main()
