from json2ciw.datasets import load_call_centre_model
from json2ciw.engine import (
    CiwConverter,
)

from json2ciw import render_simulation_app

from json2ciw.schema import ProcessModel

import ciw
import streamlit as st

st.set_page_config(layout="wide")

# 1. load the call centre model as JSON
json_call_centre = load_call_centre_model()

# 2 convert to instance of a json2ciw ProcessModel
model_instance = ProcessModel(**json_call_centre)

# 3. Convert to ciw network parameters
adapter = CiwConverter(model_instance)
default_params = adapter.generate_params()

# 4. Convert to ciw network
network = ciw.create_network(**default_params)

# 4. render the model as an app
render_simulation_app(default_params, json_call_centre, valid_process_model=model_instance)