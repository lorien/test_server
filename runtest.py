#!/usr/bin/env python
# coding: utf-8
import unittest
import sys
from argparse import ArgumentParser

TEST_LIST = (
    'test.server',
)


def main():
    parser = ArgumentParser()
    parser.add_argument('-t', '--test-only', help='Run only specified tests')
    opts = parser.parse_args()

    if opts.test_only:
        test_list = [opts.test_only]
    else:
        test_list = TEST_LIST

    # Ensure that all test modules are imported correctly
    for path in test_list:
        __import__(path, None, None, ['foo'])

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for path in test_list:
        mod_suite = loader.loadTestsFromName(path)
        for some_suite in mod_suite:
            for test in some_suite:
                suite.addTest(test)

    runner = unittest.TextTestRunner()

    result = runner.run(suite)

    if result.wasSuccessful():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
