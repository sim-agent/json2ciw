"""Create a Streamlit UI for single- and multi-class Ciw models."""

from typing import Any

import ciw
import pandas as pd
import streamlit as st

from .engine import multiple_replications
from .results import (
    create_user_filtered_hist, 
    summarise_results, 
    summarise_results_by_class,
    tidy_to_wide_format
)
from .schema import ProcessModel


def _widget_key(*parts: str) -> str:
    """Create a stable Streamlit widget key.

    Parameters
    ----------
    *parts : str
        Components that uniquely identify a widget.

    Returns
    -------
    str
        Components concatenated into a single Streamlit key.
    """
    return "__".join(str(part) for part in parts)


def _render_distribution_ui(
    dist: Any | None,
    *,
    location: Any,
    widget_prefix: str,
) -> Any | None:
    """Render an editor for one Ciw distribution.

    Parameters
    ----------
    dist : Any or None
        Ciw distribution object to edit. ``None`` denotes no arrivals or no
        reneging at an activity for the relevant customer class.
    location : Any
        Streamlit container to which widgets should be written, for example
        ``st.sidebar`` or ``st`` within a tab.
    widget_prefix : str
        Unique prefix used to construct all associated Streamlit widget keys.

    Returns
    -------
    Any or None
        A newly constructed Ciw distribution containing the values selected by
        the user, or ``None`` when no distribution is defined.

    Notes
    -----
    This function edits Ciw objects rather than schema distributions because
    ``default_params`` is the representation supplied directly to
    ``ciw.create_network``.
    """
    if dist is None:
        location.caption("No distribution.")
        return None

    dist_class = type(dist).__name__
    location.caption(dist_class)

    if dist_class == "Exponential":
        rate = location.number_input(
            "Rate", min_value=1e-12, value=float(dist.rate), format="%.6f",
            key=_widget_key(widget_prefix, "rate"),
        )
        return ciw.dists.Exponential(rate=rate)

    if dist_class == "Triangular":
        lower_col, mode_col, upper_col = location.columns(3)
        lower = lower_col.number_input("Lower", min_value=0.0, value=float(dist.lower), key=_widget_key(widget_prefix, "lower"))
        mode = mode_col.number_input("Mode", min_value=0.0, value=float(dist.mode), key=_widget_key(widget_prefix, "mode"))
        upper = upper_col.number_input("Upper", min_value=0.0, value=float(dist.upper), key=_widget_key(widget_prefix, "upper"))
        if not lower <= mode <= upper:
            location.error("Triangular parameters must satisfy lower ≤ mode ≤ upper.")
        return ciw.dists.Triangular(lower=lower, mode=mode, upper=upper)

    if dist_class == "Uniform":
        lower_col, upper_col = location.columns(2)
        lower = lower_col.number_input("Lower", min_value=0.0, value=float(dist.lower), key=_widget_key(widget_prefix, "lower"))
        upper = upper_col.number_input("Upper", min_value=0.0, value=float(dist.upper), key=_widget_key(widget_prefix, "upper"))
        if lower > upper:
            location.error("Uniform lower bound must not exceed upper bound.")
        return ciw.dists.Uniform(lower=lower, upper=upper)

    if dist_class == "Deterministic":
        value = location.number_input("Value", min_value=0.0, value=float(dist.value), key=_widget_key(widget_prefix, "value"))
        return ciw.dists.Deterministic(value=value)

    if dist_class == "Gamma":
        shape_col, scale_col = location.columns(2)
        shape = shape_col.number_input("Shape", min_value=1e-12, value=float(dist.shape), key=_widget_key(widget_prefix, "shape"))
        scale = scale_col.number_input("Scale", min_value=1e-12, value=float(dist.scale), key=_widget_key(widget_prefix, "scale"))
        return ciw.dists.Gamma(shape=shape, scale=scale)

    if dist_class in {"Normal", "Lognormal"}:
        mean_col, sd_col = location.columns(2)
        mean_label = "μ (underlying normal)" if dist_class == "Lognormal" else "Mean"
        mean = mean_col.number_input(mean_label, value=float(dist.mean), key=_widget_key(widget_prefix, "mean"))
        sd = sd_col.number_input("SD", min_value=1e-12, value=float(dist.sd), key=_widget_key(widget_prefix, "sd"))
        if dist_class == "Lognormal":
            location.caption("Ciw stores lognormal parameters as μ and σ of the underlying normal.")
            return ciw.dists.Lognormal(mean=mean, sd=sd)
        return ciw.dists.Normal(mean=mean, sd=sd)

    location.warning(f"No editor for {dist_class}; using its original value.")
    return dist


