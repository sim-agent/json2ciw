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
        Raw tidy format replication results from multiple_replications()
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


def tidy_to_wide_format(
    df_reps: pd.DataFrame,
) -> pd.DataFrame:
    """
    Return replication results in wide format:
    one row per replication, one column per (metric, activity[/resource]).
    
    Parameters
    ----------
    df_reps : pd.DataFrame
        Tidy replication results from multiple_replications(), with
        columns like: rep, activity_name, resource_name,
        arrivals, mean_wait, mean_service, utilisation, mean_Lq.
    """
   
    df_reps = df_reps.assign(activity=df_reps["activity_name"])

    # Subset metrics you care about
    metric_cols = ["arrivals", "mean_wait", "mean_service", "utilisation", "mean_Lq"]
    df_metrics = df_reps[["rep", "activity"] + metric_cols]

    # Pivot to wide: (activity, metric) -> columns
    wide = (
        df_metrics
        .set_index(["rep", "activity"])
        .unstack("activity")
    )

    # Flatten MultiIndex columns to strings like "Mean wait [Call triage (Operators)]"
    wide.columns = [f"{metric} [{activity}]" for metric, activity in wide.columns]

    # Bring rep back as single index
    wide = wide.reset_index()
    wide = wide.set_index("rep")

    return wide


def create_user_filtered_hist(results):
    '''
    Create a plotly histogram that includes a drop down list that allows a user
    to select which KPI is displayed as a histogram
    
    Params:
    -------
    results: pd.Dataframe
        rows = replications, cols = KPIs
        
    Returns:
    -------
    plotly.figure
    
    Sources:
    ------
    The code in this function was parly adapted from two sources:
    1. https://stackoverflow.com/questions/59406167/plotly-how-to-filter-a-pandas-dataframe-using-a-dropdown-menu
    
    Thanks and credit to `vestland` the author of the reponse.
    
    2. https://plotly.com/python/dropdowns/
    '''
    # create a figure
    fig = go.Figure()

    # set up a trace
    fig.add_trace(go.Histogram(x=results[results.columns[0]]))

    buttons = []

    # create list of drop down items - KPIs
    # the params in the code would need to vary depending on the type of chart.
    # The histogram will show the first KPI by default
    for col in results.columns:
        buttons.append(dict(method='restyle',
                            label=col,
                            visible=True,
                            args=[{'x':[results[col]],
                                   'type':'histogram'}, [0]],
                            )
                      )


    # create update menu and parameters
    updatemenu = []
    your_menu = dict()
    updatemenu.append(your_menu)

    updatemenu[0]['buttons'] = buttons
    updatemenu[0]['direction'] = 'down'
    updatemenu[0]['showactive'] = True
    updatemenu[0]['x'] = 0.25
    updatemenu[0]['y'] = 1.1
    updatemenu[0]['xanchor'] = 'right'
    updatemenu[0]['yanchor'] = 'bottom'
    #updatemenu[0]['pad'] = {"r": 10, "t": 10}
    
    
    
    # add dropdown menus to the figure
    fig.update_layout(showlegend=False, 
                      updatemenus=updatemenu)
    
    
    # add label for selecting performance measure
    fig.update_layout(
    annotations=[
        dict(text="Performance measure", x=0, xref="paper", y=1.25, 
             yref="paper", align="left", showarrow=False)
    ])
    return fig