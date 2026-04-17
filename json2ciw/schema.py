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
    # ADDED: lognormal and gamma. Normal 0.7.0
    type: Literal["exponential", "triangular", "uniform", "deterministic", "lognormal", "gamma", "normal"]
    parameters: Dict[str, float]


class Resource(BaseModel):
    name: str
    capacity: int = Field(..., gt=0)


class Activity(BaseModel):
    name: str
    type: str
    resource: Resource
    service_distribution: Distribution
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

        probs_by_source = defaultdict(float)

        for t in self.transitions:
            if t.source not in activity_names:
                raise ValueError(f"Transition 'from' unknown activity: {t.source}")
            if t.target not in allowed_targets:
                raise ValueError(f"Transition 'to' unknown target: {t.target}")
            probs_by_source[t.source] += t.probability

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

        return self
    
    def to_mermaid(self, include_resources: bool = True) -> str:
        """Convert the process model to Mermaid flowchart syntax."""
        lines = ["```mermaid", "graph TD"]
        
        if self.description:
            lines.append(f"    %% {self.name}: {self.description}")
        
        def make_node_id(name: str) -> str:
            return name.replace(" ", "_").replace("-", "_")
        
        entry_activities = [a for a in self.activities if a.arrival_distribution]
        
        for activity in entry_activities:
            node_id = make_node_id(activity.name)
            arrival_id = f"Arrivals_{node_id}"
            
            arr_dist = activity.arrival_distribution
            p = arr_dist.parameters
            
            if arr_dist.type == "exponential" and "rate" in p:
                arr_label = f"Time between arrivals<br/>Exponential(λ={p['rate']:.1f})"
            elif arr_dist.type == "exponential" and "mean" in p:
                arr_label = f"Time between arrivals<br/>Exponential(mean={p['mean']:.1f})"
            elif arr_dist.type == "triangular":
                arr_label = f"Time between arrivals<br/>Triangular({p.get('min', 0)}, {p.get('mode', 0)}, {p.get('max', 0)})"
            elif arr_dist.type == "uniform":
                arr_label = f"Time between arrivals<br/>Uniform({p.get('min', 0)}, {p.get('max', 0)})"
            elif arr_dist.type == "deterministic" and "value" in p:
                arr_label = f"Time between arrivals<br/>Deterministic({p['value']})"
            # ADDED: lognormal and gamma formatting
            elif arr_dist.type == "lognormal":
                arr_label = f"Time between arrivals<br/>Lognormal(mean={p.get('mean', 0)}, stdev={p.get('stdev', 0)})"
            elif arr_dist.type == "gamma":
                arr_label = f"Time between arrivals<br/>Gamma(shape={p.get('shape', 0)}, scale={p.get('scale', 0)})"
            else:
                arr_label = f"Time between arrivals<br/>{arr_dist.type}"
            
            lines.append(f'    {arrival_id}("{arr_label}")')
        
        for activity in self.activities:
            node_id = make_node_id(activity.name)
            
            serv_dist = activity.service_distribution
            p = serv_dist.parameters
            
            if serv_dist.type == "exponential" and "rate" in p:
                dist_info = f"Exp(λ={p['rate']:.1f})"
            elif serv_dist.type == "exponential" and "mean" in p:
                dist_info = f"Exp(mean={p['mean']:.1f})"
            elif serv_dist.type == "triangular":
                dist_info = f"Tri({p.get('min', 0)}, {p.get('mode', 0)}, {p.get('max', 0)})"
            elif serv_dist.type == "uniform":
                dist_info = f"Uniform({p.get('min', 0)}, {p.get('max', 0)})"
            elif serv_dist.type == "deterministic" and "value" in p:
                dist_info = f"Det({p['value']})"
            # ADDED: lognormal and gamma formatting
            elif serv_dist.type == "lognormal":
                dist_info = f"Lognormal(mean={p.get('mean', 0)}, stdev={p.get('stdev', 0)})"
            elif serv_dist.type == "gamma":
                dist_info = f"Gamma(shape={p.get('shape', 0)}, scale={p.get('scale', 0)})"
            elif serv_dist.type == "normal":
                dist_info = f"Normal(mean={p.get('mean', 0)}, sd={p.get('sd', 0)})"
            else:
                dist_info = serv_dist.type
            
            label = f"{activity.name}<br/>{dist_info}"
            lines.append(f'    {node_id}["{label}"]')
        
        if include_resources:
            seen_resources = set()
            for activity in self.activities:
                if activity.resource.name not in seen_resources:
                    resource_id = make_node_id(f"Resource_{activity.resource.name}")
                    res_label = f"{activity.resource.name}<br/>({activity.resource.capacity})"
                    lines.append(f'    {resource_id}(("{res_label}"))')
                    seen_resources.add(activity.resource.name)
        
        lines.append('    Exit(["Exit"])')
        lines.append("")
        
        for activity in entry_activities:
            node_id = make_node_id(activity.name)
            arrival_id = f"Arrivals_{node_id}"
            lines.append(f'    {arrival_id} --> {node_id}')
        
        if include_resources:
            for activity in self.activities:
                node_id = make_node_id(activity.name)
                resource_id = make_node_id(f"Resource_{activity.resource.name}")
                lines.append(f'    {resource_id} -.Seize.-> {node_id}')
                lines.append(f'    {node_id} -.Release.-> {resource_id}')
        
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

    def display_diagram(self, include_resources: bool = True):
        mermaid_code = self.to_mermaid(include_resources=include_resources)
        display(Markdown(mermaid_code))
        
    def save_diagram(self, filename: str, include_resources: bool = True):
        mermaid_code = self.to_mermaid(include_resources=include_resources)
        with open(filename, 'w') as f:
            f.write(f"# {self.name}\n\n")
            if self.description:
                f.write(f"{self.description}\n\n")
            f.write(mermaid_code)

    def get_distributions_df(self) -> pd.DataFrame:
        records = []
        for activity in self.activities:
            if activity.arrival_distribution:
                arr = activity.arrival_distribution
                records.append({
                    "Activity": activity.name,
                    "Phase": "Arrival",
                    "Distribution Type": arr.type.capitalize(),
                    "Parameters": ", ".join(f"{k}={v}" for k, v in arr.parameters.items())
                })
            
            srv = activity.service_distribution
            records.append({
                "Activity": activity.name,
                "Phase": "Service",
                "Distribution Type": srv.type.capitalize(),
                "Parameters": ", ".join(f"{k}={v}" for k, v in srv.parameters.items())
            })
            
        return pd.DataFrame(records)

    def get_routing_matrix_df(self) -> pd.DataFrame:
        activities = [a.name for a in self.activities]
        targets = activities + ["Exit"]
        matrix = pd.DataFrame(0.0, index=activities, columns=targets)
        matrix.index.name = "Source Activity"
        
        for t in self.transitions:
            if t.source in matrix.index and t.target in matrix.columns:
                matrix.at[t.source, t.target] = t.probability
                
        return matrix


