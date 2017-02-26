.PHONY: clean upload

clean:
	find -name '*.pyc' -delete
	find -name '*.swp' -delete
	find -name __pycache__ -delete

upload:
	python setup.py sdist upload
