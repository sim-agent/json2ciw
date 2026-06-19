"""Tests related to API."""

import json2ciw


def test_public_api_is_expected():
    """Test all expection functions/classes are in __all__."""
    expected = {
        "load_model_file",
        "load_call_centre_model",
        "load_jackson_network_model",
        "load_three_node_network_model",
        "load_six_node_ucc_model",
        "load_renege_call_model",
        "load_mm1_renege_model",
        "CiwConverter",
        "multiple_replications",
        "summarise_results",
        "tidy_to_wide_format",
        "create_user_filtered_hist",
        "ProcessModel",
        "render_simulation_app",
    }
    assert set(json2ciw.__all__) == expected
