"""Tests for the SQL reconciliation business rules."""

from collections import Counter

from generate_data import (
    DEFAULT_ANOMALIES_PER_TYPE,
    DEFAULT_COUNT,
    DEFAULT_SEED,
    generate_records,
    write_csv,
)
from ingest_postgres import INVOICE_FIELDS, PAYMENT_FIELDS, ingest_files
from reconcile import (
    create_reconciliation_view,
    fetch_reconciliation_results,
    reconciliation_rows_to_csv,
)


def write_dataset(directory, invoices, payments):
    invoices_path = directory / "invoices.csv"
    payments_path = directory / "payments.csv"
    write_csv(invoices_path, list(INVOICE_FIELDS), invoices)
    write_csv(payments_path, list(PAYMENT_FIELDS), payments)
    return invoices_path, payments_path


def reconciliation_statuses(connection):
    return {
        row["invoice_id"]: row["reconciliation_status"]
        for row in fetch_reconciliation_results(connection)
    }


def test_default_dataset_has_expected_reconciliation_counts(
    tmp_path,
    database_connection,
):
    invoices, payments = generate_records(
        DEFAULT_COUNT,
        DEFAULT_SEED,
        DEFAULT_ANOMALIES_PER_TYPE,
    )
    invoices_path, payments_path = write_dataset(tmp_path, invoices, payments)
    ingest_files(database_connection, invoices_path, payments_path)
    create_reconciliation_view(database_connection)

    counts = Counter(reconciliation_statuses(database_connection).values())

    assert counts == {
        "matched": 970,
        "missing_payment": 10,
        "missing_invoice": 10,
        "amount_mismatch": 10,
        "currency_mismatch": 10,
    }


def test_each_reconciliation_business_rule(tmp_path, database_connection):
    invoices = [
        invoice("INV-MATCH", "100.00"),
        invoice("INV-UNDERPAID", "100.00"),
        invoice("INV-OVERPAID", "100.00"),
        invoice("INV-NO-PAYMENT", "100.00"),
        invoice("INV-CURRENCY", "100.00", currency="USD"),
    ]
    payments = [
        payment("PAY-MATCH", "INV-MATCH", "100.00"),
        payment("PAY-UNDERPAID", "INV-UNDERPAID", "90.00"),
        payment("PAY-OVERPAID", "INV-OVERPAID", "110.00"),
        payment("PAY-CURRENCY", "INV-CURRENCY", "100.00", currency="EUR"),
        payment("PAY-ORPHAN", "INV-ORPHAN", "75.00"),
    ]
    invoices_path, payments_path = write_dataset(tmp_path, invoices, payments)
    ingest_files(database_connection, invoices_path, payments_path)
    create_reconciliation_view(database_connection)

    assert reconciliation_statuses(database_connection) == {
        "INV-MATCH": "matched",
        "INV-UNDERPAID": "amount_mismatch",
        "INV-OVERPAID": "amount_mismatch",
        "INV-NO-PAYMENT": "missing_payment",
        "INV-CURRENCY": "currency_mismatch",
        "INV-ORPHAN": "missing_invoice",
    }


def test_reconciliation_results_can_be_exported_as_csv(
    tmp_path,
    database_connection,
):
    invoices = [invoice("INV-MATCH", "100.00")]
    payments = [payment("PAY-MATCH", "INV-MATCH", "100.00")]
    invoices_path, payments_path = write_dataset(tmp_path, invoices, payments)
    ingest_files(database_connection, invoices_path, payments_path)
    create_reconciliation_view(database_connection)

    csv_text = reconciliation_rows_to_csv(
        fetch_reconciliation_results(database_connection)
    )

    assert csv_text.startswith("reconciliation_status,invoice_id,payment_id")
    assert "matched,INV-MATCH,PAY-MATCH" in csv_text


def invoice(invoice_id, amount, currency="USD"):
    return {
        "invoice_id": invoice_id,
        "customer_id": "CUST-0001",
        "invoice_date": "2025-01-01",
        "due_date": "2025-01-31",
        "amount": amount,
        "currency": currency,
    }


def payment(payment_id, invoice_id, amount, currency="USD"):
    return {
        "payment_id": payment_id,
        "invoice_id": invoice_id,
        "payment_date": "2025-01-15",
        "amount": amount,
        "currency": currency,
        "payment_method": "bank_transfer",
    }
