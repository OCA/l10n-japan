This module stores the postcode of Japanese contacts in one format, `NNN-NNNN`
by default, whichever way it was entered: without the hyphen, in full-width
digits, with another dash character, or with the 〒 mark and spaces.

The format is applied when a contact is created, when its postcode is written
and when its country or company changes, so it covers imports and API calls as
well as the form. A contact counts as Japanese when its country is Japan or,
with no country set, when its company is in Japan. For a contact shared between
companies, that is the company the user is working in. A value that does not
read as exactly seven digits is stored as entered, so that it stays visible for
correction.

Postcodes already stored are not changed on installation; see *Usage* to bring
them to the format.