def _class_labels(
    model_metadata: dict[str, Any],
    default_params: dict[str, Any],
) -> dict[str, str]:
    """Map customer-class names to display labels in Ciw parameter order.

    Parameters
    ----------
    model_metadata : dict of str to Any
        Serialised model metadata, including optional ``customer_classes``
        entries with ``name`` and ``label`` fields.
    default_params : dict of str to Any
        Ciw network arguments produced by ``CiwConverter.generate_params``.

    Returns
    -------
    dict of str to str
        Mapping of machine-readable class names to display labels. An empty
        mapping indicates a single-class model.
    """
    arrivals = default_params["arrival_distributions"]
    class_names = list(arrivals) if isinstance(arrivals, dict) else []
    labels_from_json = {
        customer_class["name"]: customer_class.get("label") or customer_class["name"]
        for customer_class in model_metadata.get("customer_classes", [])
    }
    return {name: labels_from_json.get(name, name) for name in class_names}


def _routing_frame_from_model(
    process_model: ProcessModel,
    node_names: list[str],
    customer_class: str | None = None,
) -> pd.DataFrame:
    """Return an editable routing table with an explicit Exit column.

    Parameters
    ----------
    process_model : ProcessModel
        Validated source model used to initialise the routing editor.
    node_names : list of str
        Activity names in the Ciw node order.
    customer_class : str or None, optional
        Customer class for which to retrieve a routing matrix. Use ``None``
        for a single-class model.

    Returns
    -------
    pandas.DataFrame
        Routing probabilities with source activities as rows and internal
        destinations plus ``Exit`` as columns.

    Notes
    -----
    Ciw may normalise list-based routing matrices into ``TransitionMatrix``
    objects. Reading from ``ProcessModel`` avoids depending on Ciw's internal
    object representation and preserves explicit Exit probabilities.
    """
    routing = process_model.get_routing_matrix_df()
    if customer_class is not None:
        routing = routing.xs(customer_class, level="Customer Class")
    return routing.loc[node_names, [*node_names, "Exit"]].astype(float).copy()


def _validate_and_extract_routing(
    edited: pd.DataFrame,
    node_names: list[str],
    scope_label: str,
) -> tuple[list[list[float]] | None, list[str]]:
    """Validate a complete UI routing table and make a Ciw matrix.

    Parameters
    ----------
    edited : pandas.DataFrame
        Editable routing table containing all internal destination columns and
        an ``Exit`` column.
    node_names : list of str
        Internal activity names, in Ciw node order.
    scope_label : str
        Human-readable class or routing label used in validation messages.

    Returns
    -------
    matrix : list of list of float or None
        Internal-node routing matrix ready for Ciw. ``None`` is returned if
        validation fails.
    errors : list of str
        User-facing validation messages. Empty when the matrix is valid.

    Notes
    -----
    Ciw does not receive an explicit Exit column; its residual row probability
    represents exit. The UI retains that column to make rows auditable and to
    enforce a total probability of exactly one.
    """
    numeric = edited.apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any():
        return None, [f"{scope_label}: all routing entries must be numeric."]

    errors: list[str] = []
    for source, row in numeric.iterrows():
        probabilities = row.to_numpy(dtype=float)
        total = probabilities.sum()
        if (probabilities < -1e-9).any() or (probabilities > 1.0 + 1e-9).any():
            errors.append(f"{scope_label}, {source}: each probability must be between 0 and 1.")
        if abs(total - 1.0) > 1e-9:
            errors.append(f"{scope_label}, {source}: row total is {total:.6g}; it must equal 1.")

    if errors:
        return None, errors
    return numeric.loc[node_names, node_names].to_numpy(dtype=float).tolist(), []


