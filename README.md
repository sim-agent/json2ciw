[![ORCID: Monks](https://img.shields.io/badge/Tom_Monks_ORCID-0000--0003--2631--4481-brightgreen)](https://orcid.org/0000-0003-2631-4481)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# Title

🎓 This tutorial aims to [INSERT].  By following the tutorial you will:

* ✅ Gain ...
* ✅ Understand ...
* ✅ Build ...
* 🎁 **Bonus**: ...
* 
## License

The materials have been made available under an [MIT license](LICENCE).  The materials are as-is with no liability for the author. Please provide credit if you reuse the code in your own work.

## Citation

If you reuse any of the code, or the tutorial helps you work, please provide a citation.

```bibtex
@software{TheOpenScienceNerd_Template_
author = {Monks, Thomas},
license = {MIT},
title = {{TheOpenScienceNerd - [INSERT TITLE]}},
url = {https://github.com/TheOpenScienceNerd/tosn_python_template}
}
```

## Installation instructions

### Installing dependencies

All dependencies can be found in [`binder/environment.yml`]() and are pulled from conda-forge.  To run the code locally, we recommend installing [miniforge](https://github.com/conda-forge/miniforge);

> miniforge is Free and Open Source Software (FOSS) alternative to Anaconda and miniconda that uses conda-forge as the default channel for packages. It installs both conda and mamba (a drop in replacement for conda) package managers.  We recommend mamba for faster resolving of dependencies and installation of packages. 

navigating your terminal (or cmd prompt) to the directory containing the repo and issuing the following command:

```bash
mamba env create -f binder/environment.yml
```

Activate the mamba environment using the following command:

```bash
mamba activate [INSERT]
```

Run Jupyter-lab

```bash
jupyter-lab
```

## Repo overview

```
.
├── binder
│   └── environment.yml
├── CHANGELOG.md
├── CITATION.cff
├── LICENSE
└── README.md
```

* `binder/environment.yml` - contains the conda environment if you wish to work the models.
* `CHANGES.md` - changelog with record of notable changes to project between versions.
* `CITATION.cff` - citation information for the code.
* `LICENSE` - details of the MIT permissive license of this work.
