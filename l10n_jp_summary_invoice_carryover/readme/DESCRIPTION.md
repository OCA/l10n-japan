This module extends Japan Summary Invoice to support carryover amount tracking
for recurring billing cycles.

It adds the following fields to billings:

- **Previous Billed Amount**: Total from the previous billing period
- **Payment Amount**: Payments received against the previous billing
- **Carryover Amount**: Outstanding balance carried forward
- **Total Billed Amount**: Carryover plus current purchases

Manual override fields are available to adjust values when needed.

The visibility of carryover amounts in the report can be controlled at
company, partner, and billing levels.