def _render_node_controls(
    default_params: dict[str, Any],
    activities: list[dict[str, Any]],
    node_names: list[str],
    class_labels: dict[str, str],
) -> dict[str, Any]:
    """Render resource and distribution controls.

    Parameters
    ----------
    default_params : dict of str to Any
        Baseline Ciw network arguments generated by the converter.
    activities : list of dict of str to Any
        Serialised activity metadata used to label resources.
    node_names : list of str
        Activity names in Ciw node order.
    class_labels : dict of str to str
        Customer-class names and their display labels. Empty for a single-class
        model.

    Returns
    -------
    dict of str to Any
        Fresh Ciw arguments containing resource and distribution values chosen
        by the user. Routing is added separately by the routing tab.
    """
    is_multiclass = bool(class_labels)
    has_reneging = "reneging_time_distributions" in default_params
    updated_params: dict[str, Any] = {
        "number_of_servers": [],
        "arrival_distributions": {} if is_multiclass else [],
        "service_distributions": {} if is_multiclass else [],
    }
    if has_reneging:
        updated_params["reneging_time_distributions"] = {} if is_multiclass else []

    if is_multiclass:
        for class_name in class_labels:
            updated_params["arrival_distributions"][class_name] = []
            updated_params["service_distributions"][class_name] = []
            if has_reneging:
                updated_params["reneging_time_distributions"][class_name] = []

    distribution_roles = (
        ("arrival", "arrival_distributions", "Arrival distribution"),
        ("service", "service_distributions", "Service distribution"),
        ("renege", "reneging_time_distributions", "Reneging distribution"),
    )
    st.sidebar.header("Resources and distributions")
    st.sidebar.caption("Resources are shared. Distribution values are class-specific in multi-class models.")

    for index, node_name in enumerate(node_names):
        activity = activities[index] if index < len(activities) else {}
        resource_name = activity.get("resource", {}).get("name", "Servers")
        st.sidebar.subheader(node_name)
        servers = st.sidebar.number_input(
            f"Number of {resource_name}", min_value=1,
            value=int(default_params["number_of_servers"][index]), step=1,
            key=_widget_key("servers", node_name),
        )
        updated_params["number_of_servers"].append(int(servers))

        if not is_multiclass:
            for role, parameter_name, heading in distribution_roles:
                if parameter_name in default_params:
                    st.sidebar.markdown(f"**{heading}**")
                    updated_params[parameter_name].append(_render_distribution_ui(
                        default_params[parameter_name][index], location=st.sidebar,
                        widget_prefix=_widget_key(node_name, role),
                    ))
            st.sidebar.divider()
            continue

        class_tabs = st.sidebar.tabs(list(class_labels.values()))
        for (class_name, _), class_tab in zip(class_labels.items(), class_tabs, strict=True):
            with class_tab:
                for role, parameter_name, heading in distribution_roles:
                    if parameter_name in default_params:
                        st.markdown(f"**{heading}**")
                        updated_params[parameter_name][class_name].append(_render_distribution_ui(
                            default_params[parameter_name][class_name][index], location=st,
                            widget_prefix=_widget_key(node_name, class_name, role),
                        ))
        st.sidebar.divider()

    return updated_params


def _model_for_results(
    process_model: ProcessModel,
    number_of_servers: list[int],
) -> ProcessModel:
    """Copy result metadata and apply edited resource capacities.

    Parameters
    ----------
    process_model : ProcessModel
        Original validated model.
    number_of_servers : list of int
        User-selected capacities in activity order.

    Returns
    -------
    ProcessModel
        Deep copy of the model whose resource capacities match the Ciw network
        being run. This ensures result tables display the used capacities.
    """
    run_model = process_model.model_copy(deep=True)
    for activity, capacity in zip(run_model.activities, number_of_servers, strict=True):
        activity.resource.capacity = capacity
    return run_model


