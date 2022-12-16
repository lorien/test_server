# Documentation for test_server package

[![Test Status](https://github.com/lorien/test_server/actions/workflows/test.yml/badge.svg)](https://github.com/lorien/test_server/actions/workflows/test.yml)
[![Code Quality](https://github.com/lorien/test_server/actions/workflows/check.yml/badge.svg)](https://github.com/lorien/test_server/actions/workflows/test.yml)
[![Type Check](https://github.com/lorien/test_server/actions/workflows/mypy.yml/badge.svg)](https://github.com/lorien/test_server/actions/workflows/mypy.yml)
[![Test Coverage Status](https://coveralls.io/repos/github/lorien/test_server/badge.svg)](https://coveralls.io/github/lorien/test_server)
[![Documentation Status](https://readthedocs.org/projects/test_server/badge/?version=latest)](http://user-agent.readthedocs.org)

Simple HTTP Server for testing HTTP clients.


## Installation

Run `pip install -U test_server`


## Usage Example

```python
from unittest import TestCase
import unittest
from urllib.request import urlopen

from test_server import TestServer, Response, HttpHeaderStorage


class UrllibTestCase(TestCase):
   @classmethod
   def setUpClass(cls):
       cls.server = TestServer()
       cls.server.start()

   @classmethod
   def tearDownClass(cls):
       cls.server.stop()

   def setUp(self):
       self.server.reset()

   def test_get(self):
       self.server.add_response(
           Response(
               data=b"hello",
               headers={"foo": "bar"},
           )
       )
       self.server.add_response(Response(data=b"zzz"))
       url = self.server.get_url()
       info = urlopen(url)
       self.assertEqual(b"hello", info.read())
       self.assertEqual("bar", info.headers["foo"])
       info = urlopen(url)
       self.assertEqual(b"zzz", info.read())
       self.assertTrue("bar" not in info.headers)


   unittest.main()
```
