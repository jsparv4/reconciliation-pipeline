"""Create the reconciliation view and print a summary report."""

import argparse
import os
from pathlib import Path
from typing import LiteralString, cast

import psycopg


PROJECT_DIR = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL connection URL (defaults to DATABASE_URL)",
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

    print("Reconciliation summary")
    print("status               rows   invoice total   payment total      difference")
    for status, count, invoice_total, payment_total, difference in results:
        print(
            f"{status:<19} {count:>5}  {invoice_total:>14.2f}  "
            f"{payment_total:>14.2f}  {difference:>14.2f}"
        )


if __name__ == "__main__":
    main()
