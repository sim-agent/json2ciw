import json
from typing import Dict, Any

# arrivals -> operator service -> % nurse call back or exit -> exit
CALL_CENTRE_PATH = 'models/call_centre.json'

def load_call_centre(file_path: str = CALL_CENTRE_PATH) -> Dict[str, Any]:
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
