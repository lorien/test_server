# Change Log of test-server Library

## [0.0.32] - unreleased
### Changed

## [0.0.31] - 2018-05-05
### Added
* Add support for non-ascii headers

## [0.0.30] - 2018-05-01
### Changed
* Migrate to bottle/webtest/weitress from tornado
* Items of `request['files'][key]` are dicts now

### Removed
* Removed subprocess mode

## [0.0.29] - 2018-04-17
### Changed
* Allow to use null bytes in response headers

## [0.0.28] - 2018-04-08
### Changed
* Restrict tornado dependency version: <5.0.0

## [0.0.27] - 2017-03-12
### Added
* Add partial support for requests in non-UTF-8 encoding

### Fixed
* Fix bug: test server fails to start on non-zero port

### Changed
* Change request/response access method: use direct access
* If the port is zero, then it is select automatically from free ports

## [0.0.26] - 2017-02-26
### Fixed
- Fix missing filelock dependency in setup.py

## [0.0.25] - 2017-02-25
### Added
- Option to run the server in subprocess

## [0.0.24] - 2017-01-29
### Added
- Add `keep_alive` option to start method

### Changed
- Disable keep-alive by default. 

## [0.0.23] - 2017-01-20
### Fixed
- Fix bug: incorrect processing the request['done']

## [0.0.22] - 2017-01-20
### Fixed
- Fix bug: incorrect processing the request['done']

## [0.0.21] - 2017-01-20
### Added
- Add feature: request['done']
- Add method: wait_request
- Add exception: WaitTimeoutError

## [0.0.20] - 2017-01-20
### Changed
- Internfal refactoring

## [0.0.19] - 2017-01-20
### Removed
- Remove timeout_iterator feature

## [0.0.18] - 2017-01-19
### Added
- Add feature: request['client_ip']

## [0.0.17] - 2017-01-19
### Added
- Set server thread daemon=True by default

## [0.0.16] - 2017-01-11
### Fixed
- Fix setup.py

## [0.0.15] - 2017-01-11
### Added
- Add sleep command yielded from callback

## [0.0.14] - 2015-09-10
### Added
- Add support for OPTIONS requests

## [0.0.13] - 2015-06-14
### Fixed
- Fix py3 issue
- Fixed other errors

## [0.0.12] - 2015-06-08
### Fixed
- Fix issue wit closing socket

## [0.0.11] - 2015-04-10
### Added
- Add support for files

## [0.0.10] - 2015-02-22
### Fixed
- Fix Server/Content-Type header issues

## [0.0.9] - 2015-02-19
### Added
- Support iterator in response['data']

## [0.0.8] - 2015-02-19
### Fixed
- Fix bug in processing the callback

## [0.0.7] - 2015-02-19
### Changed
- Change method of setting/getting response parameters

## [0.0.6] - 2015-02-18
### Changed
- Refactoring

## [0.0.5] - 2015-02-17
### Fixed
- Fix socket bug

## [0.0.4] - 2015-02-17
### Fixed
- Fix py3 issues

## [0.0.3] - 2015-02-17
### Changed
- More tests

## [0.0.2] - 2015-02-17
### Added
- Basic features
