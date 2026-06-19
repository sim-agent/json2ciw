"""Define validated queueing network schemas and visualisation helpers.

This module provides Pydantic models for representing queueing network
specifications, validating transition logic, and generating tabular or
Mermaid-based views of the model structure.
"""

from collections import defaultdict
from pathlib import Path
from typing import Literal, Self

import pandas as pd
from IPython.display import Markdown, display
from pydantic import BaseModel, Field, model_validator


class Distribution(BaseModel):
    """Define a probability distribution specification.

    Attributes
    ----------
    type : Literal
        Distribution type.
    parameters : dict of str to float
        Distribution parameters.

    """

    # ADDED: lognormal and gamma. Normal 0.7.0
    type: Literal[
        "exponential",
        "triangular",
        "uniform",
        "deterministic",
        "lognormal",
        "gamma",
        "normal",
    ]
    parameters: dict[str, float]


class Resource(BaseModel):
    """Define a resource used by an activity.

    Attributes
    ----------
    name : str
        Resource name.
    capacity : int
        Resource capacity.

    """

    name: str
    capacity: int = Field(..., gt=0)


class Activity(BaseModel):
    """Define an activity in the process model.

    Attributes
    ----------
    name : str
        Activity name.
    type : str
        Activity type.
    resource : Resource
        Resource used by the activity.
    service_distribution : Distribution
        Service-time distribution.
    arrival_distribution : Distribution or None
        Arrival distribution for entry activities.
    renege_distribution : Distribution or None
        Reneging distribution for the activity.

    """

    name: str
    type: str
    resource: Resource
    service_distribution: Distribution
    arrival_distribution: Distribution | None = None
    # added v0.10.0
    renege_distribution: Distribution | None = None


class Transition(BaseModel):
    """Define a transition between activities.

    Attributes
    ----------
    source : str
        Source activity name.
    target : str
        Target activity name or `"Exit"`.
    probability : float
        Transition probability.

    """

    source: str = Field(..., alias="from")
    target: str = Field(..., alias="to")
    probability: float = Field(..., ge=0.0, le=1.0)


