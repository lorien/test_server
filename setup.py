from setuptools import setup, find_packages
import os.path

ROOT = os.path.dirname(os.path.realpath(__file__))

setup(
    name = 'test-server',
    version = '0.0.3',
    description = 'Server to test HTTP clients',
    long_description = open(os.path.join(ROOT, 'README.rst')).read(),
    author = 'Gregory Petukhov',
    author_email = 'lorien@lorien.name',
    install_requires = ['tornado'],
    packages = ['test_server', 'script', 'test'],
    license = "MIT",
    classifiers = (
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: Implementation :: CPython',
        'License :: OSI Approved :: MIT License',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ),
)
