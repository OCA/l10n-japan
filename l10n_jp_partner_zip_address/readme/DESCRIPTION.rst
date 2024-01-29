This module introduces a function that automatically retrieves and fills in the Japanese
address details for a partner using the zipcloud service, provided that the following
conditions are met.

* Country is Japan or no country is set for the partner.
* A valid postcode is entered for the partner.

Note that in order to have the prefecture proposed automatically, you need to have the
prefecture records in Japanese (e.g. "福岡県" instead of "Fukuoka"). This can be done by
overriding the name of correspoinding `res.country.state` records, or by installing the
l10n_jp_country_state module.
