"""Create the reconciliation view and print a summary report."""

import argparse
import csv
import io
from pathlib import Path
from typing import LiteralString, Mapping, Sequence, cast

import psycopg
from psycopg.rows import dict_row

from database import database_connection_parameters


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


def create_reconciliation_view(connection: psycopg.Connection) -> None:
    """Create or replace the reconciliation view using the project SQL."""
    reconciliation_sql = (PROJECT_DIR / "reconciliation.sql").read_text(encoding="utf-8")
    with connection.cursor() as cursor:
        # reconciliation.sql is a trusted project file, not user-provided SQL.
        cursor.execute(cast(LiteralString, reconciliation_sql))


def fetch_reconciliation_results(
    connection: psycopg.Connection,
) -> list[dict[str, object]]:
    """Return every database-classified reconciliation row."""
    with connection.cursor(row_factory=dict_row) as cursor:
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
            ORDER BY
                CASE reconciliation_status
                    WHEN 'matched' THEN 1
                    WHEN 'missing_payment' THEN 2
                    WHEN 'missing_invoice' THEN 3
                    WHEN 'amount_mismatch' THEN 4
                    WHEN 'currency_mismatch' THEN 5
                END,
                invoice_id,
                payment_id
            """
        )
        return cursor.fetchall()


def reconciliation_rows_to_csv(rows: Sequence[Mapping[str, object]]) -> str:
    """Serialize reconciliation rows using the standard exception columns."""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=EXCEPTION_FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="optional path for a CSV containing non-matching records",
    )
    args = parser.parse_args()

    with psycopg.connect(**database_connection_parameters()) as connection:
        create_reconciliation_view(connection)
        with connection.cursor() as cursor:
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
                reconciliation_rows = fetch_reconciliation_results(connection)
                exception_rows = [
                    tuple(row[field] for field in EXCEPTION_FIELDS)
                    for row in reconciliation_rows
                    if row["reconciliation_status"] != "matched"
                ]

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