def render_simulation_app(
    default_params: dict[str, Any],
    model_metadata: dict[str, Any],
    valid_process_model: ProcessModel | None = None,
) -> None:
    """Render an editable Streamlit simulation app and run Ciw.

    Parameters
    ----------
    default_params : dict of str to Any
        Baseline arguments from ``CiwConverter.generate_params``. Single-class
        models use list-based Ciw arguments; multi-class models use dictionaries
        keyed by customer-class name.
    model_metadata : dict of str to Any
        Serialised model metadata used for titles, descriptions, activity names,
        resource labels, and customer-class labels.
    valid_process_model : ProcessModel or None, optional
        Validated model used to construct initial routing tables and to label
        simulation results. It is required for this UI.

    Returns
    -------
    None
        The function writes all interface elements and results to Streamlit.

    Notes
    -----
    A click on ``Run simulation`` creates a new Ciw network from the current
    user-edited ``updated_params``. Thus routing, resource, and distribution
    changes apply to that run without mutating the baseline ProcessModel.
    """
    st.title(model_metadata.get("name", "Discrete Event Simulation Runner"))
    if description := model_metadata.get("description"):
        st.markdown(f"**Description:** {description}")

    if valid_process_model is None:
        st.error("A validated ProcessModel is required to render this application.")
        return

    activities = model_metadata.get("activities", [])
    num_nodes = len(default_params["number_of_servers"])
    node_names = [activity["name"] for activity in activities] or [f"Node {index + 1}" for index in range(num_nodes)]
    if len(node_names) != num_nodes:
        st.error("Metadata activities do not match the generated Ciw network.")
        return

    class_labels = _class_labels(model_metadata, default_params)
    if class_labels:
        st.info("Multi-class model: class-specific arrival, service, reneging, and routing parameters are enabled.")
    updated_params = _render_node_controls(default_params, activities, node_names, class_labels)

    settings_tab, routing_tab = st.tabs(["Run settings", "Routing"])
    with settings_tab:
        reps_col, warmup_col, runtime_col = st.columns(3)
        num_reps = reps_col.number_input("Replications", min_value=1, value=100, step=5)
        warmup = warmup_col.number_input("Warm-up time", min_value=0.0, value=0.0, step=100.0)
        runtime = runtime_col.number_input("Run length", min_value=1.0, value=1440.0, step=100.0)
        if warmup >= runtime:
            st.warning("Warm-up time must be smaller than run length.")

    routing_errors: list[str] = []
    with routing_tab:
        st.markdown("Edit complete routing rows, including **Exit**. Every row must sum to 1.")
        if class_labels:
            class_tabs = st.tabs(list(class_labels.values()))
            routing: dict[str, list[list[float]]] = {}
            for (class_name, class_label), class_tab in zip(class_labels.items(), class_tabs, strict=True):
                with class_tab:
                    edited = st.data_editor(
                        _routing_frame_from_model(valid_process_model, node_names, customer_class=class_name),
                        key=_widget_key("routing", class_name), width="stretch",
                    )
                    matrix, errors = _validate_and_extract_routing(edited, node_names, class_label)
                    routing_errors.extend(errors)
                    if matrix is not None:
                        routing[class_name] = matrix
            if len(routing) == len(class_labels):
                updated_params["routing"] = routing
        else:
            edited = st.data_editor(
                _routing_frame_from_model(valid_process_model, node_names),
                key="routing", width="stretch",
            )
            matrix, routing_errors = _validate_and_extract_routing(edited, node_names, "Routing")
            if matrix is not None:
                updated_params["routing"] = matrix

    if not st.button("Run simulation", type="primary"):
        return
    if warmup >= runtime:
        st.error("Warm-up time must be smaller than run length.")
        return
    if routing_errors:
        for error in routing_errors:
            st.error(error)
        return
    if "routing" not in updated_params:
        st.error("Correct the routing matrix before running the simulation.")
        return

    run_model = _model_for_results(valid_process_model, updated_params["number_of_servers"])
    with st.spinner(f"Running {num_reps} replications of {model_metadata.get('name', 'the model')}…"):
        try:
            network = ciw.create_network(**updated_params)
            tidy = multiple_replications(
                network, run_model, warmup=float(warmup),
                num_reps=int(num_reps), runtime=float(runtime),
            )
        except Exception as error:
            st.exception(error)
            return

    # st.success("Simulation complete.")
    # st.subheader("Summary results")
    # st.dataframe(summarise_results(tidy).round(2), width="stretch")
    # st.subheader("Histogram of replications")
    # wide = tidy_to_wide_format(tidy)
    # st.plotly_chart(create_user_filtered_hist(wide), width="stretch")
    # with st.expander("Detailed replication data"):
    #     st.dataframe(wide, width="stretch")
    st.success("Simulation complete.")

    is_multiclass = bool(run_model.customer_classes)

    if is_multiclass:
        overall_tab, by_class_tab, histogram_tab, detail_tab = st.tabs(
            [
                "Overall summary",
                "By customer class",
                "Replication distribution",
                "Detailed data",
            ]
        )
    else:
        overall_tab, histogram_tab, detail_tab = st.tabs(
            [
                "Overall summary",
                "Replication distribution",
                "Detailed data",
            ]
        )

    with overall_tab:
        st.subheader("Overall summary")
        overall_summary = summarise_results(tidy).round(2)
        st.dataframe(overall_summary, width="stretch")

    if is_multiclass:
        class_label_map = {
            customer_class.name: (
                customer_class.label or customer_class.name
            )
            for customer_class in run_model.customer_classes
        }

        with by_class_tab:
            st.subheader("Results by customer class")
            st.caption(
                "Utilisation is not shown here because it is measured at "
                "the shared activity/resource level, not separately by "
                "customer class."
            )

            class_summary = summarise_results_by_class(
                tidy,
                include_overall=False,
                class_label_map=class_label_map,
            ).round(2)

            st.dataframe(
                class_summary,
                width="stretch",
                hide_index=True,
            )

    with histogram_tab:
        st.subheader("Histogram of replications")
        wide = tidy_to_wide_format(tidy)
        st.plotly_chart(
            create_user_filtered_hist(wide),
            width="stretch",
        )

    with detail_tab:
        st.subheader("Detailed replication data")
        st.dataframe(wide, width="stretch")
