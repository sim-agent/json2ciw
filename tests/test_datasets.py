"""Tests for datasets module."""

import json
from unittest.mock import patch

import pytest

# functions to test
from json2ciw.datasets import (
    CALL_CENTRE,
    MODELS_DIR,
    load_call_centre_model,
    load_model_file,
)

# -----------------------------------------------------------------------------
# 1. Tests for 'load_model_file'
# -----------------------------------------------------------------------------


def test_load_model_file_success(tmp_path):
    """Test load_model_file reads JSON from valid path."""
    # Create a dummy JSON file in the pytest temp directory
    dummy_data = {"process": {"name": "Test Process"}}
    dummy_file = tmp_path / "dummy_model.json"
    dummy_file.write_text(json.dumps(dummy_data), encoding="utf-8")

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
    bad_file.write_text("{ this is broken json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        load_model_file(str(bad_file))


# -----------------------------------------------------------------------------
# 2. Test for 'load_call_centre_model'
# -----------------------------------------------------------------------------


def test_load_call_centre_model_uses_correct_default():
    """Test load_call_centre_model uses CALL_CENTRE_PATH."""
    # Patch function 'load_model_file' inside the module where it's defined
    with patch("json2ciw.datasets.load_model_file") as mock_load:
        # Setup the mock to return something simple
        mock_load.return_value = {"status": "mocked"}

        # Execute the wrapper function
        result = load_call_centre_model()

        # check load_model_file function was called.
        assert result == {"status": "mocked"}

        # check it called the internal function with the specific constant
        mock_load.assert_called_once_with(MODELS_DIR / CALL_CENTRE)
