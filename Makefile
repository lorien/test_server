.PHONY: clean upload qa test

clean:
	find -name '*.pyc' -delete
	find -name '*.swp' -delete
	find -name __pycache__ -delete

upload:
	git push --tags; python setup.py sdist upload

qa:
	python setup.py check -s
	flake8 setup.py test
	pylint setup.py test_server test

test:
	pytest
