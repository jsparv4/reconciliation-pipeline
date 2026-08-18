CREATE OR REPLACE VIEW reconciliation_results AS
SELECT
    COALESCE(invoice.invoice_id, payment.invoice_id) AS invoice_id,
    payment.payment_id,
    invoice.customer_id,
    invoice.invoice_date,
    invoice.due_date,
    payment.payment_date,
    invoice.amount AS invoice_amount,
    payment.amount AS payment_amount,
    invoice.currency AS invoice_currency,
    payment.currency AS payment_currency,
    payment.payment_method,
    CASE
        WHEN invoice.invoice_id IS NULL THEN 'missing_invoice'
        WHEN payment.invoice_id IS NULL THEN 'missing_payment'
        WHEN invoice.currency <> payment.currency THEN 'currency_mismatch'
        WHEN invoice.amount <> payment.amount THEN 'amount_mismatch'
        ELSE 'matched'
    END AS reconciliation_status
FROM raw_invoices AS invoice
FULL OUTER JOIN raw_payments AS payment
    ON invoice.invoice_id = payment.invoice_id;
