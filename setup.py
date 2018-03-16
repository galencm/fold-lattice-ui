from setuptools import find_packages, setup
setup(
name="fold_ui",
    version="0.1",
    description="",
    author="Galen Curwen-McAdams",
    author_email='',
    platforms=["any"],
    license="Mozilla Public License 2.0 (MPL 2.0)",
    include_package_data=True,
    data_files = [("", ["LICENSE.txt"])],
    url="",
    packages=find_packages(),
    install_requires=['kivy'],
    entry_points = {'console_scripts': ['ma-ui-fold = fold_ui.fold_lattice_ui:main',
                                       ],
                            },
)
