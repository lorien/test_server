# Copyright 2015-2017 Gregory Petukhov (lorien@lorien.name)
# *
# Licensed under the MIT License
import os

from setuptools import setup

ROOT = os.path.dirname(os.path.realpath(__file__))

setup(
    # Meta data
    name='test-server',
    version='0.0.30',
    author='Gregory Petukhov',
    author_email='lorien@lorien.name',
    maintainer="Gregory Petukhov",
    maintainer_email='lorien@lorien.name',
    url='https://github.com/lorien/test_server',
    description='Server to test HTTP clients',
    long_description=open(os.path.join(ROOT, 'README.rst')).read(),
    download_url='https://pypi.python.org/pypi/test-server',
    keywords='test testing server http-server',
    license='MIT License',
    # Package files
    packages=['test_server'],
    install_requires=[
        'webtest',
        'bottle>=0.12.13',
        'six',
    ],
    # Topics
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'License :: OSI Approved :: MIT License',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
