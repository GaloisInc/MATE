from setuptools import find_packages, setup


def readme():
    """Used to return text for long description in setup."""
    with open("README.md") as f:
        return f.read()


setup(
    name="smt2lib",
    version="0.1",
    description="Modified SMTv2 parser from ANTLR specification",
    long_description=readme(),
    packages=find_packages(),
    package_data={"": ["smt2lib/SMTLIBv2*"]},
    author="Eric Kilmer",
    author_email="eric.kilmer@trailofbits.com",
    install_requires=["antlr4-python3-runtime==4.7.2"],
)
