"""Smoke tests for json2ciw."""

import ciw
import pandas as pd
from plotly.graph_objects import Figure

from json2ciw.datasets import (
    load_call_centre_model,
)
from json2ciw.engine import CiwConverter, multiple_replications
from json2ciw.results import (
    create_user_filtered_hist,
    summarise_results,
    tidy_to_wide_format,
)
from json2ciw.schema import ProcessModel


def test_example_model_loads_and_validates():
    """Smoke test that an example model loads and validates."""
    # Load raw JSON-like model specification.
    raw = load_call_centre_model()
    # Construct a ProcessModel to trigger Pydantic validation.
    model = ProcessModel(**raw)

    # Basic structural checks: we got data and non-empty model elements.
    assert isinstance(raw, dict)
    assert model.activities
    assert model.transitions


def test_can_build_network_and_run_tiny_simulation():
    """Smoke test that a tiny simulation run completes."""
    # Reuse the call centre example as a canonical test model.
    raw = load_call_centre_model()
    model = ProcessModel(**raw)

    # Convert high-level model into Ciw network parameters.
    params = CiwConverter(model).generate_params()
    network = ciw.create_network(**params)

    # Run a very small, single-replication experiment to keep tests fast.
    results = multiple_replications(
        network=network,
        process_model=model,
        num_reps=1,
        runtime=10,
        warmup=0,
        n_jobs=1,
    )

    # Ensure we get a non-empty DataFrame of node-level KPIs.
    assert isinstance(results, pd.DataFrame)
    assert not results.empty


def test_results_helpers_run():
    """Smoke test that result helper functions execute without error."""
    # Run the same tiny experiment as input to the helper functions.
    raw = load_call_centre_model()
    model = ProcessModel(**raw)
    params = CiwConverter(model).generate_params()
    network = ciw.create_network(**params)

    results = multiple_replications(
        network=network,
        process_model=model,
        num_reps=1,
        runtime=10,
        warmup=0,
        n_jobs=1,
    )

    # summarise_results: aggregate across replications and nodes.
    summary = summarise_results(results)
    # tidy_to_wide_format: reshape into wide per-replication format.
    wide = tidy_to_wide_format(results)
    # create_user_filtered_hist: build a Plotly histogram figure.
    fig = create_user_filtered_hist(wide)

    # Minimal sanity checks that outputs are non-empty and well-formed.
    assert isinstance(summary, pd.DataFrame)
    assert not summary.empty

    assert isinstance(wide, pd.DataFrame)
    assert not wide.empty

    assert isinstance(fig, Figure)
    assert len(fig.data) >= 1
