from setuptools import setup


def readme():
    with open("README.md") as f:
        return f.read()


setup(
    name="dwarflang",
    version="0.1",
    description="An implementation of the DWARFv4 stack machine",
    long_description=readme(),
    url="http://github.com/trailofbits/chess",
    author="Langston Barrett",
    author_email="langston@galois.com",
    license="Apache2",
    packages=["dwarflang", "dwarflang.eval"],
    zip_safe=False,
)
