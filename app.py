"""Streamlit interface for the PostgreSQL reconciliation pipeline."""

from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

import psycopg
import streamlit as st

from database import database_connection_parameters
from ingest_postgres import LoadVerification, ingest_files
from reconcile import (
    create_reconciliation_view,
    fetch_reconciliation_results,
    reconciliation_rows_to_csv,
)


STATUS_LABELS = {
    "matched": "Matched",
    "amount_mismatch": "Amount mismatches",
    "currency_mismatch": "Currency mismatches",
    "missing_payment": "Missing payments",
    "missing_invoice": "Missing invoices / orphan payments",
}


def run_pipeline(
    invoices_csv: bytes,
    payments_csv: bytes,
) -> tuple[LoadVerification, list[dict[str, object]]]:
    """Run the existing database pipeline for two uploaded CSV files."""
    with TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        invoices_path = directory / "invoices.csv"
        payments_path = directory / "payments.csv"
        invoices_path.write_bytes(invoices_csv)
        payments_path.write_bytes(payments_csv)

        with psycopg.connect(**database_connection_parameters()) as connection:
            verification = ingest_files(connection, invoices_path, payments_path)
            create_reconciliation_view(connection)
            results = fetch_reconciliation_results(connection)

    return verification, results


def display_metrics(results: list[dict[str, object]]) -> None:
    counts = Counter(str(row["reconciliation_status"]) for row in results)
    metrics = [
        ("Matched", counts["matched"]),
        ("Amount mismatches", counts["amount_mismatch"]),
        ("Currency mismatches", counts["currency_mismatch"]),
        ("Missing payments", counts["missing_payment"]),
        ("Missing invoices / orphan payments", counts["missing_invoice"]),
    ]
    columns = st.columns(5)
    for column, (label, value) in zip(columns, metrics):
        column.metric(label, value)


def display_control_totals(verification: LoadVerification) -> None:
    datasets = (
        ("Invoices", verification.invoices),
        ("Payments", verification.payments),
    )
    rows = [
        {
            "Dataset": name,
            "Source rows": totals.source_rows,
            "Database rows": totals.database_rows,
            "Row count valid": totals.source_rows == totals.database_rows,
            "Source amount": f"{totals.source_amount:.2f}",
            "Database amount": f"{totals.database_amount:.2f}",
            "Amount valid": totals.source_amount == totals.database_amount,
        }
        for name, totals in datasets
    ]

    st.subheader("Source and database control totals")
    st.dataframe(rows, use_container_width=True, hide_index=True)
    if all(row["Row count valid"] and row["Amount valid"] for row in rows):
        st.success("Source and database row counts and amount totals agree.")
    else:
        st.warning("One or more source and database control totals do not agree.")


def display_results(
    verification: LoadVerification,
    results: list[dict[str, object]],
) -> None:
    st.success("Reconciliation completed successfully.")

    invoice_column, payment_column = st.columns(2)
    invoice_column.metric("Invoice count", verification.invoices.database_rows)
    payment_column.metric("Payment count", verification.payments.database_rows)
    display_metrics(results)
    display_control_totals(verification)

    st.subheader("Reconciliation results")
    st.dataframe(results, use_container_width=True, hide_index=True)

    counts = Counter(str(row["reconciliation_status"]) for row in results)
    chart_rows = [
        {"Status": STATUS_LABELS[status], "Count": counts[status]}
        for status in STATUS_LABELS
    ]
    st.subheader("Status counts")
    st.bar_chart(chart_rows, x="Status", y="Count")

    exceptions = [
        row for row in results if row["reconciliation_status"] != "matched"
    ]
    st.subheader("Exceptions")
    if exceptions:
        st.dataframe(exceptions, use_container_width=True, hide_index=True)
    else:
        st.info("No reconciliation exceptions were found.")

    st.download_button(
        "Download exceptions as CSV",
        data=reconciliation_rows_to_csv(exceptions),
        file_name="reconciliation_exceptions.csv",
        mime="text/csv",
        disabled=not exceptions,
    )


def main() -> None:
    st.set_page_config(
        page_title="Financial Reconciliation Pipeline",
        page_icon="💳",
        layout="wide",
    )
    st.title("Financial Reconciliation Pipeline")
    st.write(
        "Upload invoice and payment CSV files to load them into PostgreSQL, "
        "apply the SQL reconciliation rules, and review any exceptions."
    )

    invoices_upload = st.file_uploader("Invoices CSV", type="csv")
    payments_upload = st.file_uploader("Payments CSV", type="csv")

    if st.button("Run Reconciliation", type="primary"):
        if invoices_upload is None or payments_upload is None:
            missing = []
            if invoices_upload is None:
                missing.append("invoices CSV")
            if payments_upload is None:
                missing.append("payments CSV")
            st.error(f"Please upload the {' and '.join(missing)} before running.")
            st.session_state.pop("reconciliation_run", None)
        else:
            try:
                with st.spinner("Loading data and running reconciliation..."):
                    st.session_state["reconciliation_run"] = run_pipeline(
                        invoices_upload.getvalue(),
                        payments_upload.getvalue(),
                    )
            except psycopg.OperationalError:
                st.error(
                    "PostgreSQL is unavailable. Start it with "
                    "'docker compose up -d --wait' and check your .env settings."
                )
                st.session_state.pop("reconciliation_run", None)
            except (OSError, ValueError, RuntimeError, psycopg.Error) as error:
                st.error("The reconciliation pipeline could not complete.")
                st.caption(f"Details: {error}")
                st.session_state.pop("reconciliation_run", None)

    if "reconciliation_run" in st.session_state:
        verification, results = st.session_state["reconciliation_run"]
        display_results(verification, results)


if __name__ == "__main__":
    main()
