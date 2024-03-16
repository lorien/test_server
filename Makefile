.PHONY: init venv deps dirs clean test release ruff mypy pylint check build coverage check-full

FILES_CHECK_MYPY = test_server tests
FILES_CHECK_ALL = $(FILES_CHECK_MYPY)

init: venv deps dirs

venv:
	virtualenv -p python3 .env

deps:
	.env/bin/pip install -r requirements_dev.txt
	.env/bin/pip install -e .

dirs:
	if [ ! -e var/run ]; then mkdir -p var/run; fi
	if [ ! -e var/log ]; then mkdir -p var/log; fi

clean:
	find -name '*.pyc' -delete
	find -name '*.swp' -delete
	find -name '__pycache__' -delete

pytest:
	pytest -n30 -x --cov test_server --cov-report term-missing

test:
	pytest --cov test_server --cov-report term-missing

release:
	git push \
	&& git push --tags \
	&& make build \
	&& twine upload dist/*

mypy:
	mypy --strict $(FILES_CHECK_MYPY)

pylint:
	pylint -j0 $(FILES_CHECK_ALL)

ruff:
	ruff check $(FILES_CHECK_ALL)

check: ruff mypy pylint

check-full: check
	tox -e check-minver

build:
	rm -rf *.egg-info
	rm -rf dist/*
	python -m build --sdist

coverage:
	pytest --cov selection --cov-report term-missing
