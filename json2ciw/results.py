import pandas as pd

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
        Raw replication results from run_replications_general()
    metric_name_map : dict or None, optional
        Dictionary mapping internal metric names to friendly names.
        If None, uses default friendly names. Pass False or {} to keep original names.
    include_resource_in_colname : bool, default True
        If True, column headers include both activity and resource name.
    """
    
    # Default friendly metric names
    DEFAULT_METRICS = {
        "mean_arrivals": "Mean arrivals",
        "mean_wait": "Mean waiting time",
        "mean_service": "Mean service time",
        "mean_utilisation": "Mean utilisation",
        "mean_Lq": "Mean queue length",
    }
    
    # Use default if None, otherwise use provided dict (even if empty)
    if metric_name_map is None:
        metric_name_map = DEFAULT_METRICS
    
    summary = (
        df_reps.groupby(["activity_name", "resource_name"])
        .agg(
            mean_arrivals=("arrivals", "mean"),
            mean_wait=("mean_wait", "mean"),
            mean_service=("mean_service", "mean"),
            mean_utilisation=("utilisation", "mean"),
            mean_Lq=("mean_Lq", "mean"),
        )
        .reset_index()
    )

    if include_resource_in_colname:
        summary["activity"] = summary["activity_name"] + " (" + summary["resource_name"] + ")"
    else:
        summary["activity"] = summary["activity_name"]

    summary = summary[
        ["activity", "mean_arrivals", "mean_wait", "mean_service", "mean_utilisation", "mean_Lq"]
    ]

    # Transpose: metrics as rows, activities as columns
    summary = summary.set_index("activity").T
    summary.index.name = "Metric"

    # Apply metric name mapping
    if metric_name_map:
        summary = summary.rename(index=metric_name_map)

    return summary.reset_index()