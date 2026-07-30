"""Define validated queueing network schemas and visualisation helpers.

This module provides Pydantic models for representing queueing network
specifications, validating transition logic, and generating tabular or
Mermaid-based views of the model structure.
"""

from collections import defaultdict
from pathlib import Path
from typing import Literal, Self, TypeAlias

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


class ClassDistributionMap(BaseModel):
    """Define class-specific distribution specifications.

    Attributes
    ----------
    by_class : dict of str to Distribution
        Mapping from customer class name to the distribution used for
        that class.

    """
    by_class: dict[str, Distribution]


DistributionSpec: TypeAlias = Distribution | ClassDistributionMap


class CustomerClass(BaseModel):
    """Define a customer class in the ProcessModel.

    E.g. 
    planned versus unplanned patients for surgery
    mild/moderate stroke versus severe stroke

    Attributes
    ----------
    name : str
        Unique machine-readable identifier for the customer class.
    label : str or None
        Human-readable label for the customer class.

    """
    name: str
    label: str | None = None


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
    service_distribution : Distribution or ClassDistributionMap
        Service-time distribution, either shared across all customer
        classes or specified separately by customer class.
    arrival_distribution : Distribution or ClassDistributionMap or None
        Arrival distribution for entry activities, either shared across
        all customer classes or specified separately by customer class.
    renege_distribution : Distribution or None
        Reneging distribution for the activity.

    """
    name: str
    type: str
    resource: Resource
    service_distribution: DistributionSpec
    arrival_distribution: DistributionSpec | None = None
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
    customer_classes : list of CustomerClass
        Customer classes available in the model.
    activities : list of Activity
        Activities in the model.
    transitions : list of Transition
        Directed transitions between activities.

    """

    name: str
    description: str | None = None
    customer_classes: list[CustomerClass] = Field(default_factory=list)
    activities: list[Activity]
    transitions: list[Transition]

    @model_validator(mode="after")
    def validate_customer_classes(self) -> Self:
        class_names = [c.name for c in self.customer_classes]
        if len(class_names) != len(set(class_names)):
            raise ValueError("Customer class names must be unique.")

        allowed_classes = set(class_names)

        def check_distribution_keys(
            spec: DistributionSpec | None, field_name: str, activity_name: str
        ) -> None:
            if spec is None:
                return
            if isinstance(spec, ClassDistributionMap):
                unknown = set(spec.by_class) - allowed_classes
                if unknown:
                    raise ValueError(
                        f"{field_name} in activity '{activity_name}' uses unknown "
                        f"customer classes: {', '.join(sorted(unknown))}"
                    )

        for activity in self.activities:
            check_distribution_keys(
                activity.service_distribution,
                "service_distribution",
                activity.name,
            )
            check_distribution_keys(
                activity.arrival_distribution,
                "arrival_distribution",
                activity.name,
            )

        return self

    @model_validator(mode="after")
    def validate_transition_rows(self) -> Self:
        activity_names: set[str] = {a.name for a in self.activities}
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
            details = ", ".join(
                [f"{name} (sum={total})" for name, total in bad_sums]
            )
            raise ValueError(
                "Outgoing transition probabilities must sum to 1.0 for each "
                f"activity; problems: {details}"
            )

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
                f"Triangular({params.get('min', 0)}, "
                f"{params.get('mode', 0)}, {params.get('max', 0)})",
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

    def _iter_distribution_spec(
        self, spec: DistributionSpec
    ) -> list[tuple[str | None, str | None, Distribution]]:
        """Iterate over a distribution specification.

        Parameters
        ----------
        spec : DistributionSpec
            Distribution specification to expand. This may be a single
            shared distribution or a class-specific mapping.

        Returns
        -------
        list of tuple of str or None, str or None, Distribution
            Expanded distribution entries as tuples of
            `(customer_class_name, customer_class_label, distribution)`.
            For shared distributions, the class name and label are `None`.
        """
        class_labels = {
            c.name: (c.label or c.name) for c in getattr(self, "customer_classes", [])
        }

        if isinstance(spec, Distribution):
            return [(None, None, spec)]

        return [
            (class_name, class_labels.get(class_name, class_name), dist)
            for class_name, dist in spec.by_class.items()
        ]


    def _summarise_distribution_spec(
        self, spec: DistributionSpec, context: str = "service"
    ) -> str:
        """Summarise a distribution specification for compact display.

        Parameters
        ----------
        spec : DistributionSpec
            Distribution specification to summarise.
        context : str, optional
            Rendering context. Use `"arrival"` for arrival summaries and
            `"service"` for service summaries, by default `"service"`.

        Returns
        -------
        str
            Summary label suitable for compact Mermaid node text.
        """
        if isinstance(spec, Distribution):
            return self._format_dist(spec, context=context)

        if context == "arrival":
            return "Class-specific arrival distributions"
        return "Class-specific service distributions"


    def to_mermaid(
        self,
        *,
        include_resources: bool = True,
        show_class_arrivals: bool = True,
    ) -> str:
        """Convert the process model to a Mermaid flowchart.

        Parameters
        ----------
        include_resources : bool, optional
            Whether to include resource nodes, by default `True`.
        show_class_arrivals : bool, optional
            Whether to render separate arrival nodes for each customer class
            when class-specific arrival distributions are defined, by default
            `True`.

        Returns
        -------
        str
            Mermaid flowchart source.

        Notes
        -----
        Node types used in the diagram:

        - **Rounded rectangle** ``( )``: Arrival source nodes, labelled with
        the inter-arrival distribution.
        - **Rectangle** ``[ ]``: Activity nodes, labelled with the activity
        name and service distribution.
        - **Hexagon** ``{{ }}``: Renege nodes, connected to their parent
        activity via a dashed edge. Rendered only when an activity has a
        ``renege_distribution`` defined.
        - **Stadium** ``([ ])``: The terminal ``Exit`` node.
        - **Double circle** ``(( ))``: Resource nodes, rendered when
        ``include_resources=True``.

        Transition edges with probability < 1.0 are labelled with the
        percentage. Renege edges are always dashed (``-.->``). Resource
        seize/release edges are dashed with text labels.

        Examples
        --------
        >>> print(model.to_mermaid())
        >>> model.to_mermaid(include_resources=False)
        """
    
        lines = ["flowchart TD"]

        def make_node_id(name: str) -> str:
            """Create a Mermaid-safe node identifier.

            Parameters
            ----------
            name : str
                Raw node name.

            Returns
            -------
            str
                Sanitised node identifier with spaces and hyphens replaced
                by underscores.
            """
            return name.replace(" ", "_").replace("-", "_")

        entry_activities = [a for a in self.activities if a.arrival_distribution]

        # --- Arrival nodes ---
        for activity in entry_activities:
            node_id = make_node_id(activity.name)
            arr_spec = activity.arrival_distribution

            if isinstance(arr_spec, Distribution) or not show_class_arrivals:
                arrival_id = f"Arrivals_{node_id}"
                arr_label = self._summarise_distribution_spec(
                    arr_spec, context="arrival"
                )
                lines.append(f'    {arrival_id}("{arr_label}")')
            else:
                for class_name, class_label, dist in self._iter_distribution_spec(arr_spec):
                    class_id = make_node_id(class_name)
                    arrival_id = f"Arrivals_{node_id}_{class_id}"
                    arr_label = (
                        f"{class_label}"
                        + "\\n"
                        + self._format_dist(dist, context="arrival")
                    )
                    lines.append(f'    {arrival_id}("{arr_label}")')

        # --- Activity nodes ---
        for activity in self.activities:
            node_id = make_node_id(activity.name)
            dist_info = self._summarise_distribution_spec(
                activity.service_distribution, context="service"
            )
            label = f"{activity.name}\\n{dist_info}"
            lines.append(f'    {node_id}["{label}"]')

        # --- Renege nodes ---
        for activity in self.activities:
            if activity.renege_distribution:
                node_id = make_node_id(activity.name)
                renege_id = f"Renege_{node_id}"
                renege_info = self._format_dist(activity.renege_distribution)
                lines.append(f'    {renege_id}{{{{"Renege\\n{renege_info}"}}}}')

        # --- Resource nodes ---
        if include_resources:
            seen_resources = set()
            for activity in self.activities:
                if activity.resource.name not in seen_resources:
                    resource_id = make_node_id(f"Resource_{activity.resource.name}")
                    res_label = f"{activity.resource.name} ({activity.resource.capacity})"
                    lines.append(f'    {resource_id}(("{res_label}"))')
                    seen_resources.add(activity.resource.name)

        lines.append('    Exit(["Exit"])')
        lines.append("")

        # --- Edges: arrivals ---
        for activity in entry_activities:
            node_id = make_node_id(activity.name)
            arr_spec = activity.arrival_distribution

            if isinstance(arr_spec, Distribution) or not show_class_arrivals:
                arrival_id = f"Arrivals_{node_id}"
                lines.append(f"    {arrival_id} --> {node_id}")
            else:
                for class_name, _, _ in self._iter_distribution_spec(arr_spec):
                    class_id = make_node_id(class_name)
                    arrival_id = f"Arrivals_{node_id}_{class_id}"
                    lines.append(f"    {arrival_id} --> {node_id}")

        # --- Edges: resource seize/release ---
        if include_resources:
            for activity in self.activities:
                node_id = make_node_id(activity.name)
                resource_id = make_node_id(f"Resource_{activity.resource.name}")
                lines.append(f"    {resource_id} -.Seize.-> {node_id}")
                lines.append(f"    {node_id} -.Release.-> {resource_id}")

        # --- Edges: renege ---
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
            Distribution details for each activity phase, expanded by
            customer class where class-specific distributions are defined.
        """
        records = []

        for activity in self.activities:
            if activity.arrival_distribution:
                for class_name, class_label, dist in self._iter_distribution_spec(
                    activity.arrival_distribution
                ):
                    records.append(
                        {
                            "Activity": activity.name,
                            "Phase": "Arrival",
                            "Customer Class": class_name or "All",
                            "Customer Class Label": class_label or "All",
                            "Distribution Type": dist.type.capitalize(),
                            "Parameters": ", ".join(
                                f"{k}={v}" for k, v in dist.parameters.items()
                            ),
                        }
                    )

            for class_name, class_label, dist in self._iter_distribution_spec(
                activity.service_distribution
            ):
                records.append(
                    {
                        "Activity": activity.name,
                        "Phase": "Service",
                        "Customer Class": class_name or "All",
                        "Customer Class Label": class_label or "All",
                        "Distribution Type": dist.type.capitalize(),
                        "Parameters": ", ".join(
                            f"{k}={v}" for k, v in dist.parameters.items()
                        ),
                    }
                )

            if activity.renege_distribution:
                dist = activity.renege_distribution
                records.append(
                    {
                        "Activity": activity.name,
                        "Phase": "Renege",
                        "Customer Class": "All",
                        "Customer Class Label": "All",
                        "Distribution Type": dist.type.capitalize(),
                        "Parameters": ", ".join(
                            f"{k}={v}" for k, v in dist.parameters.items()
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
