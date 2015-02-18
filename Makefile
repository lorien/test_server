flake:
	flake8 test_server test script

flake_verbose:
	flake8 test_server test script --show-pep8

test:
	run test

coverage:
	coverage erase
	coverage run --source=test_server -m runscript.cli test
	coverage report -m

clean:
	find -name '*.pyc' -delete
	find -name '*.swp' -delete

upload:
	python setup.py sdist upload

pylint:
	pylint --reports=n script test test_server

.PHONY: all build venv flake test vtest testloop cov clean doc
