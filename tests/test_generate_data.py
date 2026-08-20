"""Tests for synthetic invoice and payment generation."""

from datetime import date

from generate_data import (
    DEFAULT_ANOMALIES_PER_TYPE,
    DEFAULT_COUNT,
    DEFAULT_SEED,
    generate_records,
)


def test_generation_is_repeatable_and_has_expected_anomalies():
    invoices, payments = generate_records(
        DEFAULT_COUNT,
        DEFAULT_SEED,
        DEFAULT_ANOMALIES_PER_TYPE,
    )
    repeated_invoices, repeated_payments = generate_records(
        DEFAULT_COUNT,
        DEFAULT_SEED,
        DEFAULT_ANOMALIES_PER_TYPE,
    )

    assert invoices == repeated_invoices
    assert payments == repeated_payments
    assert len(invoices) == DEFAULT_COUNT
    assert len(payments) == DEFAULT_COUNT
    assert len({row["invoice_id"] for row in invoices}) == DEFAULT_COUNT
    assert len({row["payment_id"] for row in payments}) == DEFAULT_COUNT

    invoice_by_id = {row["invoice_id"]: row for row in invoices}
    payment_invoice_ids = {row["invoice_id"] for row in payments}

    orphan_payments = [
        row for row in payments if row["invoice_id"] not in invoice_by_id
    ]
    missing_payments = [
        row for row in invoices if row["invoice_id"] not in payment_invoice_ids
    ]
    amount_mismatches = [
        row
        for row in payments
        if row["invoice_id"] in invoice_by_id
        and row["amount"] != invoice_by_id[row["invoice_id"]]["amount"]
    ]
    currency_mismatches = [
        row
        for row in payments
        if row["invoice_id"] in invoice_by_id
        and row["currency"] != invoice_by_id[row["invoice_id"]]["currency"]
    ]

    assert len(orphan_payments) == DEFAULT_ANOMALIES_PER_TYPE
    assert len(missing_payments) == DEFAULT_ANOMALIES_PER_TYPE
    assert len(amount_mismatches) == DEFAULT_ANOMALIES_PER_TYPE
    assert len(currency_mismatches) == DEFAULT_ANOMALIES_PER_TYPE


def test_generated_dates_and_amounts_have_valid_shapes():
    invoices, payments = generate_records(count=12, seed=7, anomalies_per_type=0)

    for invoice, payment in zip(invoices, payments):
        invoice_date = date.fromisoformat(invoice["invoice_date"])
        due_date = date.fromisoformat(invoice["due_date"])
        payment_date = date.fromisoformat(payment["payment_date"])

        assert due_date.toordinal() - invoice_date.toordinal() == 30
        assert invoice_date <= payment_date
        assert payment_date.toordinal() - invoice_date.toordinal() <= 45
        assert invoice["amount"].count(".") == 1
        assert len(invoice["amount"].split(".")[1]) == 2
