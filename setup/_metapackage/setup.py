import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo13-addons-oca-l10n-japan",
    description="Meta package for oca-l10n-japan Odoo addons",
    version=version,
    install_requires=[
        'odoo13-addon-l10n_jp_country_state',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 13.0',
    ]
)
