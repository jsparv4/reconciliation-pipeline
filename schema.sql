CREATE TABLE IF NOT EXISTS raw_invoices (
    invoice_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    invoice_date DATE NOT NULL,
    due_date DATE NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    currency CHAR(3) NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_payments (
    payment_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    payment_date DATE NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    currency CHAR(3) NOT NULL,
    payment_method TEXT NOT NULL
);
