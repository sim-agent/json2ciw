from json2ciw.datasets import (
    load_call_centre_model, 
    load_jackson_network_model, 
    load_three_node_network_model,
    load_six_node_ucc_model,
    load_renege_call_model,
    load_mm1_renege_model,
    
)
from json2ciw.engine import CiwConverter
from json2ciw import render_simulation_app
from json2ciw.schema import ProcessModel

import ciw
import streamlit as st

st.set_page_config(layout="wide")

# Map the dropdown display names to their corresponding functions
model_loaders = {
    "Jackson Network": load_jackson_network_model,
    "Call Centre": load_call_centre_model,
    "Three Node Network": load_three_node_network_model,
    "Urgent Care Treatment Centre": load_six_node_ucc_model,
    "Renge Call Centre": load_renege_call_model,
    "M/M/1 with Renege": load_mm1_renege_model,
}

# Create a dropdown to select the model
selected_model_name = st.selectbox(
    "Select Model", 
    options=list(model_loaders.keys())
)

# 1. Load the selected model as JSON
# This calls the function associated with the selected dropdown option
json_model = model_loaders[selected_model_name]()

# 2. Convert to instance of a json2ciw ProcessModel
model_instance = ProcessModel(**json_model)

# 3. Convert to ciw network parameters
adapter = CiwConverter(model_instance)
default_params = adapter.generate_params()

# 4. Convert to ciw network
network = ciw.create_network(**default_params)

# 5. Render the model as an app
render_simulation_app(default_params, json_model, valid_process_model=model_instance)
