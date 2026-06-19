"""Create a Streamlit user interface."""

from typing import Any

import ciw
import pandas as pd
import streamlit as st

from .engine import CiwConverter, multiple_replications
from .results import (
    create_user_filtered_hist,
    summarise_results,
    tidy_to_wide_format,
)
from .schema import ProcessModel


def _render_distribution_ui(
    dist: Any,
    node_name: str,
    dist_type: str,
) -> Any | None:
    """Render sidebar controls based on included distributions.

    Parameters
    ----------
    dist : Any
        Ciw distribution object.
    node_name : str
        Node name used in widget keys.
    dist_type : str
        Distribution role label used in widget keys.

    Returns
    -------
    Any or None
        Updated distribution object, or `None` if no distribution is set.

    """
    if dist is None:
        return None

    dist_class = type(dist).__name__

    st.sidebar.markdown(f"*{dist_class}*")

    # Render different inputs based on the distribution class
    if dist_class == "Exponential":
        rate = st.sidebar.number_input(
            "Rate",
            value=float(dist.rate),
            format="%.4f",
            key=f"{dist_type}_rate_{node_name}",
        )
        return type(dist)(rate=rate)

    if dist_class == "Triangular":
        col1, col2, col3 = st.sidebar.columns(3)
        lower = col1.number_input(
            "Lower",
            value=float(dist.lower),
            key=f"{dist_type}_tl_{node_name}",
            min_value=0.0,
        )
        mode = col2.number_input(
            "Mode",
            value=float(dist.mode),
            key=f"{dist_type}_tm_{node_name}",
            min_value=0.0,
        )
        upper = col3.number_input(
            "Upper",
            value=float(dist.upper),
            key=f"{dist_type}_tu_{node_name}",
            min_value=0.0,
        )
        return type(dist)(lower=lower, mode=mode, upper=upper)

    if dist_class == "Uniform":
        col1, col2 = st.sidebar.columns(2)
        lower = col1.number_input(
            "Lower", value=float(dist.lower), key=f"{dist_type}_ul_{node_name}"
        )
        upper = col2.number_input(
            "Upper", value=float(dist.upper), key=f"{dist_type}_uu_{node_name}"
        )
        return type(dist)(lower=lower, upper=upper)

    if dist_class == "Deterministic":
        value = st.sidebar.number_input(
            "Value", value=float(dist.value), key=f"{dist_type}_d_{node_name}"
        )
        return type(dist)(value=value)

    if dist_class == "Lognormal":
        col1, col2 = st.sidebar.columns(2)
        mean = col1.number_input(
            "mean", value=float(dist.mean), key=f"{dist_type}_ul_{node_name}"
        )
        sd = col2.number_input(
            "sd", value=float(dist.sd), key=f"{dist_type}_uu_{node_name}"
        )

        # convert to mu sigma of the underlying normal
        mu, sigma = CiwConverter.normal_moments_from_lognormal(mean, sd)
        return type(dist)(mean=mu, sd=sigma)

    if dist_class == "Normal":
        col1, col2 = st.sidebar.columns(2)
        mean = col1.number_input(
            "mean", value=float(dist.mean), key=f"{dist_type}_ul_{node_name}"
        )
        sd = col2.number_input(
            "sd", value=float(dist.sd), key=f"{dist_type}_uu_{node_name}"
        )
        return type(dist)(mean=mean, sd=sd)

    st.sidebar.warning(f"UI for {dist_class} not implemented. Using defaults.")
    return dist


