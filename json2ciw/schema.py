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


class ClassProbabilityMap(BaseModel):
    """Define class-specific routing probabilities.

    Attributes
    ----------
    by_class : dict of str to float
        Mapping from customer class name to the routing probability
        used for that class.
    """
    by_class: dict[str, float]


ProbabilitySpec: TypeAlias = float | ClassProbabilityMap


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
    renege_distribution : Distribution or ClassDistributionMap or None
            Reneging distribution for the activity, either shared across
            all customer classes or specified separately by customer class

    """
    name: str
    type: str
    resource: Resource
    service_distribution: DistributionSpec
    arrival_distribution: DistributionSpec | None = None
    renege_distribution: DistributionSpec | None = None


class Transition(BaseModel):
    """Define a transition between activities.

    Attributes
    ----------
    source : str
        Source activity name.
    target : str
        Target activity name or `"Exit"`.
    probability : float or ClassProbabilityMap
        Transition probability, either shared across all customer
        classes or specified separately by customer class.

    """

    source: str = Field(..., alias="from")
    target: str = Field(..., alias="to")
    probability: ProbabilitySpec


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
            check_distribution_keys(
                activity.renege_distribution,
                "renege_distribution",
                activity.name,
            )

        # validate transitions
        for transition in self.transitions:
            if isinstance(transition.probability, ClassProbabilityMap):
                if not allowed_classes:
                    raise ValueError(
                        "Class-specific routing probabilities require "
                        "customer_classes to be defined."
                    )
                unknown = set(transition.probability.by_class) - allowed_classes
                if unknown:
                    raise ValueError(
                        f"Transition '{transition.source}' -> "
                        f"'{transition.target}' uses unknown customer "
                        f"classes: {', '.join(sorted(unknown))}"
                    )


        return self

    @model_validator(mode="after")
    def validate_transition_rows(self) -> Self:
        """Validate transition targets and outgoing routing probabilities.

        For single-class models, outgoing probabilities must sum to 1.0
        for every activity.

        For multi-class models, each customer class has its own effective
        routing probabilities. Shared scalar probabilities apply to every
        class, while class-specific probabilities apply only to their
        named class. The outgoing probabilities must therefore sum to 1.0
        for every activity/customer-class combination.

        Returns
        -------
        Self
            Validated process model.

        """
        # Build the set of valid activity names. Transitions may point to
        # another activity or to the special terminal "Exit" target.
        activity_names: set[str] = {activity.name for activity in self.activities}
        allowed_targets = activity_names | {"Exit"}

        # Extract class names once. An empty list denotes a single-class
        # model, which retains the original scalar-routing behaviour.
        class_names = [customer_class.name for customer_class in self.customer_classes]

        # Floating-point tolerance for comparison
        tol = 1e-9

        # First validate the activity names used by every transition.
        # Do this before calculating probability totals, so errors refer
        # directly to an invalid source or target.
        for transition in self.transitions:
            if transition.source not in activity_names:
                raise ValueError(
                    f"Transition 'from' unknown activity: {transition.source}"
                )

            if transition.target not in allowed_targets:
                raise ValueError(
                    f"Transition 'to' unknown target: {transition.target}"
                )

        # Single-class models cannot use a class-specific probability map.
        # In this case, preserve the original rule: sum scalar probabilities
        # once for each source activity.
        if not class_names:
            probs_by_source = defaultdict(float)

            for transition in self.transitions:
                if isinstance(transition.probability, ClassProbabilityMap):
                    raise ValueError(
                        "Class-specific routing probabilities require "
                        "customer_classes to be defined."
                    )

                probs_by_source[transition.source] += transition.probability

            missing_sources = []
            bad_sums = []

            # Each activity must have at least one outgoing transition, and
            # its probabilities must add up to 1.0.
            for activity in self.activities:
                total = probs_by_source.get(activity.name, 0.0)

                if total == 0.0:
                    missing_sources.append(activity.name)
                elif abs(total - 1.0) > tol:
                    bad_sums.append((activity.name, total))

            if missing_sources:
                raise ValueError(
                    "Missing outgoing transitions for activities (sum=0.0): "
                    + ", ".join(missing_sources)
                )

            if bad_sums:
                details = ", ".join(
                    f"{activity_name} (sum={total})"
                    for activity_name, total in bad_sums
                )
                raise ValueError(
                    "Outgoing transition probabilities must sum to 1.0 for "
                    f"each activity; problems: {details}"
                )

            return self

        # Multi-class models need one probability total per source activity
        # and per customer class. The nested defaultdict creates a zero-valued
        # total automatically for unseen activity/class combinations.
        probs_by_source_and_class = defaultdict(lambda: defaultdict(float))

        for transition in self.transitions:
            if isinstance(transition.probability, ClassProbabilityMap):
                # A class-specific probability map may omit a class. An omitted
                # class contributes zero probability on this transition; the
                # full set of outgoing transitions must still total 1.0 for it.
                for class_name in class_names:
                    probs_by_source_and_class[transition.source][class_name] += (
                        transition.probability.by_class.get(class_name, 0.0)
                    )
            else:
                # A scalar probability is shared: it applies to every customer
                # class in the model.
                for class_name in class_names:
                    probs_by_source_and_class[transition.source][class_name] += (
                        transition.probability
                    )

        missing_sources = []
        bad_sums = []

        # Validate every activity/class combination independently. This is what
        # allows, for example, TIA patients to exit from Acute Stroke Unit while
        # severe-stroke patients route to the Rehab Unit.
        for activity in self.activities:
            for class_name in class_names:
                total = probs_by_source_and_class[activity.name].get(
                    class_name,
                    0.0,
                )

                if total == 0.0:
                    missing_sources.append(f"{activity.name} [{class_name}]")
                elif abs(total - 1.0) > tol:
                    bad_sums.append((activity.name, class_name, total))

        if missing_sources:
            raise ValueError(
                "Missing outgoing transitions for activity/customer class "
                "(sum=0.0): " + ", ".join(missing_sources)
            )

        if bad_sums:
            details = ", ".join(
                f"{activity_name} [{class_name}] (sum={total})"
                for activity_name, class_name, total in bad_sums
            )
            raise ValueError(
                "Outgoing transition probabilities must sum to 1.0 for each "
                f"activity and customer class; problems: {details}"
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

    def _resolve_probability_spec(
        self,
        spec: ProbabilitySpec,
        customer_class: str,
    ) -> float:
        """Resolve a transition probability for one customer class.

        Parameters
        ----------
        spec : ProbabilitySpec
            Shared scalar routing probability or a class-specific
            probability mapping.
        customer_class : str
            Customer class name for which to resolve the probability.

        Returns
        -------
        float
            Routing probability for the requested customer class. A missing
            class-specific value is treated as zero.

        """
        if isinstance(spec, ClassProbabilityMap):
            return spec.by_class.get(customer_class, 0.0)

        return spec

    def _format_probability_spec(self, spec: ProbabilitySpec) -> str | None:
        """Format a routing probability specification for Mermaid.

        Parameters
        ----------
        spec : ProbabilitySpec
            Shared scalar routing probability or a class-specific
            probability mapping.

        Returns
        -------
        str or None
            Mermaid edge label. Returns `None` for a shared probability
            of 1.0, allowing an unlabelled edge.

        """
        if not isinstance(spec, ClassProbabilityMap):
            if spec == 1.0:
                return None
            return f"{spec:.0%}"

        class_labels = {
            customer_class.name: (
                customer_class.label or customer_class.name
            )
            for customer_class in self.customer_classes
        }

        parts = [
            f"{class_labels.get(class_name, class_name)}: {probability:.0%}"
            for class_name, probability in spec.by_class.items()
        ]

        return "<br/>".join(parts)

    def _summarise_distribution_spec(
        self, spec: DistributionSpec, context: str = "service"
    ) -> str:
        """Summarise a distribution specification for compact display.

        Parameters
        ----------
        spec : DistributionSpec
            Distribution specification to summarise.
        context : str, optional
            Rendering context. Use `"arrival"` for arrival summaries,
            `"service"` for service summaries, and `"renege"` for
            reneging summaries, by default `"service"`.

        Returns
        -------
        str
            Summary label suitable for compact Mermaid node text.
        """
        if isinstance(spec, Distribution):
            return self._format_dist(spec, context=context)

        n_classes = len(spec.by_class)

        if context == "arrival":
            return f"Class-specific arrival distributions (n={n_classes})"
        if context == "renege":
            return f"Class-specific reneging distributions (n={n_classes})"
        return f"Class-specific service distributions (n={n_classes})"


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
    
        lines = ["graph TD"]

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
                        + "</br>"
                        + self._format_dist(dist, context="arrival")
                    )
                    lines.append(f'    {arrival_id}("{arr_label}")')

        # --- Activity nodes ---
        for activity in self.activities:
            node_id = make_node_id(activity.name)
            dist_info = self._summarise_distribution_spec(
                activity.service_distribution, context="service"
            )
            label = f"{activity.name}</br>{dist_info}"
            lines.append(f'    {node_id}["{label}"]')

        # --- Renege nodes ---
        for activity in self.activities:
            if activity.renege_distribution:
                node_id = make_node_id(activity.name)
                renege_id = f"Renege_{node_id}"
                renege_info = self._summarise_distribution_spec(
                    activity.renege_distribution,
                    context="renege",
                )
                lines.append(f' {renege_id}{{{{"Renege</br>{renege_info}"}}}}')

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
        # for transition in self.transitions:
        #     source_id = make_node_id(transition.source)
        #     target_id = (
        #         make_node_id(transition.target)
        #         if transition.target != "Exit"
        #         else "Exit"
        #     )
        #     if transition.probability == 1.0:
        #         lines.append(f"    {source_id} --> {target_id}")
        #     else:
        #         prob_label = f"{transition.probability:.0%}"
        #         lines.append(f"    {source_id} -->|{prob_label}| {target_id}")
        # -- -Modified to handle multi-class.  Need to view summary to make decision.
        for transition in self.transitions:
            source_id = make_node_id(transition.source)
            target_id = (
                make_node_id(transition.target)
                if transition.target != "Exit"
                else "Exit"
            )

            probability_label = self._format_probability_spec(
                transition.probability
            )

            if probability_label is None:
                lines.append(f" {source_id} --> {target_id}")
            else:
                lines.append(
                    f" {source_id} -->|{probability_label}| {target_id}"
                )

        #lines.append("```")
        return "\n".join(lines)


    def display_diagram(
            self, *, include_resources: bool = True, show_class_arrivals: bool = True
    ) -> None:
        """Display the Mermaid diagram in a notebook.

        Parameters
        ----------
        include_resources : bool, optional
            Whether to include resource nodes, by default `True`.

        """ 

        prefix = "```mermaid \n"
        postfix = " \n```"
        mermaid_code = self.to_mermaid(include_resources=include_resources, show_class_arrivals=show_class_arrivals)

        display(Markdown(prefix + mermaid_code + postfix))

    def save_diagram(
        self, filename: str, *, include_resources: bool = True, show_class_arrivals: bool = True
    ) -> None:
        """Save the Mermaid diagram to a file.

        Parameters
        ----------
        filename : str
            Output filename (e.g., "diagram.mmd").
        include_resources : bool, optional
            Whether to include resource nodes, by default `True`.

        """
        mermaid_code = self.to_mermaid(include_resources=include_resources, show_class_arrivals=show_class_arrivals)
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
                for class_name, class_label, dist in self._iter_distribution_spec(
                    activity.renege_distribution
                ):
                    records.append(
                        {
                            "Activity": activity.name,
                            "Phase": "Renege",
                            "Customer Class": class_name or "All",
                            "Customer Class Label": class_label or "All",
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
