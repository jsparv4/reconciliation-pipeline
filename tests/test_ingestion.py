"""Tests for CSV validation and PostgreSQL ingestion controls."""

from decimal import Decimal

import pytest

from generate_data import generate_records, write_csv
from ingest_postgres import (
    INVOICE_FIELDS,
    PAYMENT_FIELDS,
    ingest_files,
    read_invoices,
    read_payments,
)


def write_dataset(directory, invoices, payments):
    invoices_path = directory / "invoices.csv"
    payments_path = directory / "payments.csv"
    write_csv(invoices_path, list(INVOICE_FIELDS), invoices)
    write_csv(payments_path, list(PAYMENT_FIELDS), payments)
    return invoices_path, payments_path


def test_ingestion_control_totals_and_rerun_are_idempotent(
    tmp_path,
    database_connection,
):
    invoices, payments = generate_records(count=8, seed=17, anomalies_per_type=0)
    invoices_path, payments_path = write_dataset(tmp_path, invoices, payments)

    first_load = ingest_files(database_connection, invoices_path, payments_path)
    second_load = ingest_files(database_connection, invoices_path, payments_path)

    expected_invoice_total = sum(
        (Decimal(row["amount"]) for row in invoices),
        start=Decimal("0"),
    )
    expected_payment_total = sum(
        (Decimal(row["amount"]) for row in payments),
        start=Decimal("0"),
    )

    assert first_load.invoices.source_rows == 8
    assert first_load.invoices.database_rows == 8
    assert first_load.invoices.source_amount == expected_invoice_total
    assert first_load.invoices.database_amount == expected_invoice_total
    assert first_load.payments.source_rows == 8
    assert first_load.payments.database_rows == 8
    assert first_load.payments.source_amount == expected_payment_total
    assert first_load.payments.database_amount == expected_payment_total

    assert second_load == first_load
    with database_connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM raw_invoices")
        assert cursor.fetchone() == (8,)
        cursor.execute("SELECT COUNT(*) FROM raw_payments")
        assert cursor.fetchone() == (8,)


def test_missing_input_file_has_a_clear_error(tmp_path):
    missing_path = tmp_path / "missing-invoices.csv"

    with pytest.raises(FileNotFoundError) as error:
        read_invoices(missing_path)

    assert "missing-invoices.csv" in str(error.value)


def test_invalid_csv_columns_have_a_clear_error(tmp_path):
    invalid_path = tmp_path / "invalid-payments.csv"
    invalid_path.write_text("payment_id,wrong_column\nPAY-1,value\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unexpected columns"):
        read_payments(invalid_path)
