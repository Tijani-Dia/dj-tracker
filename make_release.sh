#!/bin/sh

# Cleanup
find . -name '*.pyc' -exec rm -rf {} +
find . -name '__pycache__' -exec rm -rf {} +
find . -name '*.egg-info' -exec rm -rf {} +
rm -rf dist/ build/

# Build
python3 -m build

# Upload
twine upload dist/*
