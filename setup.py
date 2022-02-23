import os

from setuptools import setup

ROOT = os.path.dirname(os.path.realpath(__file__))

setup(
    # Meta data
    name="test_server",
    version="0.0.35",
    author="Gregory Petukhov",
    author_email="lorien@lorien.name",
    maintainer="Gregory Petukhov",
    maintainer_email="lorien@lorien.name",
    url="https://github.com/lorien/test_server",
    description="Server for testing HTTP clients",
    long_description=open(os.path.join(ROOT, "README.rst"), encoding="utf-8").read(),
    download_url="https://pypi.python.org/pypi/test_server",
    keywords="test testing server http-server",
    license="MIT License",
    # Package files
    packages=["test_server"],
    install_requires=[],
    # Topics
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: Implementation :: CPython",
        "License :: OSI Approved :: MIT License",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
