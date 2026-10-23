This module introduces a function that automatically retrieves and fills
in the Japanese address details for a partner using the zipcloud
service, provided that the following conditions are met.

- The partner is Japanese: its country is Japan or, with no country set,
  its company is in Japan (the current company for a shared partner).
- A valid postcode is entered for the partner.

The postcode is formatted as configured in l10n_jp_partner_zip
(`NNN-NNNN` by default). A value that does not read as a Japanese
postcode raises an error.

Note that in order to have the prefecture proposed automatically, you
need to have the prefecture records in Japanese (e.g. "福岡県" instead
of "Fukuoka"). This can be done by overriding the name of correspoinding
res.country.state records, or by installing the l10n_jp_country_state
module.
