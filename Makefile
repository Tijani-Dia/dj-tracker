default: format

clean:
	find . -name '*.pyc' -exec rm -rf {} +
	find . -name '__pycache__' -exec rm -rf {} +
	find . -name '*.egg-info' -exec rm -rf {} +
	rm -rf dist/ build/ .pytest_cache/

format:
	autoflake -i -r --remove-all-unused-imports src/dj_tracker/* tests
	isort src/dj_tracker tests setup.py manage.py
	black src/dj_tracker tests setup.py manage.py
	flake8 src/dj_tracker tests setup.py manage.py --ignore E501,W503

format-client:
	npx prettier --write docs README.md --tab-width=4
	npx prettier --write *.yml .github --tab-width=2

format-html:
	djlint --reformat --quiet src/dj_tracker/templates

test:
	python manage.py test

coverage:
	coverage run --source=src/dj_tracker manage.py test
	coverage report -m
	coverage html