class ProcessModel(BaseModel):
    """Define a validated queueing network process model.

    Attributes
    ----------
    name : str
        Model name.
    description : str or None
        Model description.
    activities : list of Activity
        Activities in the model.
    transitions : list of Transition
        Directed transitions between activities.

    """

    name: str
    description: str | None = None
    activities: list[Activity]
    transitions: list[Transition]

    @model_validator(mode="after")
    def validate_transition_rows(self) -> Self:
        """Validate outgoing transition probabilities.

        Returns
        -------
        Self
            Validated process model.

        """
        activity_names: set[str] = {a.name for a in self.activities}
        allowed_targets = activity_names | {"Exit"}

        probs_by_source = defaultdict(float)

        for t in self.transitions:
            if t.source not in activity_names:
                msg = f"Transition 'from' unknown activity: {t.source}"
                raise ValueError(msg)
            if t.target not in allowed_targets:
                msg = f"Transition 'to' unknown target: {t.target}"
                raise ValueError(msg)
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
            details = ", ".join(
                [f"{name} (sum={total})" for name, total in bad_sums]
            )
            msg = (
                "Outgoing transition probabilities must sum to 1.0 for each "
                f"activity; problems: {details}"
            )
            raise ValueError(msg)

        return self

    def _format_dist(
        self, dist: Distribution, context: str = "service"
    ) -> str:
        """Format a distribution for Mermaid labels.

        Parameters
        ----------
        dist : Distribution
            Distribution to format.
        context : str, optional
            Rendering context. Use `'arrival'` to prepend
            `'Time between arrivals<br/>'` for arrival node labels.
            Use `'service'` or `'renege'` for compact activity and
            renege node labels. Default is `'service'`.

        Returns
        -------
        str
            Formatted distribution label.

        """
        params = dist.parameters

        # Parameter formatting (shared logic)
        if dist.type == "exponential" and "rate" in params:
            label = f"Exponential(λ={params['rate']:.1f})"
        elif dist.type == "exponential" and "mean" in params:
            label = f"Exponential(mean={params['mean']:.1f})"
        elif dist.type == "triangular":
            label = (
                f"Triangular({params.get('min', 0)}, ",
                +f"{params.get('mode', 0)}, {params.get('max', 0)})",
            )
        elif dist.type == "uniform":
            label = f"Uniform({params.get('min', 0)}, {params.get('max', 0)})"
        elif dist.type == "deterministic" and "value" in params:
            label = f"Deterministic({params['value']})"
        elif dist.type == "lognormal":
            label = (
                f"Lognormal(mean={params.get('mean', 0)}, "
                f"stdev={params.get('stdev', 0)})"
            )
        elif dist.type == "gamma":
            label = (
                f"Gamma(shape={params.get('shape', 0)}, "
                f"scale={params.get('scale', 0)})"
            )
        elif dist.type == "normal":
            label = (
                f"Normal(mean={params.get('mean', 0)}, "
                f"sd={params.get('sd', 0)})"
            )
        else:
            label = dist.type

        # Context-specific prefix
        if context == "arrival":
            return f"Time between arrivals<br/>{label}"
        return label

    def to_mermaid(self, *, include_resources: bool = True) -> str:
        """Convert the process model to a Mermaid flowchart.

        Parameters
        ----------
        include_resources : bool, optional
            Whether to include resource nodes, by default `True`.

        Returns
        -------
        str
            Mermaid flowchart source.

        """
        lines = ["flowchart TD"]

        def make_node_id(name: str) -> str:
            return name.replace(" ", "_").replace("-", "_")

        entry_activities = [
            a for a in self.activities if a.arrival_distribution
        ]

        # --- Arrival nodes ---
        for activity in entry_activities:
            node_id = make_node_id(activity.name)
            arrival_id = f"Arrivals_{node_id}"
            arr_label = self._format_dist(
                activity.arrival_distribution, context="arrival"
            )
            lines.append(f'    {arrival_id}("{arr_label}")')

        # --- Activity nodes ---
        for activity in self.activities:
            node_id = make_node_id(activity.name)
            dist_info = self._format_dist(activity.service_distribution)
            label = f"{activity.name}<br/>{dist_info}"
            lines.append(f'    {node_id}["{label}"]')

        # --- Renege nodes (parallel renege flow) ---
        for activity in self.activities:
            if activity.renege_distribution:
                node_id = make_node_id(activity.name)
                renege_id = f"Renege_{node_id}"
                renege_info = self._format_dist(activity.renege_distribution)
                lines.append(
                    "    " + renege_id + '{{"Renege<br/>' + renege_info + '"}}'
                )

        # --- Resource nodes ---
        if include_resources:
            seen_resources = set()
            for activity in self.activities:
                if activity.resource.name not in seen_resources:
                    resource_id = make_node_id(
                        f"Resource_{activity.resource.name}"
                    )
                    res_label = (
                        f"{activity.resource.name}<br/>("
                        f"{activity.resource.capacity})"
                    )
                    lines.append(f'    {resource_id}(("{res_label}"))')
                    seen_resources.add(activity.resource.name)

        lines.append('    Exit(["Exit"])')
        lines.append("")

        # --- Edges: arrivals ---
        for activity in entry_activities:
            node_id = make_node_id(activity.name)
            arrival_id = f"Arrivals_{node_id}"
            lines.append(f"    {arrival_id} --> {node_id}")

        # --- Edges: resource seize/release ---
        if include_resources:
            for activity in self.activities:
                node_id = make_node_id(activity.name)
                resource_id = make_node_id(
                    f"Resource_{activity.resource.name}"
                )
                lines.append(f"    {resource_id} -.Seize.-> {node_id}")
                lines.append(f"    {node_id} -.Release.-> {resource_id}")

        # --- Edges: renege (dashed optional path) ---
        for activity in self.activities:
            if activity.renege_distribution:
                node_id = make_node_id(activity.name)
                renege_id = f"Renege_{node_id}"
                lines.append(f"    {node_id} -.-> {renege_id}")

        # --- Edges: transitions ---
        for transition in self.transitions:
            source_id = make_node_id(transition.source)
            target_id = (
                make_node_id(transition.target)
                if transition.target != "Exit"
                else "Exit"
            )

            if transition.probability == 1.0:
                lines.append(f"    {source_id} --> {target_id}")
            else:
                prob_label = f"{transition.probability:.0%}"
                lines.append(f"    {source_id} -->|{prob_label}| {target_id}")

        return "\n".join(lines)

    def display_diagram(self, *, include_resources: bool = True) -> None:
        """Display the Mermaid diagram in a notebook.

        Parameters
        ----------
        include_resources : bool, optional
            Whether to include resource nodes, by default `True`.

        """
        mermaid_code = self.to_mermaid(include_resources=include_resources)
        display(Markdown(mermaid_code))

    def save_diagram(
        self, filename: str, *, include_resources: bool = True
    ) -> None:
        """Save the Mermaid diagram to a file.

        Parameters
        ----------
        filename : str
            Output filename (e.g., "diagram.mmd").
        include_resources : bool, optional
            Whether to include resource nodes, by default `True`.

        """
        mermaid_code = self.to_mermaid(include_resources=include_resources)
        with Path.open(filename, "w") as f:
            f.write(mermaid_code)

    def get_distributions_df(self) -> pd.DataFrame:
        """Return model distributions as a DataFrame.

        Returns
        -------
        pandas.DataFrame
            Distribution details for each activity phase.

        """
        records = []
        for activity in self.activities:
            if activity.arrival_distribution:
                arr = activity.arrival_distribution
                records.append(
                    {
                        "Activity": activity.name,
                        "Phase": "Arrival",
                        "Distribution Type": arr.type.capitalize(),
                        "Parameters": ", ".join(
                            f"{k}={v}" for k, v in arr.parameters.items()
                        ),
                    }
                )

            srv = activity.service_distribution
            records.append(
                {
                    "Activity": activity.name,
                    "Phase": "Service",
                    "Distribution Type": srv.type.capitalize(),
                    "Parameters": ", ".join(
                        f"{k}={v}" for k, v in srv.parameters.items()
                    ),
                }
            )

            # added v0.10.0 to show renege parameters if present.
            if activity.renege_distribution:
                ren = activity.renege_distribution
                records.append(
                    {
                        "Activity": activity.name,
                        "Phase": "Renege",
                        "Distribution Type": ren.type.capitalize(),
                        "Parameters": ", ".join(
                            f"{k}={v}" for k, v in ren.parameters.items()
                        ),
                    }
                )

        return pd.DataFrame(records)

    def get_routing_matrix_df(self) -> pd.DataFrame:
        """Return routing probabilities as a DataFrame.

        Returns
        -------
        pandas.DataFrame
            Routing matrix with source activities as rows.

        """
        activities = [a.name for a in self.activities]
        targets = [*activities, "Exit"]
        matrix = pd.DataFrame(0.0, index=activities, columns=targets)
        matrix.index.name = "Source Activity"

        for transition in self.transitions:
            if (
                transition.source in matrix.index
                and transition.target in matrix.columns
            ):
                matrix.loc[transition.source, transition.target] = (
                    transition.probability
                )

        return matrix

    def get_resources_df(self) -> pd.DataFrame:
        """Return activity resources as a DataFrame.

        Returns
        -------
        pandas.DataFrame
            Resource assignments for each activity.

        """
        records = [
            {
                "Resource": activity.resource.name,
                "Activity": activity.name,
                "Count": activity.resource.capacity,
            }
            for activity in self.activities
        ]
        return pd.DataFrame(records)
