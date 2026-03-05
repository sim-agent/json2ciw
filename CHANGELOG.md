# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Dates formatted as YYYY-MM-DD as per [ISO standard](https://www.iso.org/iso-8601-date-and-time-format.html).

Consistent identifier (represents all versions, resolves to latest): 

## v0.3.0

### Changed

* `engine.CiwConverter` can now handle "Exponential" being passed with **mean** or **rate** parameters.  If mean is passed them rate is calculated as `1/mean`.
* `schemaa.ProcessModel.to_mermaid()` updated to handle **mean** and **rate**.
* `engine.multiple_replications` now runs using parallel replications for `ciw` (implemented using `joblib`).
* `pyproject.toml` and `environment.yml`updated to include `joblib` dependency.

### Fixed

* `pyproject.toml` updated to include missing `pydantic` dependency.
* `environment.yml`updated to include missing `rich` dependency.
* `call_centre.json` inter-arrival distribution fixed to use `mean` as parameter rather than `rate`.

## v0.2.0

### Added

* Function to run replications and obtain automatic results from all queues and activites in the ciw model
* `schema`: module containing the `pydantic` classes describing a valid json `ProcessModel`
* Convert a valid `ProcessModel` to a `mermaid` diagram.


## :seedling: v0.1.0

* Cloned from https://github.com/TheOpenScienceNerd/tosn_python_template

### Added

* `json2ciw` installable Python package
* `datasets` module for importing JSON files (no validation)
* `engine` module for converting a valid JSON file into a ciw model.
* `tests`: testing data loading.

