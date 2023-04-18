# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

- Error with the query groups view when passed an invalid `request_id`
- Ordering options in requests list view

## [0.6.0a2] - 2023-04-17

### Fixed

- List annotations when using `Count` - pass `distinct=True` to avoid duplicate rows

## [0.6.0a1] - 2023-04-17

### Removed

- `related_name` parameter from `QueryGroup` model to avoid migrations warnings

## [0.6.0a0] - 2023-04-16

### Added

- Display latest query groups with an N + 1 situation in the dashboard
- Sorting and filtering options in listing views - `django-filter` is now a dependency
- Custom representation of common objects
- Django 4.2 to the test matrix

### Changed

- Updated dashboard and listing views design
- Updated Cython to 3.0.0b2

### Fixed

- `KeyError` in the query group view when a parent query comes from another request

## [0.5.2a0] - 2023-03-08

### Added

- Ignore `runtests.py` files in tracebacks

### Fixed

- `AttributeError` when a queryset tracker is saved before Django finishes iterating over all of its related querysets

## [0.5.1a0] - 2023-02-20

### Added

- CHANGELOG - thanks to [@zerolab](https://github.com/zerolab)

### Fixed

- Catch errors raised in `PyFrame_GetVar`
