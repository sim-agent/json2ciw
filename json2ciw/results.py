"""Summarise and reshape simulation output for analysis and plotting."""

import pandas as pd
import plotly.graph_objects as go

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


def summarise_results(
    df_reps: pd.DataFrame,
    metric_name_map: dict[str, str] | None = None,
    *,
    include_resource_in_colname: bool = True,
) -> pd.DataFrame:
    """Summarise replication results by activity.

    Parameters
    ----------
    df_reps : pandas.DataFrame
        Tidy-format replication results from multiple_replications().
    metric_name_map : dict or None, optional
        Dictionary mapping internal metric names to friendly names.
        If None, default friendly names are used. Pass empty dictionary to
        keep original names.
    include_resource_in_colname : bool, default True
        Whether to include resource names in output column labels.

    Returns
    -------
    pandas.DataFrame
        Summary table with metrics as rows and activities as columns.

    """
    if metric_name_map is None:
        metric_name_map = DEFAULT_METRICS

    # Keep this function focused on overall node summaries.
    # If the replication output contains both overall and class-specific
    # rows, filter to the overall rows only.
    if "measure_scope" in df_reps.columns:
        df_reps = df_reps[df_reps["measure_scope"] == "overall"].copy()

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

    metric_cols = ["activity", *list(agg_spec.keys())]
    summary = summary[metric_cols]

    summary = summary.set_index("activity").T
    summary.index.name = "Metric"

    if metric_name_map:
        summary = summary.rename(index=metric_name_map)

    return summary.reset_index()


def summarise_results_by_class(
    df_reps: pd.DataFrame,
    metric_name_map: dict[str, str] | None = None,
    *,
    include_overall: bool = False,
    class_label_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Summarise replication results by activity and customer class.

    Parameters
    ----------
    df_reps : pandas.DataFrame
        Tidy-format replication results from multiple_replications().
    metric_name_map : dict or None, optional
        Dictionary mapping internal metric names to friendly names.
        If None, default friendly names are used. Pass empty dictionary to
        keep original names.
    include_overall : bool, default False
        Whether to include overall rows alongside class-specific rows.
    class_label_map : dict or None, optional
        Optional mapping from internal customer class names to friendly
        display labels.

    Returns
    -------
    pandas.DataFrame
        Summary table with one row per activity and customer class, and
        one column per metric.

    """
    if metric_name_map is None:
        metric_name_map = DEFAULT_METRICS

    df_summary = df_reps.copy()

    # This function is intended for customer-class breakdowns.
    # If the replication output contains measure scopes, default to the
    # class-specific rows unless overall rows are explicitly requested.
    if "measure_scope" in df_summary.columns:
        if include_overall:
            df_summary = df_summary[
                df_summary["measure_scope"].isin(["overall", "customer_class"])
            ].copy()
        else:
            df_summary = df_summary[
                df_summary["measure_scope"] == "customer_class"
            ].copy()

    # If there is no customer_class column, fall back to a single "All"
    # label so the function still behaves sensibly on older outputs.
    if "customer_class" not in df_summary.columns:
        df_summary["customer_class"] = "All"

    # Optionally map internal class names to display labels.
    if class_label_map:
        df_summary["Customer Class"] = df_summary["customer_class"].map(
            class_label_map
        ).fillna(df_summary["customer_class"])
    else:
        df_summary["Customer Class"] = df_summary["customer_class"]

    # If overall rows are included, make the label explicit.
    if "measure_scope" in df_summary.columns:
        overall_mask = df_summary["measure_scope"] == "overall"
        df_summary.loc[overall_mask, "Customer Class"] = "Overall"

    agg_spec = {
        "mean_n_service": ("n_service", "mean"),
        "mean_wait": ("mean_wait", "mean"),
        "mean_service": ("mean_service", "mean"),
        "mean_Lq": ("mean_Lq", "mean"),
    }

    # Utilisation is only meaningful on overall rows in the engine
    # output, since class-specific utilisation is not directly available
    # from Ciw at node level.
    if include_overall and "utilisation" in df_summary.columns:
        if "measure_scope" in df_summary.columns:
            util_source = df_summary[df_summary["measure_scope"] == "overall"]
            has_overall_util = (
                "utilisation" in util_source.columns
                and util_source["utilisation"].notna().any()
            )
            if has_overall_util:
                agg_spec["mean_utilisation"] = ("utilisation", "mean")
        else:
            agg_spec["mean_utilisation"] = ("utilisation", "mean")

    optional_metrics = {
        "mean_n_renege": ("n_renege", "mean"),
        "mean_renege_rate": ("renege_rate", "mean"),
        "mean_wait_renege": ("mean_wait_renege", "mean"),
        "mean_wait_all": ("mean_wait_all", "mean"),
    }

    for out_name, spec in optional_metrics.items():
        source_col = spec[0]
        if source_col in df_summary.columns:
            agg_spec[out_name] = spec

    summary = (
        df_summary.groupby(["activity_name", "Customer Class"])
        .agg(**agg_spec)
        .reset_index()
    )

    # Rename activity column for display and drop resource name from the
    # class breakdown summary.
    summary = summary.rename(columns={"activity_name": "Activity"})

    # Apply friendly metric labels to columns if provided.
    if metric_name_map:
        rename_map = {
            internal: friendly
            for internal, friendly in metric_name_map.items()
            if internal in summary.columns
        }
        summary = summary.rename(columns=rename_map)

    return summary


def tidy_to_wide_format(
    df_reps: pd.DataFrame,
    *,
    include_resource_in_colname: bool = False,
) -> pd.DataFrame:
    """Convert tidy replication results to wide format.

    Parameters
    ----------
    df_reps : pandas.DataFrame
        Tidy-format replication results from multiple_replications().
    include_resource_in_colname : bool, default False
        Whether to include resource names in output column labels.

    Returns
    -------
    pandas.DataFrame
        Wide-format replication results with one row per replication.

    """
    if include_resource_in_colname:
        activity = (
            df_reps["activity_name"] + " (" + df_reps["resource_name"] + ")"
        )
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

    df_metrics = df_reps[["rep", "activity", *metric_cols]]

    wide = df_metrics.pivot_table(
        index="rep",
        columns="activity",
        values=metric_cols,
        aggfunc="first",
    )

    wide.columns = [
        f"{metric} [{activity}]" for metric, activity in wide.columns
    ]

    return wide


def create_user_filtered_hist(results: pd.DataFrame) -> go.Figure:
    """Create an interactive histogram for selected result columns.

    Parameters
    ----------
    results : pandas.DataFrame
        Wide-format replication results with one column per measure.

    Returns
    -------
    plotly.graph_objects.Figure
        Histogram figure with a metric selection dropdown.

    """
    fig = go.Figure()

    first_col = results.columns[0]
    fig.add_trace(go.Histogram(x=results[first_col].dropna()))

    buttons = [
        {
            "method": "restyle",
            "label": col,
            "args": [
                {"x": [results[col].dropna()], "type": "histogram"},
                [0],
            ],
        }
        for col in results.columns
    ]

    fig.update_layout(
        showlegend=False,
        updatemenus=[
            {
                "buttons": buttons,
                "direction": "down",
                "showactive": True,
                "x": 0.25,
                "y": 1.1,
                "xanchor": "right",
                "yanchor": "bottom",
            }
        ],
        annotations=[
            {
                "text": "Performance measure",
                "x": 0,
                "xref": "paper",
                "y": 1.25,
                "yref": "paper",
                "align": "left",
                "showarrow": False,
            }
        ],
    )

    return fig
