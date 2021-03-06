from setuptools import find_packages, setup

setup(
    name="fold_ui",
    version="0.1",
    description="",
    author="Galen Curwen-McAdams",
    author_email="",
    platforms=["any"],
    license="Mozilla Public License 2.0 (MPL 2.0)",
    include_package_data=True,
    url="",
    packages=find_packages(),
    install_requires=["kivy", "ma_cli", "keli", "pre-commit"],
    dependency_links=[
        "https://github.com/galencm/ma-cli/tarball/master#egg=ma_cli-0.1",
        "https://github.com/galencm/machinic-keli/tarball/master#egg=keli-0.1",
    ],
    entry_points={
        "console_scripts": [
            "ma-ui-fold = fold_ui.fold_lattice_ui:main",
            "fold-ui = fold_ui.fold_lattice_ui:main",
            "fold-ui-fairytale = fold_ui.fairy_tale:main",
            "fold-ui-sequence = fold_ui.sequence_cli:main",
        ]
    },
)
