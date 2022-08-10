from setuptools import setup


def readme():
    """Used to return text for long description in setup."""
    with open("README.md") as f:
        return f.read()


setup(
    name="dwarfcore",
    version="0.1",
    description="DWARFv4 extensions and plugins for Manticore",
    long_description=readme(),
    url="http://github.com/trailofbits/chess/dwarfcore",
    author="Eric Kilmer",
    author_email="eric.kilmer@trailofbits.com",
    packages=["dwarfcore"],
    zip_safe=False,
)
