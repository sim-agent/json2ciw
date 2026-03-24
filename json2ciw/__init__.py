__author__ = "Tom Monks"
__version__ = "0.4.0"

from .datasets import load_call_centre_model, load_model_file
from .engine import CiwConverter, multiple_replications
from .results import summarise_results

# define what is exported
__all__ = [
    "load_model_file"
    "load_call_centre_model",
    "CiwConverter",
    "multiple_replications"
    "summarise_results"
    "__version__",
    "__author__"
]