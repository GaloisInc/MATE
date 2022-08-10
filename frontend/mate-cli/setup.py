#!/usr/bin/env python3

from setuptools import find_packages, setup

with open("./README.md") as f:
    long_description = f.read()

with open("./requirements.txt") as f:
    requirements = list(f.read().splitlines())

setup(
    name="mate-cli",
    version="0.0.1",
    license="BSD-3-Clause",
    author="The MATE authors",
    author_email="mate@galois.com",
    description="A CLI for the MATE REST API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    # url="TODO",
    project_urls={"Documentation": "https://mate.galois.com"},
    packages=find_packages(),
    platforms="any",
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": ["mate-cli = mate_cli.cli:cli"],
    },
)
