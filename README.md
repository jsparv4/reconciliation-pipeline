# Reconciliation Pipeline

This repository contains a simple Python pipeline that generates synthetic invoice and payment data, loads it into PostgreSQL, and reports reconciliation results.

## Start the pipeline

The prerequisites are Python 3.10 or newer and Docker with Docker Compose. From the repository root, create a local environment file from the checked-in example.

PowerShell:

```powershell
Copy-Item .env.example .env
```

Bash:

```bash
cp .env.example .env
```

Edit `.env` and replace `change-me` with a local database password. Then install the Python dependencies and start PostgreSQL:

```bash
python -m pip install -r requirements.txt
docker compose up -d --wait
```

Generate the source files, load them, and run the reconciliation report:

```bash
python generate_data.py
python ingest_postgres.py
python reconcile.py --output data/reconciliation_exceptions.csv
```

Compose reads `.env` when it creates PostgreSQL, and the Python scripts read the same file when connecting. Existing process environment variables take precedence over values in `.env`. The required settings are:

| Variable | Purpose | Example |
| --- | --- | --- |
| `POSTGRES_DB` | Database name | `reconciliation` |
| `POSTGRES_USER` | Database user | `reconciliation` |
| `POSTGRES_PASSWORD` | Database password | `change-me` |
| `POSTGRES_HOST` | Host used by the Python scripts | `localhost` |
| `POSTGRES_PORT` | Host port published by Compose | `5432` |

To stop PostgreSQL while retaining its data, run `docker compose down`. To also delete the database volume and start fresh next time, run `docker compose down --volumes`.

## Generate the data

Run the script from the repository root:

```bash
python generate_data.py
```

This creates `data/invoices.csv` and `data/payments.csv`, each with 1,000 rows. The default random seed is fixed, so repeated runs produce the same data. You can optionally change the row count, seed, anomaly count, or output directory:

```bash
python generate_data.py --count 1000 --seed 42 --anomalies-per-type 10 --output-dir data
```

By default, the files contain 10 examples of each reconciliation anomaly:

- Missing payment: an invoice has no payment with the same `invoice_id`.
- Missing invoice: a payment references an `INV-ORPHAN-*` identifier.
- Amount mismatch: the payment is half the invoice amount.
- Currency mismatch: the invoice is in USD and the payment is in EUR.

All other records match. The missing-payment records are replaced by the same number of orphan payments, keeping both CSV files at 1,000 rows. Pass `--anomalies-per-type 0` to produce entirely matching data. Payment dates range from the invoice date through 45 days afterward.

## CSV schemas

### `invoices.csv`

| Column | Description | Example |
| --- | --- | --- |
| `invoice_id` | Unique invoice identifier | `INV-000001` |
| `customer_id` | Synthetic customer identifier | `CUST-0004` |
| `invoice_date` | Invoice issue date in ISO 8601 format | `2025-11-24` |
| `due_date` | Payment due date, 30 days after issue | `2025-12-24` |
| `amount` | Invoice amount in decimal currency units | `593.69` |
| `currency` | ISO 4217 currency code | `USD` |

### `payments.csv`

| Column | Description | Example |
| --- | --- | --- |
| `payment_id` | Unique payment identifier | `PAY-000001` |
| `invoice_id` | Identifier of the invoice being paid | `INV-ORPHAN-000001` |
| `payment_date` | Payment date in ISO 8601 format | `2025-12-11` |
| `amount` | Payment amount in decimal currency units | `593.69` |
| `currency` | ISO 4217 currency code | `USD` |
| `payment_method` | Synthetic payment channel | `bank_transfer` |

The `invoice_id` column is the reconciliation key between the two files.

## Load the CSVs into PostgreSQL

The PostgreSQL tables are defined explicitly in `schema.sql` and match the CSV columns. With PostgreSQL running and the five `POSTGRES_*` variables configured in `.env`, run:

```bash
python ingest_postgres.py
```

The loader performs these steps in one database transaction:

1. Creates `raw_invoices` and `raw_payments` if they do not exist.
2. Truncates both raw tables so rerunning the script produces a clean reload.
3. Inserts every row from the two CSV files.
4. Prints source and database row counts and amount totals for verification.

The PostgreSQL schema uses `DATE` for dates, `NUMERIC(12, 2)` for amounts, and text columns for identifiers and labels. The raw tables deliberately do not add a foreign key between payments and invoices, allowing future reconciliation work to detect unmatched records instead of rejecting them during ingestion.

## Run the reconciliation report

After generating and loading the data, run:

```bash
python reconcile.py
```

The script creates the `reconciliation_results` view from `reconciliation.sql` and prints row counts, invoice totals, payment totals, and differences for these mutually exclusive statuses:

| Status | Meaning |
| --- | --- |
| `matched` | Invoice ID, amount, and currency agree. |
| `missing_payment` | An invoice has no payment with the same invoice ID. |
| `missing_invoice` | A payment has no invoice with the same invoice ID. |
| `amount_mismatch` | Invoice and payment amounts differ. |
| `currency_mismatch` | Invoice and payment currencies differ. |

With the default 1,000-row data, the report contains 970 matched rows and 10 rows in each anomaly status. The full outer join produces 1,010 reconciliation rows because missing invoices and missing payments appear separately.

To export the non-matching records for review, pass an output path:

```bash
python reconcile.py --output data/reconciliation_exceptions.csv
```

The export contains one row per exception with its status, identifiers, dates, amounts, currencies, payment method, and amount difference. With the default data it contains 40 rows. The generated exception report is ignored by Git because it is an operational output that can be recreated from PostgreSQL.
