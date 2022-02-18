.PHONY: build venv deps clean upload check test

build: venv deps

venv:
	virtualenv -p python3 .env

deps:
	.env/bin/pip install -r requirements_dev.txt

clean:
	find -name '*.pyc' -delete
	find -name '*.swp' -delete
	find -name __pycache__ -delete

upload:
	git push --tags; python setup.py sdist upload

check:
	python setup.py check -s \
		&& pylint setup.py test_server tests \
		&& flake8 setup.py test_server tests \
		&& pytype setup.py test_server tests

test:
	coverage run -m pytest \
		&& coverage report -m
