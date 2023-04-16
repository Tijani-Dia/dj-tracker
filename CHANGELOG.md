# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Display latest query groups with an N + 1 situation in the dashboard
- Sorting and filtering options in listing views - `django-filter` is now a dependency
- Custom representation of common objects

### Changed

- Updated dashboard and listing views design

### Fixed

- `KeyError` in the query group view when a parent query comes from another request

### Removed

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
