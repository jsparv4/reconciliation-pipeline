# Reconciliation Pipeline

This repository contains a simple Python script that generates synthetic invoice and payment data for reconciliation experiments. It uses only the Python standard library.

## Generate the data

Run the script from the repository root:

```bash
python generate_data.py
```

This creates `data/invoices.csv` and `data/payments.csv`, each with 1,000 rows. The default random seed is fixed, so repeated runs produce the same data. You can optionally change the row count, seed, or output directory:

```bash
python generate_data.py --count 1000 --seed 42 --output-dir data
```

Each generated invoice has one payment with the same invoice ID, amount, and currency. Payment dates range from the invoice date through 45 days afterward.

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
| `invoice_id` | Identifier of the invoice being paid | `INV-000001` |
| `payment_date` | Payment date in ISO 8601 format | `2025-12-11` |
| `amount` | Payment amount in decimal currency units | `593.69` |
| `currency` | ISO 4217 currency code | `USD` |
| `payment_method` | Synthetic payment channel | `bank_transfer` |

The `invoice_id` column is the reconciliation key between the two files.

## Load the CSVs into PostgreSQL

The PostgreSQL tables are defined explicitly in `schema.sql` and match the CSV columns. Install the one required database driver:

```bash
python -m pip install -r requirements.txt
```

Set a PostgreSQL connection URL and run the loader. In PowerShell:

```powershell
$env:DATABASE_URL = "postgresql://postgres:password@localhost:5432/reconciliation"
python ingest_postgres.py
```

Or pass the connection URL directly:

```bash
python ingest_postgres.py --database-url postgresql://postgres:password@localhost:5432/reconciliation
```

The loader performs these steps in one database transaction:

1. Creates `raw_invoices` and `raw_payments` if they do not exist.
2. Truncates both raw tables so rerunning the script produces a clean reload.
3. Inserts every row from the two CSV files.
4. Prints source and database row counts and amount totals for verification.

The PostgreSQL schema uses `DATE` for dates, `NUMERIC(12, 2)` for amounts, and text columns for identifiers and labels. The raw tables deliberately do not add a foreign key between payments and invoices, allowing future reconciliation work to detect unmatched records instead of rejecting them during ingestion.
