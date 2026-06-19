[![ORCID: Monks](https://img.shields.io/badge/Tom_Monks_ORCID-0000--0003--2631--4481-brightgreen)](https://orcid.org/0000-0003-2631-4481)
[![ORCID: Heather](https://img.shields.io/badge/Amy_Heather_ORCID-0000--0002--6596--3479-brightgreen)](https://orcid.org/0000-0002-6596-3479)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18879547.svg)](https://doi.org/10.5281/zenodo.18879547)

# JSON to Ciw (`json2ciw`)

A simple tool for converting JSON files into functional Ciw simulation models.

## Citation

If you reuse any of the code, or this project supports your work, please provide a citation. The recommended citation detailed are maintained in `CITATION.cff`.

## Development installation instructions

All dependencies are listed in `pyproject.toml`. To run the code locally, we recommend installing [miniforge](https://github.com/conda-forge/miniforge);

> Miniforge is Free and Open Source Software (FOSS) alternative to Anaconda and miniconda that uses conda-forge as the default channel for packages. It installs both `conda` and `mamba` (a drop in replacement for conda) package managers.  We recommend `mamba` for faster resolving of dependencies and installation of packages. 

Navigate to the repository directory in your terminal (or command prompt), then create the environment:

```bash
mamba create -n json2ciw python=3.12
mamba activate json2ciw
pip install -e .
pip install --group dev
```

Alternatively, a fixed environment is provided in `binder/environment.yml`:

```bash
mamba env create -f binder/environment.yml
mamba activate json2ciw
```

## Licence

The materials have been made available under an [MIT license](LICENCE).  The materials are as-is with no liability for the author. Please provide credit if you reuse the code in your own work.

## Key files

* `binder/environment.yml` - Conda environment for local set-up.
* `CHANGELOG.md` - Record of notable changes between versions.
* `CITATION.cff` - Citation metadata for the repository.
* `LICENSE` - Terms of the MIT licence.

## Contributors ✨

<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/badge/all_contributors-2-orange.svg?style=flat-square)](#contributors-)
<!-- ALL-CONTRIBUTORS-BADGE:END -->

Thanks goes to these wonderful people ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://experts.exeter.ac.uk/19244-thomas-monks"><img src="https://avatars.githubusercontent.com/u/881493?v=4?s=100" width="100px;" alt="Tom Monks"/><br /><sub><b>Tom Monks</b></sub></a><br /><a href="https://github.com/sim-agent/json2ciw/commits?author=TomMonks" title="Code">💻</a> <a href="#design-TomMonks" title="Design">🎨</a> <a href="https://github.com/sim-agent/json2ciw/commits?author=TomMonks" title="Documentation">📖</a> <a href="#example-TomMonks" title="Examples">💡</a> <a href="#ideas-TomMonks" title="Ideas, Planning, & Feedback">🤔</a> <a href="#infra-TomMonks" title="Infrastructure (Hosting, Build-Tools, etc)">🚇</a> <a href="#maintenance-TomMonks" title="Maintenance">🚧</a> <a href="https://github.com/sim-agent/json2ciw/commits?author=TomMonks" title="Tests">⚠️</a> <a href="#tutorial-TomMonks" title="Tutorials">✅</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://www.linkedin.com/in/amyheather"><img src="https://avatars.githubusercontent.com/u/92166537?v=4?s=100" width="100px;" alt="Amy Heather"/><br /><sub><b>Amy Heather</b></sub></a><br /><a href="https://github.com/sim-agent/json2ciw/commits?author=amyheather" title="Code">💻</a> <a href="#design-amyheather" title="Design">🎨</a> <a href="https://github.com/sim-agent/json2ciw/commits?author=amyheather" title="Documentation">📖</a> <a href="#example-amyheather" title="Examples">💡</a> <a href="https://github.com/sim-agent/json2ciw/commits?author=amyheather" title="Tests">⚠️</a></td>
    </tr>
  </tbody>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

This project follows the [all-contributors](https://github.com/all-contributors/all-contributors) specification. Contributions of any kind welcome!
