1.  Create a billing for customer invoices using the functionality of
    the account_billing module, and make adjustments as necessary.
    - **Remit-to Bank**: If not selected, the bank account related to
      the company with the smallest sequence will show in the printed
      document.
    - **Due Date**: The earliest due date among the selected invoices
      will be proposed. Adjust this as necessary as it will show in the
      printed document.
    - **Exclude invoices from billing**: On each invoice form, you can
      check the "Is not for billing" field in the Billing tab to exclude
      specific invoices from the billing process.
2.  Validate the billing. An invoice for tax adjustment will be created
    automatically in case the recalculated tax amount is different from
    the summary of the tax amounts in the selected invoices.
3.  Print the summary invoice report (合計請求書) from *Print \> JP
    Summary Invoice* of the billing.
4.  Once a validated summary invoice has been printed or sent at least
    once, the **Printed/Sent** field is checked automatically, and
    trying to delete the billing raises an error, so that its sequence
    number is never orphaned from accounting reports. Cancel it instead
    if it is no longer valid. If you still need to delete it, uncheck
    the **Printed/Sent** field manually first.
