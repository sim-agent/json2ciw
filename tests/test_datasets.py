"""
Test the functionality within the dataset module.

There are two functions:

1. `load_model_file`

The function used for loading a file (at the moment there is no verification)

2. `load_call_centre_model`

Convenience wrapper for `load_model_file` that returns the JSON schema for 
a simple call centre model.

"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch

# functions to test
from json2ciw.datasets import (
    load_model_file, 
    load_call_centre_model, 
    CALL_CENTRE_PATH
)

# -----------------------------------------------------------------------------
# 1. Tests for 'load_model_file' 
# -----------------------------------------------------------------------------

def test_load_model_file_success(tmp_path):
    """
    Test that load_model_file correctly reads/returns JSON from a valid path.
    """
    # Create a dummy JSON file in the pytest temp directory
    dummy_data = {"process": {"name": "Test Process"}}
    dummy_file = tmp_path / "dummy_model.json"
    dummy_file.write_text(json.dumps(dummy_data), encoding='utf-8')

    # Execute
    result = load_model_file(str(dummy_file))

    # Assert
    assert result == dummy_data

def test_load_model_file_not_found():
    """Test that FileNotFoundError is raised for non-existent files."""
    with pytest.raises(FileNotFoundError):
        load_model_file("non_existent_path.json")

def test_load_model_file_bad_json(tmp_path):
    """Test that JSONDecodeError is raised for corrupt files."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ this is broken json", encoding='utf-8')

    with pytest.raises(json.JSONDecodeError):
        load_model_file(str(bad_file))

# -----------------------------------------------------------------------------
# 2. Test for 'load_call_centre_model'
# -----------------------------------------------------------------------------

def test_load_call_centre_model_uses_correct_default():
    """
    Test that load_call_centre_model calls load_model_file with the 
    expected constant CALL_CENTRE_PATH.
    
    Mocks 'load_model_file' so we don't need the actual default 
    file to exist during this test.
    """
    # We patch the function 'load_model_file' inside the module where it is defined
    with patch('json2ciw.datasets.load_model_file') as mock_load:
        # Setup the mock to return something simple
        mock_load.return_value = {"status": "mocked"}
        
        # Execute the wrapper function
        result = load_call_centre_model()
        
        # check load_model_file function was called.
        assert result == {"status": "mocked"}
        
        # check it called the internal function with the specific constant
        mock_load.assert_called_once_with(CALL_CENTRE_PATH)
