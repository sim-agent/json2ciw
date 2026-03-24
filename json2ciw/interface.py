"""
Convert a valid JSON and Ciw network model to a streamlit user interface
"""

import streamlit as st
import pandas as pd
import ciw
from .engine import multiple_replications
from .results import summarise_results

def _render_distribution_ui(dist, node_name, dist_type):
    """Dynamically generates Streamlit UI inputs based on the ciw distribution type."""
    if dist is None:
        return None
    
    dist_class = type(dist).__name__
    
    # Render different inputs based on the distribution class
    if dist_class == "Exponential":
        rate = st.sidebar.number_input(
            "Rate", value=float(dist.rate), format="%.4f", key=f"{dist_type}_rate_{node_name}"
        )
        return type(dist)(rate=rate)
        
    elif dist_class == "Triangular":
        col1, col2, col3 = st.sidebar.columns(3)
        lower = col1.number_input("Lower", value=float(dist.lower), key=f"{dist_type}_tl_{node_name}")
        mode = col2.number_input("Mode", value=float(dist.mode), key=f"{dist_type}_tm_{node_name}")
        upper = col3.number_input("Upper", value=float(dist.upper), key=f"{dist_type}_tu_{node_name}")
        return type(dist)(lower=lower, mode=mode, upper=upper)
        
    elif dist_class == "Uniform":
        col1, col2 = st.sidebar.columns(2)
        lower = col1.number_input("Lower", value=float(dist.lower), key=f"{dist_type}_ul_{node_name}")
        upper = col2.number_input("Upper", value=float(dist.upper), key=f"{dist_type}_uu_{node_name}")
        return type(dist)(lower=lower, upper=upper)
        
    elif dist_class == "Deterministic":
        value = st.sidebar.number_input("Value", value=float(dist.value), key=f"{dist_type}_d_{node_name}")
        return type(dist)(value=value)
        
    else:
        st.sidebar.warning(f"UI for {dist_class} not implemented. Using defaults.")
        return dist

def render_simulation_app(default_params, model_metadata, valid_process_model=None):
    """Main function to render the simulation UI and execute the model."""
    
    # --- UI: MAIN HEADER ---
    st.title(model_metadata.get("name", "Discrete Event Simulation Runner"))
    st.markdown(f"**Description:** {model_metadata.get('description', 'No description provided.')}")
    
    num_nodes = len(default_params['number_of_servers'])
    
    # Extract node names from JSON metadata if available
    activities = model_metadata.get("activities", [])
    node_names = [act["name"] for act in activities] if activities else [f"Node {i}" for i in range(num_nodes)]
        
    # --- UI: PARAMETER MANIPULATION ---
    st.sidebar.header("1. Resource & Distribution Parameters")
    updated_params = {
        'number_of_servers': [],
        'arrival_distributions': [],
        'service_distributions': [],
        'routing': []
    }
    
    for i in range(num_nodes):
        node_name = node_names[i]
        st.sidebar.subheader(f"{node_name}")
        
        # Extract specific resource name if available in JSON
        resource_name = "Servers"
        if i < len(activities) and "resource" in activities[i]:
            resource_name = activities[i]["resource"]["name"]
            
        # Resourcing
        servers = st.sidebar.slider(
            f"Number of {resource_name}", min_value=1, max_value=50, 
            value=int(default_params['number_of_servers'][i]), key=f"server_{node_name}"
        )
        updated_params['number_of_servers'].append(servers)
        
        # Distributions
        st.sidebar.markdown(f"**Arrival Distribution**")
        arr_dist = _render_distribution_ui(default_params['arrival_distributions'][i], node_name, "Arrival")
        st.sidebar.markdown(f"**Service Distribution**")
        srv_dist = _render_distribution_ui(default_params['service_distributions'][i], node_name, "Service")
        
        updated_params['arrival_distributions'].append(arr_dist)
        updated_params['service_distributions'].append(srv_dist)
        st.sidebar.divider()

    # --- UI: ROUTING MATRIX ---
    st.sidebar.header("32 Routing Matrix")
    df_routing = pd.DataFrame(
        default_params['routing'],
        columns=node_names,
        index=node_names
    )
    
    st.sidebar.write("Edit transition probabilities below:")
    edited_routing = st.sidebar.data_editor(df_routing, key="routing_editor")
    updated_params['routing'] = edited_routing.values.tolist()

    
    # --- UI: SIMULATION SETTINGS --- on main window
    st.markdown("### Run Settings")
    num_reps = st.number_input("Replications", min_value=1, value=100, step=10)
    warmup = st.number_input("Warm-up Time", min_value=0, value=1440, step=100)
    runtime = st.number_input("Run length", min_value=1, value=2880, step=100)

    # --- MAIN PANEL: EXECUTION ---
    if st.button("Run Simulation", type="primary", use_container_width=True):
        with st.spinner(f"Running {num_reps} replications of {model_metadata.get('name', 'the model')}...") :
            try:
                network = ciw.create_network(**updated_params)
                
                df_reps_tidy = multiple_replications(
                    network, 
                    valid_process_model, 
                    warmup=warmup,
                    num_reps=num_reps, 
                    runtime=runtime
                )
                
                st.success("Simulation complete!")
                
                st.subheader("Summary Results")
                summary = summarise_results(df_reps_tidy).round(2)
                st.dataframe(summary, width='stretch')
                
                with st.expander("View Detailed Replication Data"):
                    st.dataframe(df_reps_tidy)
                    
            except Exception as e:
                st.error(f"Simulation Error: {str(e)}")