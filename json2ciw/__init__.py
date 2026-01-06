__author__ = "Tom Monks"
__version__ = "0.1.0"

from .datasets import load_call_centre_model
from .engine import create_ciw_network

# define what is exported
__all__ = [
    "load_call_centre_model",
    "create_ciw_network",
    "__version__",
    "__author__"
]