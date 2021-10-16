import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo11-addons-oca-l10n-japan",
    description="Meta package for oca-l10n-japan Odoo addons",
    version=version,
    install_requires=[
        'odoo11-addon-l10n_jp_address_layout',
        'odoo11-addon-l10n_jp_country_state',
        'odoo11-addon-l10n_jp_partner_title_qweb',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 11.0',
    ]
)
