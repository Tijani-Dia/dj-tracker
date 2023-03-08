# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

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
