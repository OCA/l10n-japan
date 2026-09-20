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

The invoices are grouped by partner, currency and recipient bank:

- An invoice without a recipient bank does not state where it is to be
  remitted, so it is billed together with the invoices of the same
  partner and currency that do have one, instead of getting a billing of
  its own.
- When those invoices point to several recipient banks, the first bank is
  used, which is the one the invoice would have been given by default.
- The same holds for a draft billing that states no recipient bank: it
  is used for the invoices that do state one, and takes their bank,
  unless its own invoices already point to another one. Where several
  banks are in play, the first one is the one that gets to use it.
