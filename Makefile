.PHONY: build venv deps clean release check test docs

build: venv deps

venv:
	virtualenv -p python3 .env

deps:
	.env/bin/pip install -r requirements_dev.txt

clean:
	find -name '*.pyc' -delete
	find -name '*.swp' -delete
	find -name __pycache__ -delete

release:
	git push; git push --tags; rm dist/*; python3 setup.py clean sdist; twine upload dist/*

check:
	python setup.py check -s \
		&& pylint setup.py test_server tests \
		&& flake8 setup.py test_server tests \
		&& pytype setup.py test_server tests \
		&& mypy setup.py test_server tests

test:
	coverage run -m pytest \
		&& coverage report -m

docs:
	rm -r docs/_build \
		&& sphinx-build -b html docs docs/_build
