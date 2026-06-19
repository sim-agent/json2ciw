"""Load example process model specifications.."""

import json
from os import PathLike
from pathlib import Path
from typing import Any

MODELS_DIR = Path(__file__).parent / "models"
CALL_CENTRE = "call_centre.json"
JACKSON_NETWORK = "jackson_network.json"
THREE_NODE = "three_node_network.json"
SIX_NODE_UCC = "six_node_ucc.json"
RENEGE = "call_renege.json"
MM1_RENEGE = "mm1_renege.json"


def load_model_file(file_path: str | PathLike[str]) -> dict[str, Any]:
    """Load a model specification from a JSON file.

    Parameters
    ----------
    file_path : str | PathLike[str]
        Path to the JSON file.

    Returns
    -------
    dict[str, Any]
        Parsed JSON model specification.

    """
    with Path.open(file_path) as file:
        return json.load(file)


def load_call_centre_model() -> dict[str, Any]:
    """Load the call centre model specification.

    Returns
    -------
    dict[str, Any]
        Parsed JSON model specification.

    """
    return load_model_file(MODELS_DIR / CALL_CENTRE)


def load_jackson_network_model() -> dict[str, Any]:
    """Load the classic open jackson network model specification.

    Returns
    -------
    dict[str, Any]
        Parsed JSON model specification.

    """
    return load_model_file(MODELS_DIR / JACKSON_NETWORK)


def load_three_node_network_model() -> dict[str, Any]:
    """Load the three-node network model specification.

    Returns
    -------
    dict[str, Any]
        Parsed JSON model specification.

    """
    return load_model_file(MODELS_DIR / THREE_NODE)


def load_six_node_ucc_model() -> dict[str, Any]:
    """Load the six-node urgent care model specification.

    Returns
    -------
    dict[str, Any]
        Parsed JSON model specification.

    """
    return load_model_file(MODELS_DIR / SIX_NODE_UCC)


def load_renege_call_model() -> dict[str, Any]:
    """Load the reneging call centre model specification.

    Returns
    -------
    dict[str, Any]
        Parsed JSON model specification.

    """
    return load_model_file(MODELS_DIR / RENEGE)


def load_mm1_renege_model() -> dict[str, Any]:
    """Load the M/M/1 reneging model specification.

    Returns
    -------
    dict of str to Any
        Parsed JSON model specification.

    """
    return load_model_file(MODELS_DIR / MM1_RENEGE)
