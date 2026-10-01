"""Summarise and reshape simulation output for analysis and plotting."""

import pandas as pd
import plotly.graph_objects as go

DEFAULT_METRICS = {
    "mean_n_service": "Mean completed services",
    "mean_n_rejected": "Mean rejected arrivals",
    "mean_wait": "Mean waiting time",
    "mean_service": "Mean service time",
    "mean_utilisation": "Mean utilisation",
    "mean_Lq": "Mean queue length",
    "mean_n_renege": "Mean reneges",
    "mean_renege_rate": "Mean reneging rate",
    "mean_wait_renege": "Mean reneging wait",
    "mean_wait_all": "Mean wait (all customers)",
}

DEFAULT_TRANSFER_METRICS = {
    "mean_n_transfers": "Mean transfers",
    "mean_n_blocked": "Mean blocked transfers",
    "mean_blocking_probability": "Mean blocking probability",
    "mean_blocking_delay": "Mean blocking delay",
    "mean_blocking_delay_given_blocked": (
        "Mean blocking delay (given blocked)"
    ),
}


def summarise_transfer_results(
    df_transfer_reps: pd.DataFrame,
    metric_name_map: dict[str, str] | None = None,
    *,
    include_customer_class: bool = False,
    class_label_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Summarise replication-level transfer blocking results.


    Parameters
    ----------
    df_transfer_reps : pandas.DataFrame
        Tidy-format source-to-destination transfer results returned by
        `multiple_replications()`.
    metric_name_map : dict or None, optional
        Dictionary mapping internal metric names to friendly names.
        If None, default friendly names are used. Pass an empty dictionary
        to keep internal names.
    include_customer_class : bool, default False
        Whether to include customer-class-specific rows. By default, only
        overall transfer results are summarised.
    class_label_map : dict or None, optional
        Optional mapping from internal customer class names to friendly
        display labels.


    Returns
    -------
    pandas.DataFrame
        Summary table with one row per source-to-destination transfer,
        and one column per summary metric.


    """
    if metric_name_map is None:
        metric_name_map = DEFAULT_TRANSFER_METRICS


    # A model without finite queue capacities produces an empty but
    # correctly structured transfer-results DataFrame.
    if df_transfer_reps.empty:
        return pd.DataFrame(
            columns=[
                "Source activity",
                "Destination activity",
                "Mean transfers",
                "Mean blocked transfers",
                "Mean blocking probability",
                "Mean blocking delay",
                "Mean blocking delay (given blocked)",
            ]
        )


    df_summary = df_transfer_reps.copy()


    # Keep the default summary focused on all customers. Class-specific
    # rows can be requested when the model includes customer classes.
    if "measure_scope" in df_summary.columns:
        if include_customer_class:
            df_summary = df_summary[
                df_summary["measure_scope"].isin(
                    ["overall", "customer_class"]
                )
            ].copy()
        else:
            df_summary = df_summary[
                df_summary["measure_scope"] == "overall"
            ].copy()


    # Create a display label only when a class-level breakdown is wanted.
    if include_customer_class:
        if "customer_class" not in df_summary.columns:
            df_summary["customer_class"] = "All"


        if class_label_map:
            df_summary["Customer Class"] = (
                df_summary["customer_class"]
                .map(class_label_map)
                .fillna(df_summary["customer_class"])
            )
        else:
            df_summary["Customer Class"] = df_summary["customer_class"]


        if "measure_scope" in df_summary.columns:
            overall_mask = df_summary["measure_scope"] == "overall"
            df_summary.loc[overall_mask, "Customer Class"] = "Overall"


    # These are replication-level quantities, so take their mean over
    # replications, matching the existing node-level summary functions.
    agg_spec = {
        "mean_n_transfers": ("n_transfers", "mean"),
        "mean_n_blocked": ("n_blocked", "mean"),
        "mean_blocking_probability": (
            "blocking_probability",
            "mean",
        ),
        "mean_blocking_delay": (
            "mean_blocking_delay",
            "mean",
        ),
        "mean_blocking_delay_given_blocked": (
            "mean_blocking_delay_given_blocked",
            "mean",
        ),
    }


    group_cols = [
        "source_activity_name",
        "destination_activity_name",
    ]

    if include_customer_class:
        group_cols.append("Customer Class")


    summary = (
        df_summary.groupby(group_cols)
        .agg(**agg_spec)
        .reset_index()
    )


    summary = summary.rename(
        columns={
            "source_activity_name": "Source activity",
            "destination_activity_name": "Destination activity",
        }
    )


    # Apply friendly metric labels to columns if requested.
    if metric_name_map:
        rename_map = {
            internal: friendly
            for internal, friendly in metric_name_map.items()
            if internal in summary.columns
        }
        summary = summary.rename(columns=rename_map)


    return summary


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
        "mean_n_rejected": ("n_rejected", "mean"),
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
        "mean_n_rejected": ("n_rejected", "mean"),
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

    df_wide = df_reps.copy()

    # Keep this function focused on overall node summaries.
    # If the replication output contains both overall and class-specific
    # rows, filter to the overall rows only.
    if "measure_scope" in df_wide.columns:
        df_wide = df_wide[df_wide["measure_scope"] == "overall"].copy()

    if include_resource_in_colname:
        activity = (
            df_wide["activity_name"] + " (" + df_wide["resource_name"] + ")"
        )
    else:
        activity = df_wide["activity_name"]

    df_wide = df_wide.assign(activity=activity)

    metric_cols = [
        "n_service",
        "mean_wait",
        "mean_service",
        "utilisation",
        "mean_Lq",
    ]

    optional_cols = [
        "n_rejected",
        "n_renege",
        "renege_rate",
        "mean_wait_renege",
        "mean_wait_all",
    ]
    
    metric_cols.extend([c for c in optional_cols if c in df_wide.columns])

    df_metrics = df_wide[["rep", "activity", *metric_cols]]

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

def tidy_to_wide_format_by_class(
    df_reps: pd.DataFrame,
    *,
    customer_class: str | None = None,
    include_overall: bool = False,
    class_label_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Convert tidy replication results to class-specific wide format.

    Parameters
    ----------
    df_reps : pandas.DataFrame
        Tidy-format replication results from multiple_replications().
    customer_class : str or None, optional
        Specific customer class to include. If `None`, all customer
        classes are included.
    include_overall : bool, default False
        Whether to include overall rows alongside class-specific rows.
    class_label_map : dict or None, optional
        Optional mapping from internal customer class names to friendly
        display labels.

    Returns
    -------
    pandas.DataFrame
        Wide-format class-specific replication results with one row per
        replication.

    """
    df_wide = df_reps.copy()

    # Keep this function focused on class-specific summaries.
    # If the replication output contains measure scopes, default to the
    # customer-class rows unless overall rows are explicitly requested.
    if "measure_scope" in df_wide.columns:
        if include_overall:
            df_wide = df_wide[
                df_wide["measure_scope"].isin(["overall", "customer_class"])
            ].copy()
        else:
            df_wide = df_wide[
                df_wide["measure_scope"] == "customer_class"
            ].copy()

    # If there is no customer_class column, fall back to a single "All"
    # label so the function still behaves sensibly on older outputs.
    if "customer_class" not in df_wide.columns:
        df_wide["customer_class"] = "All"

    # Filter to one class if requested.
    if customer_class is not None:
        keep_mask = df_wide["customer_class"] == customer_class
        if include_overall and "measure_scope" in df_wide.columns:
            keep_mask = keep_mask | (df_wide["measure_scope"] == "overall")
        df_wide = df_wide[keep_mask].copy()

    # Optionally map internal class names to display labels.
    if class_label_map:
        df_wide["customer_class_display"] = df_wide["customer_class"].map(
            class_label_map
        ).fillna(df_wide["customer_class"])
    else:
        df_wide["customer_class_display"] = df_wide["customer_class"]

    # If overall rows are included, make the label explicit.
    if "measure_scope" in df_wide.columns:
        overall_mask = df_wide["measure_scope"] == "overall"
        df_wide.loc[overall_mask, "customer_class_display"] = "Overall"

    # Build column labels.
    # If a single class has been selected, keep labels compact and use
    # the activity name only. Otherwise include the customer class in the
    # label to distinguish columns.
    if customer_class is not None:
        df_wide["activity_class"] = df_wide["activity_name"]
    else:
        df_wide["activity_class"] = (
            df_wide["activity_name"]
            + " - "
            + df_wide["customer_class_display"]
        )

    # If overall rows are included together with a single class, mark the
    # overall columns explicitly so they do not collide with class columns.
    if customer_class is not None and include_overall:
        if "measure_scope" in df_wide.columns:
            overall_mask = df_wide["measure_scope"] == "overall"
            df_wide.loc[overall_mask, "activity_class"] = (
                df_wide.loc[overall_mask, "activity_name"] + " - Overall"
            )

    metric_cols = [
        "n_service",
        "mean_wait",
        "mean_service",
        "mean_Lq",
    ]

    # Utilisation is only meaningful for overall rows in the current
    # engine output, since class-specific utilisation is not directly
    # available from Ciw at node level.
    if include_overall and "utilisation" in df_wide.columns:
        if "measure_scope" in df_wide.columns:
            util_source = df_wide[df_wide["measure_scope"] == "overall"]
            if util_source["utilisation"].notna().any():
                metric_cols.append("utilisation")
        else:
            metric_cols.append("utilisation")

    optional_cols = [
        "n_renege",
        "renege_rate",
        "mean_wait_renege",
        "mean_wait_all",
    ]
    metric_cols.extend([c for c in optional_cols if c in df_wide.columns])

    df_metrics = df_wide[["rep", "activity_class", *metric_cols]]

    wide = df_metrics.pivot_table(
        index="rep",
        columns="activity_class",
        values=metric_cols,
        aggfunc="first",
    )

    wide.columns = [
        f"{metric} [{activity_class}]"
        for metric, activity_class in wide.columns
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


def tidy_transfer_to_wide_format(
    df_transfer_reps: pd.DataFrame,
    *,
    include_customer_class: bool = False,
    class_label_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Convert tidy transfer blocking results to wide format.

    Parameters
    ----------
    df_transfer_reps : pandas.DataFrame
        Tidy-format source-to-destination transfer results returned by
        `multiple_replications()`.
    include_customer_class : bool, default False
        Whether to include class-specific results alongside overall
        results. By default, only overall results are included.
    class_label_map : dict or None, optional
        Optional mapping from internal customer class names to friendly
        display labels.

    Returns
    -------
    pandas.DataFrame
        Wide-format transfer results with one row per replication.
        Columns use the format "metric [source -> destination]".
        When customer classes are included, labels also include the class.
        The replication identifier is retained as the index.

    """
    df_wide = df_transfer_reps.copy()

    # Keep all replication identifiers present in the input, even if
    # scope filtering leaves a replication with no transfer rows.
    rep_index = pd.Index(
        sorted(df_wide["rep"].unique()),
        name="rep",
    )

    # Default to overall transfer results. Optionally include the
    # customer-class breakdown alongside the overall rows.
    if "measure_scope" in df_wide.columns:
        scopes = (
            ["overall", "customer_class"]
            if include_customer_class
            else ["overall"]
        )
        df_wide = df_wide[
            df_wide["measure_scope"].isin(scopes)
        ].copy()

    # Models without finite queue capacities return empty transfer
    # results. Also handle inputs emptied by the scope filter.
    if df_wide.empty:
        return pd.DataFrame(index=rep_index)

    # Identify each directed transfer using its source and destination.
    df_wide["transfer"] = (
        df_wide["source_activity_name"]
        + " -> "
        + df_wide["destination_activity_name"]
    )

    # Add customer-class labels only when a breakdown is requested.
    if include_customer_class:
        if "customer_class" not in df_wide.columns:
            df_wide["customer_class"] = "All"

        if class_label_map:
            class_display = (
                df_wide["customer_class"]
                .map(class_label_map)
                .fillna(df_wide["customer_class"])
            )
        else:
            class_display = df_wide["customer_class"].copy()

        # Explicitly distinguish overall rows from class-specific rows.
        if "measure_scope" in df_wide.columns:
            overall_mask = df_wide["measure_scope"] == "overall"
            class_display.loc[overall_mask] = "Overall"

        df_wide["transfer"] = (
            df_wide["transfer"] + " - " + class_display
        )

    metric_cols = [
        "n_transfers",
        "n_blocked",
        "blocking_probability",
        "mean_blocking_delay",
        "mean_blocking_delay_given_blocked",
    ]

    # Reshape without aggregating: duplicate replication/transfer labels
    # indicate an input or display-label collision and should raise.
    # Missing values remain missing rather than being replaced with zero.
    wide = df_wide.pivot(
        index="rep",
        columns="transfer",
        values=metric_cols,
    )

    # Match the flat column naming convention of the node-level helpers.
    wide.columns = [
        f"{metric} [{transfer}]"
        for metric, transfer in wide.columns
    ]

    return wide.reindex(rep_index)