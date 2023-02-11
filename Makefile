format:
	autoflake -i -r --remove-all-unused-imports src/dj_tracker/*.py tests
	isort src/dj_tracker tests tutorial setup.py manage.py
	black src/dj_tracker tests tutorial setup.py manage.py
	flake8 src/dj_tracker tests tutorial setup.py manage.py

format-client:
	npx prettier --write docs README.md tutorial/README.md styles *.js --tab-width=4
	npx prettier --write *.yml .github --tab-width=2

format-html:
	djlint --reformat --quiet src/dj_tracker/templates

test:
	python manage.py test

coverage:
	coverage run manage.py test
	coverage report -m
	coverage html

watch-styles:
	tailwindcss -i styles/main.css -o src/dj_tracker/static/dj_tracker/css/main.css --watch

build-styles:
	tailwindcss -i styles/main.css -o src/dj_tracker/static/dj_tracker/css/main.css --minify

clean:
	find . -name '*.pyc' -exec rm -rf {} +
	find . -name '__pycache__' -exec rm -rf {} +
	find . -name '*.egg-info' -exec rm -rf {} +
	rm -rf dist/ build/ .pytest_cache/ cython_debug/
