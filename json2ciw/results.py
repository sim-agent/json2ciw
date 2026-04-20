import pandas as pd
import plotly.graph_objects as go


def summarise_results(
    df_reps: pd.DataFrame,
    metric_name_map: dict[str, str] | None = None,
    include_resource_in_colname: bool = True,
) -> pd.DataFrame:
    """
    Aggregate replication results and transpose so metrics are rows
    and activity names are columns.

    Parameters
    ----------
    df_reps : pd.DataFrame
        Raw tidy-format replication results from multiple_replications().
    metric_name_map : dict or None, optional
        Dictionary mapping internal metric names to friendly names.
        If None, default friendly names are used. Pass {} to keep original names.
    include_resource_in_colname : bool, default True
        If True, column headers include both activity and resource name.
    """
    DEFAULT_METRICS = {
        "mean_n_service": "Mean completed services",
        "mean_wait": "Mean waiting time",
        "mean_service": "Mean service time",
        "mean_utilisation": "Mean utilisation",
        "mean_Lq": "Mean queue length",
        "mean_n_renege": "Mean reneges",
        "mean_renege_rate": "Mean reneging rate",
        "mean_wait_renege": "Mean reneging wait",
        "mean_wait_all": "Mean wait (all completed)",
    }

    if metric_name_map is None:
        metric_name_map = DEFAULT_METRICS

    agg_spec = {
        "mean_n_service": ("n_service", "mean"),
        "mean_wait": ("mean_wait", "mean"),
        "mean_service": ("mean_service", "mean"),
        "mean_utilisation": ("utilisation", "mean"),
        "mean_Lq": ("mean_Lq", "mean"),
    }

    optional_metrics = {
        "mean_n_renege": ("n_renege", "mean"),
        "mean_renege_rate": ("renege_rate", "mean"),
        "mean_wait_renege": ("mean_wait_renege", "mean"),
        "mean_wait_all": ("mean_wait_all", "mean"),
    }

    for out_name, spec in optional_metrics.items():
        source_col = spec[0]
        if source_col in df_reps.columns:
            agg_spec[out_name] = spec

    summary = (
        df_reps.groupby(["activity_name", "resource_name"])
        .agg(**agg_spec)
        .reset_index()
    )

    if include_resource_in_colname:
        summary["activity"] = (
            summary["activity_name"] + " (" + summary["resource_name"] + ")"
        )
    else:
        summary["activity"] = summary["activity_name"]

    metric_cols = ["activity"] + list(agg_spec.keys())
    summary = summary[metric_cols]

    summary = summary.set_index("activity").T
    summary.index.name = "Metric"

    if metric_name_map:
        summary = summary.rename(index=metric_name_map)

    return summary.reset_index()


def tidy_to_wide_format(
    df_reps: pd.DataFrame,
    include_resource_in_colname: bool = False,
) -> pd.DataFrame:
    """
    Return replication results in wide format:
    one row per replication, one column per (metric, activity[/resource]).

    Parameters
    ----------
    df_reps : pd.DataFrame
        Tidy replication results from multiple_replications().
    include_resource_in_colname : bool, default False
        If True, wide-format columns include resource names as well.
    """
    if include_resource_in_colname:
        activity = df_reps["activity_name"] + " (" + df_reps["resource_name"] + ")"
    else:
        activity = df_reps["activity_name"]

    df_reps = df_reps.assign(activity=activity)

    metric_cols = [
        "n_service",
        "mean_wait",
        "mean_service",
        "utilisation",
        "mean_Lq",
    ]

    optional_cols = [
        "n_renege",
        "renege_rate",
        "mean_wait_renege",
        "mean_wait_all",
    ]
    metric_cols.extend([c for c in optional_cols if c in df_reps.columns])

    df_metrics = df_reps[["rep", "activity"] + metric_cols]

    wide = (
        df_metrics
        .set_index(["rep", "activity"])
        .unstack("activity")
    )

    wide.columns = [f"{metric} [{activity}]" for metric, activity in wide.columns]

    wide = wide.reset_index().set_index("rep")

    return wide


def create_user_filtered_hist(results: pd.DataFrame) -> go.Figure:
    """
    Create a Plotly histogram with a dropdown that lets the user
    choose which metric to display.

    Parameters
    ----------
    results : pd.DataFrame
        Wide-format results with one row per replication and one
        column per KPI.

    Returns
    -------
    plotly.graph_objects.Figure
        Interactive histogram figure.
    """
    fig = go.Figure()

    first_col = results.columns[0]
    fig.add_trace(go.Histogram(x=results[first_col].dropna()))

    buttons = []
    for col in results.columns:
        buttons.append(
            dict(
                method="restyle",
                label=col,
                args=[{"x": [results[col].dropna()], "type": "histogram"}, [0]],
            )
        )

    fig.update_layout(
        showlegend=False,
        updatemenus=[
            dict(
                buttons=buttons,
                direction="down",
                showactive=True,
                x=0.25,
                y=1.1,
                xanchor="right",
                yanchor="bottom",
            )
        ],
        annotations=[
            dict(
                text="Performance measure",
                x=0,
                xref="paper",
                y=1.25,
                yref="paper",
                align="left",
                showarrow=False,
            )
        ],
    )

    return fig
