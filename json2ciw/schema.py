"""
Pydantic schema definitions for validating and visualizing queuing network models.

This module provides data structures to represent discrete event simulation models
compatible with the Ciw library. It includes validation logic for network topology
and transition probabilities, as well as functionality to generate Mermaid
flowcharts for visual verification of the model structure.
"""


from typing import List, Literal, Dict, Optional, Set
from pydantic import BaseModel, Field, model_validator
from collections import defaultdict
from IPython.display import Markdown, display
import pandas as pd

class Distribution(BaseModel):
    type: Literal["exponential", "triangular", "uniform", "deterministic"]
    parameters: Dict[str, float]

class Resource(BaseModel):
    name: str
    capacity: int = Field(..., gt=0)

class Activity(BaseModel):
    name: str
    type: str
    resource: Resource
    service_distribution: Distribution
    # Optional because not all nodes have arrivals
    arrival_distribution: Optional[Distribution] = None

class Transition(BaseModel):
    source: str = Field(..., alias="from")
    target: str = Field(..., alias="to")
    probability: float = Field(..., ge=0.0, le=1.0)

class ProcessModel(BaseModel):
    name: str
    description: Optional[str] = None
    activities: List[Activity]
    transitions: List[Transition]

    @model_validator(mode="after")
    def validate_transition_rows(self) -> "ProcessModel":
        activity_names: Set[str] = {a.name for a in self.activities}
        allowed_targets = activity_names | {"Exit"}

        # 1) Validate references + accumulate outgoing probs per source
        probs_by_source = defaultdict(float)

        for t in self.transitions:
            if t.source not in activity_names:
                raise ValueError(f"Transition 'from' unknown activity: {t.source}")
            if t.target not in allowed_targets:
                raise ValueError(f"Transition 'to' unknown target: {t.target}")
            probs_by_source[t.source] += t.probability

        # 2) Require every activity to have an outgoing total of exactly 1.0
        tol = 1e-9
        missing_sources = []
        bad_sums = []

        for a in self.activities:
            total = probs_by_source.get(a.name, 0.0)
            if total == 0.0:
                missing_sources.append(a.name)
            elif abs(total - 1.0) > tol:
                bad_sums.append((a.name, total))

        if missing_sources:
            raise ValueError(
                "Missing outgoing transitions for activities (sum=0.0): "
                + ", ".join(missing_sources)
            )

        if bad_sums:
            details = ", ".join([f"{name} (sum={total})" for name, total in bad_sums])
            raise ValueError(
                "Outgoing transition probabilities must sum to 1.0 for each activity; "
                f"problems: {details}"
            )

        print("Transitions sum to 1.0 for all activities.")

        return self
    
    def to_mermaid(self) -> str:
        """Convert the process model to Mermaid flowchart syntax."""
        lines = ["```mermaid", "graph TD"]
        
        # Add title as a comment
        if self.description:
            lines.append(f"    %% {self.name}: {self.description}")
        
        # Helper function to create valid node IDs (no spaces)
        def make_node_id(name: str) -> str:
            return name.replace(" ", "_").replace("-", "_")
        
        # Find activities with arrivals (entry points)
        entry_activities = [a for a in self.activities if a.arrival_distribution]
        
        # Create arrival source nodes
        for activity in entry_activities:
            node_id = make_node_id(activity.name)
            arrival_id = f"Arrivals_{node_id}"
            
            arr_dist = activity.arrival_distribution
            # Use <br/> for line breaks
            if arr_dist.type == "exponential" and "rate" in arr_dist.parameters:
                arr_label = f"Time between arrivals<br/>Exponential(λ={arr_dist.parameters['rate']:.1f})"
            elif arr_dist.type == "exponential" and "mean" in arr_dist.parameters:
                arr_label = f"Time between arrivals<br/>Exponential(mean={arr_dist.parameters['mean']:.1f})"
            elif arr_dist.type == "triangular":
                params = arr_dist.parameters
                # Updated to use min/max
                arr_label = f"Time between arrivals<br/>Triangular({params.get('min', 0)}, {params.get('mode', 0)}, {params.get('max', 0)})"
            elif arr_dist.type == "uniform":
                params = arr_dist.parameters
                # Updated to use min/max
                arr_label = f"Time between arrivals<br/>Uniform({params.get('min', 0)}, {params.get('max', 0)})"
            elif arr_dist.type == "deterministic" and "value" in arr_dist.parameters:
                arr_label = f"Time between arrivals<br/>Deterministic({arr_dist.parameters['value']})"
            else:
                arr_label = f"Time between arrivals<br/>{arr_dist.type}"
            
            lines.append(f'    {arrival_id}("{arr_label}")')
        
        # Define activity nodes
        for activity in self.activities:
            node_id = make_node_id(activity.name)
            
            serv_dist = activity.service_distribution
            if serv_dist.type == "exponential" and "rate" in serv_dist.parameters:
                dist_info = f"Exp(λ={serv_dist.parameters['rate']:.1f})"
            elif serv_dist.type == "triangular":
                params = serv_dist.parameters
                dist_info = f"Tri({params.get('min', 0)}, {params.get('mode', 0)}, {params.get('max', 0)})"
            elif serv_dist.type == "uniform":
                params = serv_dist.parameters
                dist_info = f"Uniform({params.get('min', 0)}, {params.get('max', 0)})"
            elif serv_dist.type == "deterministic" and "value" in serv_dist.parameters:
                dist_info = f"Det({serv_dist.parameters['value']})"
            else:
                dist_info = serv_dist.type
            
            # Removed resource name from here. Using <br/> for line break.
            label = f"{activity.name}<br/>{dist_info}"
            
            lines.append(f'    {node_id}["{label}"]')
        
        # Add resource nodes (circles) with capacity
        seen_resources = set()
        for activity in self.activities:
            if activity.resource.name not in seen_resources:
                resource_id = make_node_id(f"Resource_{activity.resource.name}")
                # Added capacity to label here: Name\n(Capacity)
                res_label = f"{activity.resource.name}<br/>({activity.resource.capacity})"
                lines.append(f'    {resource_id}(("{res_label}"))')
                seen_resources.add(activity.resource.name)
        
        # Add Exit node
        lines.append('    Exit(["Exit"])')
        lines.append("")
        
        # Connections
        # 1. Arrival -> Activity
        for activity in entry_activities:
            node_id = make_node_id(activity.name)
            arrival_id = f"Arrivals_{node_id}"
            lines.append(f'    {arrival_id} --> {node_id}')
        
        # 2. Resource -> Activity (Seize/Release)
        for activity in self.activities:
            node_id = make_node_id(activity.name)
            resource_id = make_node_id(f"Resource_{activity.resource.name}")
            lines.append(f'    {resource_id} -.Seize.-> {node_id}')
            lines.append(f'    {node_id} -.Release.-> {resource_id}')
        
        # 3. Transitions
        for transition in self.transitions:
            source_id = make_node_id(transition.source)
            target_id = make_node_id(transition.target) if transition.target != "Exit" else "Exit"
            
            if transition.probability == 1.0:
                lines.append(f'    {source_id} --> {target_id}')
            else:
                prob_label = f"{transition.probability:.0%}"
                lines.append(f'    {source_id} -->|{prob_label}| {target_id}')
        
        lines.append("```")
        return "\n".join(lines)


    def display_diagram(self):
        """Display the Mermaid diagram in Jupyter notebook."""
        mermaid_code = self.to_mermaid()
        display(Markdown(mermaid_code))
        
    def save_diagram(self, filename: str):
        """Save the Mermaid diagram to a markdown file."""
        mermaid_code = self.to_mermaid()
        with open(filename, 'w') as f:
            f.write(f"# {self.name}\n\n")
            if self.description:
                f.write(f"{self.description}\n\n")
            f.write(mermaid_code)

    def get_distributions_df(self) -> pd.DataFrame:
        """Returns a DataFrame of all arrival and service distributions."""
        records = []
        for activity in self.activities:
            # Arrival distribution
            if activity.arrival_distribution:
                arr = activity.arrival_distribution
                records.append({
                    "Activity": activity.name,
                    "Phase": "Arrival",
                    "Distribution Type": arr.type.capitalize(),
                    "Parameters": ", ".join(f"{k}={v}" for k, v in arr.parameters.items())
                })
            
            # Service distribution
            srv = activity.service_distribution
            records.append({
                "Activity": activity.name,
                "Phase": "Service",
                "Distribution Type": srv.type.capitalize(),
                "Parameters": ", ".join(f"{k}={v}" for k, v in srv.parameters.items())
            })
            
        return pd.DataFrame(records)

    def get_routing_matrix_df(self) -> pd.DataFrame:
        """Returns a DataFrame representing the transition probability matrix."""
        # Sources are activities; targets include activities and the Exit node
        activities = [a.name for a in self.activities]
        targets = activities + ["Exit"]
        
        # Initialize matrix with zeros
        matrix = pd.DataFrame(0.0, index=activities, columns=targets)
        matrix.index.name = "Source Activity"
        
        # Populate probabilities
        for t in self.transitions:
            if t.source in matrix.index and t.target in matrix.columns:
                matrix.at[t.source, t.target] = t.probability
                
        return matrix



