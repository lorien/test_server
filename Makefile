.PHONY: clean upload check test

clean:
	find -name '*.pyc' -delete
	find -name '*.swp' -delete
	find -name __pycache__ -delete

upload:
	git push --tags; python setup.py sdist upload

check:
	python setup.py check -s && pylint setup.py test_server tests && flake8 setup.py test_server tests

test:
	pytest
