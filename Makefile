.PHONY: init deps py27 dirs clean pytest test release mypy pylint ruff check build coverage

FILES_CHECK_MYPY = test_server tests
FILES_CHECK_ALL = $(FILES_CHECK_MYPY)
PY2_ROOT = /home/user/.pyenv/versions/2.7.18

init: py27 deps dirs

deps:
	.venv/bin/pip install -r requirements_dev.txt
	.venv/bin/pip install .

py27:
	$(PY2_ROOT)/bin/pip install virtualenv
	$(PY2_ROOT)/bin/virtualenv --python=$(PY2_ROOT)/bin/python2.7 .venv
	#.venv/bin/pip install -r requirements_dev.txt


dirs:
	if [ ! -e var/run ]; then mkdir -p var/run; fi
	if [ ! -e var/log ]; then mkdir -p var/log; fi

clean:
	find -name '*.pyc' -delete
	find -name '*.swp' -delete
	find -name '__pycache__' -delete

pytest:
	pytest -n10 -x --cov test_server --cov-report term-missing

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

build:
	rm -rf *.egg-info
	rm -rf dist/*
	python -m build --sdist

coverage:
	pytest --cov selection --cov-report term-missing
