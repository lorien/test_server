import os.path

from setuptools import setup

ROOT = os.path.dirname(os.path.realpath(__file__))

setup(
    name='test-server',
    version='0.0.26',
    description='Server to test HTTP clients',
    long_description=open(os.path.join(ROOT, 'README.rst')).read(),
    author='Gregory Petukhov',
    author_email='lorien@lorien.name',
    install_requires=['tornado', 'six', 'psutil', 'filelock'],
    packages=['test_server'],
    license="MIT",
    entry_points={
        'console_scripts': [
            'test_server = test_server.server:script_test_server',
        ],
    },
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
