To use this module,

- Go to *Invoicing -\> Customers or Vendors -\> Create Billing From
  Cutoff*
- Set the cutoff date and click on *Create Billings*

The cutoff date you enter becomes the threshold date of the billing:

- A new billing is created with *Invoice Date* as its threshold date
  type and the cutoff date as its threshold date.
- When the invoices are added to an existing draft billing, its
  threshold date is moved forward to the cutoff date. A threshold date
  that is already later is kept, so that it is never lowered.
- A draft billing whose threshold date type is *Due Date* is not reused.
  As the cutoff date is derived from the invoice date, applying it to
  such a billing would leave its threshold date earlier than the due
  dates of its lines and prevent the billing from being validated.
