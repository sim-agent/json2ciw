[![ORCID: Monks](https://img.shields.io/badge/Tom_Monks_ORCID-0000--0003--2631--4481-brightgreen)](https://orcid.org/0000-0003-2631-4481)
[![ORCID: Heather](https://img.shields.io/badge/Amy_Heather_ORCID-0000--0002--6596--3479-brightgreen)](https://orcid.org/0000-0002-6596-3479)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18879547.svg)](https://doi.org/10.5281/zenodo.18879547)

# JSON to Ciw (`json2ciw`)

🎓 A simple tool that can convert JSON file to a functional Ciw simulation model.

## License

The materials have been made available under an [MIT license](LICENCE).  The materials are as-is with no liability for the author. Please provide credit if you reuse the code in your own work.

## Citation

If you reuse any of the code, or the tutorial helps you work, please provide a citation.

```bibtex
@software{json2ciw,
  author       = {Monks, Thomas},
  title        = {json2ciw},
  month        = apr,
  year         = 2026,
  publisher    = {Zenodo},
  version      = {v0.10.0},
  doi          = {10.5281/zenodo.18879547},
  url          = {https://doi.org/10.5281/zenodo.18879547},
}
```

## Installation instructions

### Installing dependencies

All dependencies are listed in [`binder/environment.yml`](https://github.com/sim-agent/json2ciw/blob/main/binder/environment.yml) and are pulled from conda-forge. To run the code locally, we recommend installing [miniforge](https://github.com/conda-forge/miniforge);

> Miniforge is Free and Open Source Software (FOSS) alternative to Anaconda and miniconda that uses conda-forge as the default channel for packages. It installs both `conda` and `mamba` (a drop in replacement for conda) package managers.  We recommend `mamba` for faster resolving of dependencies and installation of packages. 

Navigate to the repository directory in your terminal (or command prompt), then create the environment:

```bash
mamba env create -f binder/environment.yml
```

Activate the environment:

```bash
mamba activate json2ciw
```

## Key files

* `binder/environment.yml` - Contains the conda environment if you wish to work the models.
* `CHANGELOG.md` - Changelog with record of notable changes to project between versions.
* `CITATION.cff` - Citation information for the code.
* `LICENSE` - Details of the MIT permissive license of this work.
