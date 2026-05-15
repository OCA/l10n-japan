As of Odoo 17, the Japan prefecture (`res.country.state`) records are
shipped with their native Japanese names (e.g. `東京都`, `北海道`) as the
source value. This module overrides those records to use English names
(e.g. `Tokyo`, `Hokkaido`) as the source and provides Japanese
translations, so users with `ja_JP` selected continue to see the native
prefecture names while other users see the romanized English names.
