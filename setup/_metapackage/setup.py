import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo12-addons-oca-l10n-japan",
    description="Meta package for oca-l10n-japan Odoo addons",
    version=version,
    install_requires=[
        'odoo12-addon-l10n_jp_address_layout',
        'odoo12-addon-l10n_jp_country_state',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
    ]
)
