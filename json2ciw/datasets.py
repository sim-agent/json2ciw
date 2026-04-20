import json
from typing import Dict, Any

from pathlib import Path

# arrivals -> operator service -> % nurse call back or exit -> exit
CALL_CENTRE_FILE_NAME = "call_centre.json"
CALL_CENTRE_PATH = Path(__file__).parent.joinpath("models", CALL_CENTRE_FILE_NAME)

# classic open jackson network example
JACKSON_NETWORK_FILE_NAME = "jackson_network.json"
JACKSON_NETWORK_PATH = Path(__file__).parent.joinpath("models", JACKSON_NETWORK_FILE_NAME)

# modified open jackson network example
THREE_NODE_FILE_NAME = "three_node_network.json"
THREE_NODE_PATH = Path(__file__).parent.joinpath("models", THREE_NODE_FILE_NAME)

# modified version of treatsim - 6 node network
SIX_NODE_UCC_FILE_NAME = "six_node_ucc.json"
SIX_NODE_UCC_PATH = Path(__file__).parent.joinpath("models", SIX_NODE_UCC_FILE_NAME)

# Call centre example with reneging calls
RENEGE_FILE_NAME = "call_renege.json"
RENEGE_PATH = Path(__file__).parent.joinpath("models", RENEGE_FILE_NAME)

# m/m/1 with renege
MM1_RENEGE_FILE_NAME = "mm1_renege.json"
MM1_RENEGE_PATH = Path(__file__).parent.joinpath("models", MM1_RENEGE_FILE_NAME)


def load_model_file(file_path: str) -> Dict[str, Any]:
    """
    Load a JSON specification for a call centre model from a file.

    Parameters
    ----------
    file_path : str, optional
        The absolute or relative path to the JSON file containing the model 
        specification. Defaults to CALL_CENTRE_PATH ('models/call_centre.json').

    Returns
    -------
    Dict[str, Any]
        A dictionary containing the parsed JSON data. The keys are strings
        representing configuration fields (e.g., "process", "activities") 
        and values are the corresponding model parameters.

    Raises
    ------
    FileNotFoundError
        If the file specified by `file_path` cannot be found.
    json.JSONDecodeError
        If the file content is not valid JSON.
    OSError
        If there are permissions issues or other I/O errors opening the file.
    """
    with open(file_path, 'r') as file:
        return json.load(file)

def load_call_centre_model() -> Dict[str, Any]:
    """
    Load a JSON specification for a call centre model from a file.

    Returns
    -------
    Dict[str, Any]
        A dictionary containing the parsed JSON data. The keys are strings
        representing configuration fields (e.g., "process", "activities") 
        and values are the corresponding model parameters.

    Raises
    ------
    FileNotFoundError
        If the file specified by `file_path` cannot be found.
    json.JSONDecodeError
        If the file content is not valid JSON.
    OSError
        If there are permissions issues or other I/O errors opening the file.
    """
    return load_model_file(CALL_CENTRE_PATH)


def load_jackson_network_model() -> Dict[str, Any]:
    """
    Load a JSON specification for a classic open jackson network
    problem from file.

    Returns
    -------
    Dict[str, Any]
        A dictionary containing the parsed JSON data. The keys are strings
        representing configuration fields (e.g., "process", "activities") 
        and values are the corresponding model parameters.

    Raises
    ------
    FileNotFoundError
        If the file specified by `file_path` cannot be found.
    json.JSONDecodeError
        If the file content is not valid JSON.
    OSError
        If there are permissions issues or other I/O errors opening the file.
    """
    return load_model_file(JACKSON_NETWORK_PATH)

def load_three_node_network_model() -> Dict[str, Any]:
    """
    Load a JSON specification for a simple node network
    with mixed distribution types from file

    Returns
    -------
    Dict[str, Any]
        A dictionary containing the parsed JSON data. The keys are strings
        representing configuration fields (e.g., "process", "activities") 
        and values are the corresponding model parameters.

    Raises
    ------
    FileNotFoundError
        If the file specified by `file_path` cannot be found.
    json.JSONDecodeError
        If the file content is not valid JSON.
    OSError
        If there are permissions issues or other I/O errors opening the file.
    """
    return load_model_file(THREE_NODE_PATH)

def load_six_node_ucc_model() -> Dict[str, Any]:
    """
    Load a JSON specification for a Urgent care centre
    with mixed distribution types and six nodes
    
    Returns
    -------
    Dict[str, Any]
        A dictionary containing the parsed JSON data. The keys are strings
        representing configuration fields (e.g., "process", "activities") 
        and values are the corresponding model parameters.

    Raises
    ------
    FileNotFoundError
        If the file specified by `file_path` cannot be found.
    json.JSONDecodeError
        If the file content is not valid JSON.
    OSError
        If there are permissions issues or other I/O errors opening the file.
    """
    return load_model_file(SIX_NODE_UCC_PATH)

def load_renege_call_model() -> Dict[str, Any]:
    """
    Load a JSON specification for a Urgent care call
    centre with calls that renege if they wait for too long
    
    Returns
    -------
    Dict[str, Any]
        A dictionary containing the parsed JSON data. The keys are strings
        representing configuration fields (e.g., "process", "activities") 
        and values are the corresponding model parameters.

    Raises
    ------
    FileNotFoundError
        If the file specified by `file_path` cannot be found.
    json.JSONDecodeError
        If the file content is not valid JSON.
    OSError
        If there are permissions issues or other I/O errors opening the file.
    """
    return load_model_file(RENEGE_PATH)

def load_mm1_renege_model() -> Dict[str, Any]:
    """
    Load a JSON specification for a M/M/1 with
    customers that renege if they wait for too long

    Returns
    -------
    Dict[str, Any]
        A dictionary containing the parsed JSON data. The keys are strings
        representing configuration fields (e.g., "process", "activities")
        and values are the corresponding model parameters.

    Raises
    ------
    FileNotFoundError
        If the file specified by `file_path` cannot be found.
    json.JSONDecodeError
        If the file content is not valid JSON.
    OSError
        If there are permissions issues or other I/O errors opening the file.
    """
    return load_model_file(MM1_RENEGE_PATH)

