from setuptools import setup

setup(
    name="test_server",
    version="0.0.47",
    packages=["test_server"],
    install_requires=[
        "six",
        'typing-extensions; python_version <= "2.7"',
    ],
)
