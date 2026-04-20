# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Dates formatted as YYYY-MM-DD as per [ISO standard](https://www.iso.org/iso-8601-date-and-time-format.html).

Consistent identifier (represents all versions, resolves to latest): 

## 0.10.0

### Changed

* `ProcessModel.to_mermaid()` refactored.  Refactored distribution formatting to function. Added Renege as hexagon with dashed arrow.
* `ProcessModel.get_distributions_df()` now handles renege distributions
* `engine.CiwConverter` now handles renege distributions as part of `generate_params`
* `ui` modified to handle renege distributions.
* `example_app.py` new models demonstrating renege have been added.

### Added

* `schema.Activity` now has a optional `renege_distribution` field.
* Two new examples in `datasets`:  `load_mm1_renege_model` and `load_renege_call_model`
* `04_call_centre_renege.ipynb` example notebook added.

## 0.9.0

### Changed

* Mermaid diagram now has `include_resources` parameter to toggle circles off in complex diagrams.

### Added

* `ProcessModel.get_resources_df()` returns a `pandas.DataFrame` containing a list of resources, their activities and counts.

## 0.8.1

### Fixed

* Mermaid diagram code updated to recognise and display normal distributions.

## 0.8.0

### Added

* `six_node_ucc.json` - a simple version of the 6 node treat-sim urgent care treatment centre example with stationary arrivals.   
* `example_app.py`: added the example treatment centre model.
* `03_urgent_care_treatment_centre_example.ipynb` - example of converting treat-sim json2ciw

### Changed

* `engine.CiwConverter._normal_moments_from_lognormal` updated to static method.

### Removed

* `03_three_node_network_example.ipynb` notebook not needed and removed.

### Fixed

* `ui` patched so that mean and sd of lognormal is converted to underlying normal before passing to `updated_params`

## 0.7.0

### Added 

* `three_node_network.json`: example that modifies the basic jackson network and uses lognormal and normal service distributions in v0.7.0 
* `example_app.py`: added three node example  

### Changed

* `schema.Distribution` now supports "normal" with sample mean and std (`ciw` auto truncates normal at 0)
* `engine.CiwConverter` updated to handle `ciw` normal distribution.  Handles standard deviation parameter when expressed as "std", "sd" or "var" using `_extract_std()` method.

### Fixed

* `engine.CiwConverter` updated handling log normal. Fixed incorrect parameter "standard_deviation". Should have been "sd".
* `jackson_network.json`: updated activity "type" parameter to "activity".

## 0.6.0

### Changed

* `schema.Distribution` now supports "lognormal" with sample mean and std along with "gamma" (shape, scale)
* `engine.CiwConverter` updated to handle `ciw` lognormal and gamma distributions. Lognormal parameters converted to mu and sigma of underlying normal.

### Fixed

* Included missing distribution type in `json2ciw` app sidebar.
* Service distribution now displays mean parameter for the exponential distribution.

## 0.5.0

### Added

* `datasets.load_jackson_network_model()` to load a open jackson network model in JSON format to convert into a `ProcessModel`
* `ProcessModel` has new methods `get_distributions_df` and `get_routing_matrix_df` to help with face validation of model.
  
### Changed

* `app.py` updated the app to switch dynamically between models.

## 0.4.0

### Added

* `json2ciw.ui` and `render_simulation_app` function to automatically create a basic streamlit dashboard interface for a json schema and `ciw` model.

### Changed

* Added `streamlit` as package dependency.
* Added `plotly` as package dependency.

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

