This module extends the Account Payment Terms functionality by introducing the 
fields: *has_cutoff_day*, *months*, and *cutoff_day* in `account.payment.term.line`.

With this feature, users can define a specific cutoff day for payment terms. If an 
invoice is dated after this cutoff day, the system will automatically shift the due 
date by one additional month.

It also adds the cutoff_date field in account.move.
