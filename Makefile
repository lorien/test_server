.PHONY: clean upload viewdoc

clean:
	find -name '*.pyc' -delete
	find -name '*.swp' -delete
	find -name __pycache__ -delete

upload:
	git push --tags; python setup.py sdist upload

viewdoc:
	x-www-browser docs/_build/html/index.html
