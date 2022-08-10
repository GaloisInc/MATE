from setuptools import find_packages, setup

setup(
    name="mantiserve",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "protobuf",
        "pyzmq==18.1.0",
        "pyelftools",
    ],
)
