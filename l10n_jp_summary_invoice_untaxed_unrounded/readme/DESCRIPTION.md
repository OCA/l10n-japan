On the summary invoice report, per-line subtotals and the per-invoice
"Amount Untaxed" are shown with the currency precision. Under **Round Globally**
tax rounding with a zero-decimal currency (such as JPY), this rounding can hide
decimals, so the displayed amounts no longer reconcile with the invoice untaxed
total.

This bridge module applies the unrounded disclosure provided by
`account_invoice_report_untaxed_unrounded` to the summary invoice report: the
per-line subtotal (`price_subtotal_unrounded`) and the per-invoice untaxed
amount (`amount_untaxed_unrounded`) are shown at full precision, formatted with
the per-company *Untaxed Unrounded Digits*.

It installs automatically when both `l10n_jp_summary_invoice` and
`account_invoice_report_untaxed_unrounded` are present.
