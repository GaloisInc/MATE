from setuptools import find_packages, setup

with open("./README.md") as f:
    long_description = f.read()

with open("./requirements.txt") as f:
    requirements = list(f.read().splitlines())

setup(
    name="mate",
    version="0.0.1-pre.0",
    license="BSD-3-Clause",
    author="The MATE authors",
    author_email="mate@galois.com",
    description="MATE's core backend library",
    long_description=long_description,
    long_description_content_type="text/markdown",
    # url="TODO",
    project_urls={"Documentation": "https://mate.galois.com"},
    scripts=["bin/mate", "bin/mate-bridge", "bin/mate-docs"],
    packages=find_packages(),
    include_package_data=True,
    platforms="any",
    python_requires=">=3.8",
    install_requires=requirements,
)