def render_simulation_app(
    default_params: dict[str, Any],
    model_metadata: dict[str, Any],
    valid_process_model: ProcessModel | None = None,
) -> None:
    """Render the simulation app and run the selected model.

    Parameters
    ----------
    default_params : dict of str to Any
        Default Ciw network parameters.
    model_metadata : dict of str to Any
        Model metadata used to label the interface.
    valid_process_model : ProcessModel or None, optional
        Validated process model passed to the simulation engine, by
        default `None`.

    """
    # --- UI: MAIN HEADER ---
    st.title(model_metadata.get("name", "Discrete Event Simulation Runner"))
    description = model_metadata.get(
        "description",
        "No description provided.",
    )
    st.markdown(f"**Description:** {description}")

    num_nodes = len(default_params["number_of_servers"])

    # Extract node names from JSON metadata if available
    activities = model_metadata.get("activities", [])
    node_names = (
        [act["name"] for act in activities]
        if activities
        else [f"Node {i}" for i in range(num_nodes)]
    )

    # --- UI: PARAMETER MANIPULATION (SIDEBAR) ---
    st.sidebar.header("Resource & Distribution Parameters")
    updated_params = {
        "number_of_servers": [],
        "arrival_distributions": [],
        "service_distributions": [],
        "reneging_time_distributions": [],
        "routing": [],
    }

    for index in range(num_nodes):
        node_name = node_names[index]
        st.sidebar.subheader(f"{node_name}")

        # Extract specific resource name if available in JSON
        resource_name = "Servers"
        if index < len(activities) and "resource" in activities[index]:
            resource_name = activities[index]["resource"]["name"]

        # Resourcing
        servers = st.sidebar.slider(
            f"Number of {resource_name}",
            min_value=1,
            max_value=50,
            value=int(default_params["number_of_servers"][index]),
            key=f"server_{node_name}",
        )
        updated_params["number_of_servers"].append(servers)

        # Arrival Distribution (Conditional Header)
        arr_dist_data = default_params["arrival_distributions"][index]
        if arr_dist_data is not None:
            st.sidebar.markdown("**Arrival Distribution**")
        arr_dist = _render_distribution_ui(arr_dist_data, node_name, "Arrival")
        updated_params["arrival_distributions"].append(arr_dist)

        # Service Distribution (Conditional Header)
        srv_dist_data = default_params["service_distributions"][index]
        if srv_dist_data is not None:
            st.sidebar.markdown("**Service Distribution**")
        srv_dist = _render_distribution_ui(srv_dist_data, node_name, "Service")
        updated_params["service_distributions"].append(srv_dist)

        # Reneging Distribution (Conditional Header)
        renege_dist_data = default_params["reneging_time_distributions"][index]
        if renege_dist_data is not None:
            st.sidebar.markdown("**Renege Distribution**")
        renege_dist = _render_distribution_ui(
            renege_dist_data, node_name, "Renege"
        )
        updated_params["reneging_time_distributions"].append(renege_dist)

        st.sidebar.divider()

    # --- UI: MAIN PANEL TABS ---
    tab_settings, tab_routing = st.tabs(["Run Settings", "Routing Logic"])

    with tab_settings:
        st.markdown("### Run Settings")
        # Change 1: Columns side-by-side
        col1, col2, col3 = st.columns(3)
        with col1:
            num_reps = st.number_input(
                "Replications", min_value=1, value=100, step=5
            )
        with col2:
            warmup = st.number_input(
                "Warm-up Time", min_value=0, value=0, step=100
            )
        with col3:
            runtime = st.number_input(
                "Run length", min_value=1, value=1440, step=100
            )

    with tab_routing:
        # Change 3: Routing Matrix in its own tab
        st.markdown("### Routing Matrix")
        df_routing = pd.DataFrame(
            default_params["routing"], columns=node_names, index=node_names
        )

        st.write("Edit transition probabilities below:")
        edited_routing = st.data_editor(
            df_routing, key="routing_editor", width="stretch"
        )
        updated_params["routing"] = edited_routing.to_numpy().tolist()

    st.markdown("---")  # Visual separator before the run button

    # --- MAIN PANEL: EXECUTION ---
    if st.button("Run Simulation", type="primary", width="content"):
        with st.spinner(
            f"Running {num_reps} replications of "
            f"{model_metadata.get('name', 'the model')}..."
        ):
            try:
                network = ciw.create_network(**updated_params)

                df_reps_tidy = multiple_replications(
                    network,
                    valid_process_model,
                    warmup=warmup,
                    num_reps=num_reps,
                    runtime=runtime,
                )

                st.success("Simulation complete!")

                st.subheader("Summary Results")
                summary = summarise_results(df_reps_tidy).round(2)
                st.dataframe(summary, width="stretch")

                st.subheader("Histogram of Replications")
                df_reps_wide = tidy_to_wide_format(df_reps_tidy)
                st.plotly_chart(create_user_filtered_hist(df_reps_wide))

                with st.expander("View Detailed Replication Data"):
                    st.dataframe(df_reps_wide, width="stretch")

            except Exception as e:
                st.error(f"Simulation Error: {e!s}")
