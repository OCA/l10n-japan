1.  When creating a new billing, the system automatically finds the most
    recent validated billing for the same partner and calculates:
    - **Previous Billed Amount**: Total amount from the previous billing.
    - **Payment Amount**: Payments received on the previous billing invoices.
    - **Carryover Amount**: Previous billed amount minus payments.
2.  Use the **Manual Adj.** toggle to manually override the computed values
    if needed. This is useful when the previous billing was created before
    this module was installed or when adjustments are required.
3.  When the billing is validated, the current computed values are
    automatically frozen by enabling the manual override toggles. This
    ensures that subsequent payments on previous invoices do not affect
    the validated billing's carryover amounts.
