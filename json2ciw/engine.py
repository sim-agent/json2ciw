"""Convert process models to Ciw inputs and run simulations."""

import math
import statistics
from typing import Any

import ciw
import pandas as pd
from joblib import Parallel, delayed

from .schema import ProcessModel


class CiwConverter:
    """Convert a process model into Ciw network parameters.

    Parameters
    ----------
    model : ProcessModel
        Process model to convert.

    Attributes
    ----------
    model : ProcessModel
        Process model to convert.

    """

    def __init__(self, model: ProcessModel) -> None:
        """Initialise the converter.

        Parameters
        ----------
        model : ProcessModel
            Process model to convert.

        """
        self.model = model

    def generate_params(self) -> dict[str, Any]:
        """Generate Ciw network parameters from the process model.

        Returns
        -------
        dict of str to Any
            Parameters compatible with `ciw.create_network`.

        """
        # Branch conversion depending on whether the model defines
        # customer classes. Single-class models keep the original list-based
        # Ciw inputs, while multi-class models use class-keyed dictionaries
        # for arrivals, services, routing, and reneging when needed.
        if getattr(self.model, "customer_classes", []):
            return self._generate_multiclass_params()
        return self._generate_singleclass_params()

    def _generate_singleclass_params(self) -> dict[str, Any]:
        """Generate single-class Ciw network parameters.

        Returns
        -------
        dict of str to Any
            Parameters compatible with `ciw.create_network`.

        """
        # 1. Map Activity Names to Integer Indices
        # Ciw networks are index-based (0, 1, 2...), but our JSON is
        # name-based. We assume the order in the list is the order of
        # the nodes.
        node_map = {act.name: i for i, act in enumerate(self.model.activities)}
        n_nodes = len(self.model.activities)

        # 2. Initialize Lists for Ciw Arguments
        number_of_servers = []
        service_distributions = []
        arrival_distributions = []
        reneging_time_distributions = []
        queue_capacities = []

        # 3. Track Whether Reneging Is Used Anywhere
        # If reneging is unused throughout the model, omit the Ciw
        # parameter entirely rather than sending a list of all None.
        has_reneging = any(
            act.renege_distribution is not None for act in self.model.activities
        )

        # 4. Iterate through Activities to build Node properties
        for act in self.model.activities:
            # -- Resources (Servers) --
            number_of_servers.append(act.resource.capacity)

            # -- Service Distribution (Mandatory) --
            service_distributions.append(
                self._make_ciw_dist(act.service_distribution)
            )

            # -- Arrival Distribution (Optional) --
            if act.arrival_distribution is not None:
                arrival_distributions.append(
                    self._make_ciw_dist(act.arrival_distribution)
                )
            else:
                # If no arrival distribution is specified in JSON, it means
                # no external arrivals.
                # None = old NoArrivals pre ciw v3.
                arrival_distributions.append(None)

            # -- Renege Distribution (Optional) --
            # Only build the list if reneging is used anywhere in the model.
            if has_reneging:
                if act.renege_distribution is not None:
                    reneging_time_distributions.append(
                        self._make_ciw_dist(act.renege_distribution)
                    )
                else:
                    reneging_time_distributions.append(None)


        # 5. Build Routing Matrix (Process Flow -> Probability Matrix)
        # Initialize an N x N matrix with 0.0.
        routing = [[0.0] * n_nodes for _ in range(n_nodes)]

        for t in self.model.transitions:
            # We only care about transitions between internal nodes.
            # Transitions to "Exit" are implicit in Ciw
            # (1.0 - sum(row)).
            if t.target != "Exit":
                # Validate that nodes exist (Pydantic validates types,
                # but not logic across lists).
                if t.source not in node_map or t.target not in node_map:
                    msg = (
                        "Transition references unknown node: "
                        f"{t.source} -> {t.target}"
                    )
                    raise ValueError(msg)

                u_idx = node_map[t.source]
                v_idx = node_map[t.target]
                routing[u_idx][v_idx] = t.probability

        params = {
            "number_of_servers": number_of_servers,
            "arrival_distributions": arrival_distributions,
            "service_distributions": service_distributions,
            "routing": routing,
        }

        # 6. Add Reneging Only If It Is Used
        # This keeps the generated parameter dictionary cleaner and avoids
        # specifying an unnecessary optional Ciw keyword.
        if has_reneging:
            params["reneging_time_distributions"] = (
                reneging_time_distributions
            )

        # 7. Queue capacities
        queue_capacities = [
            act.queue_capacity if act.queue_capacity is not None else math.inf
            for act in self.model.activities
        ]

        # only add if if scalar value included.
        if min(queue_capacities) < math.inf:
            params["queue_capacities"] = queue_capacities

        return params

    def _generate_multiclass_params(self) -> dict[str, Any]:
        """Generate multi-class Ciw network parameters.

        Returns
        -------
        dict of str to Any
            Parameters compatible with `ciw.create_network`.

        """
        # 1. Map Activity Names to Integer Indices
        # Ciw still indexes nodes internally, even when customer classes
        # are used.
        node_map = {act.name: i for i, act in enumerate(self.model.activities)}
        n_nodes = len(self.model.activities)

        # 2. Extract Customer Class Names
        # Use the model class names as the keys expected by
        # ciw.create_network.
        class_names = [c.name for c in self.model.customer_classes]

        # 3. Track Whether Reneging Is Used Anywhere
        # If reneging is unused throughout the model, omit the Ciw
        # parameter entirely rather than sending class-keyed lists of
        # all None.
        has_reneging = any(
            act.renege_distribution is not None for act in self.model.activities
        )

        # 4. Build Shared Node-Level Inputs
        # Resources remain shared across all customer classes for now.
        number_of_servers = [
            act.resource.capacity for act in self.model.activities
        ]

        # 5. Track if queue capacities are used otherwise infinite.
        queue_capacities = [
            act.queue_capacity if act.queue_capacity is not None else math.inf
            for act in self.model.activities
        ]
        
        # 6. Initialize Class-Keyed Ciw Arguments
        arrival_distributions = {}
        service_distributions = {}
        routing = {}

        # Renege distributions need to be class-keyed too when using a
        # multi-class model, otherwise Ciw raises a class consistency
        # error. For now the same reneging structure is given to each
        # class because reneging itself is still activity-level in the
        # schema.
        reneging_time_distributions = {} if has_reneging else None

        # 7. Build Class-Specific Arrival, Service, and Reneging Lists
        for class_name in class_names:
            arrival_distributions[class_name] = []
            service_distributions[class_name] = []

            # Build an independent routing matrix for this customer class.
            # Scalar probabilities apply to every class; class-specific
            # probability maps are resolved for this class.
            routing[class_name] = [[0.0] * n_nodes for _ in range(n_nodes)]

            for transition in self.model.transitions:
                # Ciw infers an Exit probability as one minus the sum of
                # the row's internal-node probabilities, so Exit is omitted
                # from the explicit routing matrix.
                if transition.target == "Exit":
                    continue

                if (
                    transition.source not in node_map
                    or transition.target not in node_map
                ):
                    msg = (
                        "Transition references unknown node: "
                        f"{transition.source} -> {transition.target}"
                    )
                    raise ValueError(msg)

                source_index = node_map[transition.source]
                target_index = node_map[transition.target]

                routing[class_name][source_index][target_index] = (
                    self.model._resolve_probability_spec(
                        transition.probability,
                        customer_class=class_name,
                    )
                )

            if has_reneging:
                reneging_time_distributions[class_name] = []

            for act in self.model.activities:
                # -- Arrival Distribution (Optional) --
                # Shared distributions apply to all classes. Class-specific
                # distributions are looked up by customer class name.
                arr_dist = self._resolve_distribution_spec(
                    act.arrival_distribution,
                    customer_class=class_name,
                )
                if arr_dist is not None:
                    arrival_distributions[class_name].append(
                        self._make_ciw_dist(arr_dist)
                    )
                else:
                    # If no arrival distribution is specified for this class
                    # at this node, it means no external arrivals.
                    arrival_distributions[class_name].append(None)

                # -- Service Distribution (Mandatory in Ciw) --
                # For multi-class networks, Ciw expects a service entry for
                # every class at every node. If a class-specific service
                # distribution is missing, use Deterministic(0.0) as the
                # neutral placeholder recommended in the Ciw docs.
                srv_dist = self._resolve_distribution_spec(
                    act.service_distribution,
                    customer_class=class_name,
                )
                if srv_dist is not None:
                    service_distributions[class_name].append(
                        self._make_ciw_dist(srv_dist)
                    )
                else:
                    service_distributions[class_name].append(
                        ciw.dists.Deterministic(value=0.0)
                    )

                # -- Renege Distribution (Optional but Class-Keyed) --
                # -- Renege Distribution (Optional and Class-Keyed) --
                # Shared distributions apply to all classes. Class-specific
                # distributions are looked up by customer class name.
                if has_reneging:
                    ren_dist = self._resolve_distribution_spec(
                        act.renege_distribution,
                        customer_class=class_name,
                    )
                    if ren_dist is not None:
                        reneging_time_distributions[class_name].append(
                            self._make_ciw_dist(ren_dist)
                        )
                    else:
                        reneging_time_distributions[class_name].append(None)

        params = {
            "number_of_servers": number_of_servers,
            "arrival_distributions": arrival_distributions,
            "service_distributions": service_distributions,
            "routing": routing,
        }

        # 8. Add Reneging Only If It Is Used
        # This keeps the generated parameter dictionary cleaner and avoids
        # specifying an unnecessary optional Ciw keyword.
        if has_reneging:
            params["reneging_time_distributions"] = (
                reneging_time_distributions
            )

        # 9. Add queue capacities only if it is used.
        if min(queue_capacities) < math.inf:
            params["queue_capacities"] = queue_capacities

        return params

    

    def _resolve_distribution_spec(
        self,
        spec: Any,
        customer_class: str,
    ) -> Any:
        """Resolve a distribution specification for one customer class.

        Parameters
        ----------
        spec : Any
            Distribution specification to resolve. This may be a shared
            `Distribution`, a class-specific mapping wrapper, or `None`.
        customer_class : str
            Customer class name.

        Returns
        -------
        Any
            Resolved distribution object for the customer class, or `None`
            if no class-specific distribution is defined.

        """
        # No specification means nothing to resolve.
        if spec is None:
            return None

        # Shared single distribution: applies to all customer classes.
        if hasattr(spec, "type") and hasattr(spec, "parameters"):
            return spec

        # Class-specific distribution mapping: look up by class name.
        if hasattr(spec, "by_class"):
            return spec.by_class.get(customer_class)

        # Fallback for unexpected types.
        return None

    @staticmethod
    def normal_moments_from_lognormal(
        mean: float, variance: float
    ) -> tuple[float, float]:
        """Convert lognormal moments to normal moments.

        Parameters
        ----------
        mean : float
            Mean of the lognormal distribution.
        variance : float
            Variance of the lognormal distribution.

        Returns
        -------
        tuple of float
            Mean and standard deviation of the underlying normal
            distribution.

        """
        phi = math.sqrt(variance + mean**2)
        mu = math.log(mean**2 / phi)
        sigma = math.sqrt(math.log(phi**2 / mean**2))
        return mu, sigma

    def _extract_std(self, dist_obj: Any, params: dict[str, Any]) -> float:
        """Extract a standard deviation value from distribution parameters.

        Parameters
        ----------
        dist_obj : Any
            Distribution object being converted.
        params : dict of str to Any
            Distribution parameters.

        Returns
        -------
        float
            Standard deviation value.

        """
        sd_alias = ["sd", "std", "stdev"]

        # check for special case of var first
        if "var" in params:
            return math.sqrt(params["var"])

        # sd aliases
        for alias in sd_alias:
            if alias in params:
                return params[alias]

        # throw exception if sd not supplied
        err_msg = (
            f"{dist_obj.name} is type {dist_obj.type} and requires a standard "
            "deviation param. None provided. Please review distributions."
        )
        raise AttributeError(err_msg)

    def _make_ciw_dist(self, dist_obj: Any) -> Any:
        """Convert a distribution model to a Ciw distribution.

        Parameters
        ----------
        dist_obj : Any
            Distribution object to convert.

        Returns
        -------
        Any
            Ciw distribution object.

        """
        p = dist_obj.parameters

        if dist_obj.type == "exponential":
            if "rate" in p:
                return ciw.dists.Exponential(p["rate"])
            if "mean" in p:
                return ciw.dists.Exponential(1 / p["mean"])
        if dist_obj.type == "triangular":
            return ciw.dists.Triangular(p["min"], p["mode"], p["max"])
        if dist_obj.type == "uniform":
            return ciw.dists.Uniform(p["min"], p["max"])
        if dist_obj.type == "deterministic":
            return ciw.dists.Deterministic(p["value"])
        if dist_obj.type == "lognormal":
            m = p["mean"]
            v = self._extract_std(dist_obj, p) ** 2
            mu, sigma = CiwConverter.normal_moments_from_lognormal(m, v)
            return ciw.dists.Lognormal(mean=mu, sd=sigma)
        if dist_obj.type == "gamma":
            return ciw.dists.Gamma(shape=p["shape"], scale=p["scale"])
        if dist_obj.type == "normal":
            # normal expects mean and sd
            return ciw.dists.Normal(
                mean=p["mean"], sd=self._extract_std(dist_obj, p)
            )

        msg = f"Unsupported distribution type for json2ciw: {dist_obj.type}"
        raise ValueError(msg)


def multiple_replications(
    network: ciw.Network,
    process_model: "ProcessModel",
    num_reps: int = 50,
    runtime: float = 1000.0,
    warmup: float = 0.0,
    n_jobs: int = -1,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run multiple simulation replications and collect node metrics.

    Parameters
    ----------
    network : ciw.Network
        Configured Ciw network.
    process_model : ProcessModel
        Process model used to map node metadata.
    num_reps : int, optional
        Number of replications to run, by default 50.
    runtime : float, optional
        Simulation time horizon, by default 1000.0.
    warmup : float, optional
        Warmup period to exclude, by default 0.0.
    n_jobs : int, optional
        Number of parallel jobs, by default -1.

    Returns
    -------
    tuple of pandas.DataFrame
        A tuple containing:

        - Node-level replication results
        - Source-to-destination transfer blocking results

        The transfer blocking DataFrame is empty when no queue capacities
        are configured in the process model.

    """

    has_queue_capacities = any(
        activity.queue_capacity is not None
        for activity in process_model.activities
    )

    # Build a mapping from node_id (1-indexed) to activity/resource info
    node_metadata = {}
    for idx, activity in enumerate(process_model.activities):
        node_id = idx + 1  # Ciw uses 1-based indexing
        node_metadata[node_id] = {
            "activity_name": activity.name,
            "resource_name": activity.resource.name,
            "resource_capacity": activity.resource.capacity,
            "has_reneging": activity.renege_distribution is not None,
            "queue_capacity": activity.queue_capacity,
            "has_queue_capacities": has_queue_capacities,
        }

    # Extract customer class names from the model.
    # If no classes are defined, the single-class behaviour is retained
    # and only overall rows are returned.
    customer_classes = [
        c.name for c in getattr(process_model, "customer_classes", [])
    ]

    # Run independent replications in parallel, one per seed
    results = Parallel(n_jobs=n_jobs)(
        delayed(_single_run)(
            network=network,
            node_metadata=node_metadata,
            customer_classes=customer_classes,
            has_queue_capacities=has_queue_capacities,
            rep=rep,
            warmup=warmup,
            runtime=runtime,
        )
        for rep in range(num_reps)
    )

    # NEW: Each replication returns a tuple:
    # (node_rows, transfer_blocking_rows).
    node_records = [
        row
        for rep_node_rows, _ in results
        for row in rep_node_rows
    ]

    transfer_records = [
        row
        for _, rep_transfer_rows in results
        for row in rep_transfer_rows
    ]

    node_results = pd.DataFrame.from_records(node_records)

    # Defining columns explicitly means that models with no queue
    # capacities return an empty but correctly structured DataFrame.
    transfer_result_columns = [
        "rep",
        "measure_scope",
        "customer_class",
        "source_node_id",
        "source_activity_name",
        "destination_node_id",
        "destination_activity_name",
        "n_transfers",
        "n_blocked",
        "blocking_probability",
        "mean_blocking_delay",
        "mean_blocking_delay_given_blocked",
    ]

    transfer_results = pd.DataFrame.from_records(
        transfer_records,
        columns=transfer_result_columns,
    )

    return node_results, transfer_results


def _build_result_row(
    recs_subset: list[Any],
    rep: int,
    node_id: int,
    meta: dict[str, Any],
    horizon: float,
    measure_scope: str,
    customer_class: str | None = None,
) -> dict[str, Any]:
    """Summarise a subset of records for one node and one scope.

    Parameters
    ----------
    recs_subset : list of Any
        Record subset to summarise.
    rep : int
        Replication index.
    node_id : int
        Node identifier.
    meta : dict of str to Any
        Node metadata dictionary.
    horizon : float
        Effective analysis horizon after warmup removal.
    measure_scope : str
        Scope of the summary, typically `"overall"` or `"customer_class"`.
    customer_class : str or None, optional
        Customer class name for class-specific summaries, by default `None`.

    Returns
    -------
    dict of str to Any
        One tidy-format summary row.

    """
    # Split records by outcome type.
    service_recs = [r for r in recs_subset if r.record_type == "service"]
    renege_recs = [r for r in recs_subset if r.record_type == "renege"]

    # Extract primitive metrics from records.
    service_waits = [r.waiting_time for r in service_recs]
    renege_waits = [r.waiting_time for r in renege_recs]
    all_waits = [r.waiting_time for r in recs_subset]
    service_times = [r.service_time for r in service_recs]

    blocked_time = [r.time_blocked for r in service_recs]

    n_service = len(service_recs)
    n_renege = len(renege_recs)
    n_total = n_service + n_renege

    mean_wait_service = (
        statistics.mean(service_waits) if service_waits else 0.0
    )
    mean_wait_renege = (
        statistics.mean(renege_waits) if renege_waits else 0.0
    )
    mean_wait_all = statistics.mean(all_waits) if all_waits else 0.0
    mean_service = statistics.mean(service_times) if service_times else 0.0

    # Queue-length contribution can be computed from the same waiting-time
    # identity as the overall metric, just using the filtered record subset.
    total_wait_all = sum(all_waits)
    mean_lq = total_wait_all / horizon if horizon > 0 else 0.0

    # Renege rate is useful for downstream summaries if reneging is present.
    renege_rate = n_renege / n_total if n_total > 0 else 0.0

    row = {
        "rep": rep,
        "node_id": node_id,
        "activity_name": meta.get("activity_name", f"Node {node_id}"),
        "resource_name": meta.get("resource_name", "Unknown"),
        "resource_capacity": meta.get("resource_capacity", 0),
        "measure_scope": measure_scope,
        "customer_class": customer_class if customer_class is not None else "All",
        "n_service": n_service,
        "mean_wait": mean_wait_service,
        "mean_service": mean_service,
        "mean_Lq": mean_lq,
    }

    # Utilisation is only available at node level from Ciw, so keep it on
    # the overall row only rather than implying a class-specific split.
    if measure_scope == "overall":
        row["utilisation"] = meta.get("utilisation", 0.0)
    else:
        row["utilisation"] = None

    # Add reneging metrics only for nodes that can renege.
    if meta.get("has_reneging", False):
        row.update(
            {
                "n_renege": n_renege,
                "renege_rate": renege_rate,
                "mean_wait_renege": mean_wait_renege,
                "mean_wait_all": mean_wait_all,
            }
        )

    return row

def _build_transfer_blocking_rows(
    service_recs: list[Any],
    rep: int,
    source_node_id: int,
    node_metadata: dict[int, dict[str, Any]],
    measure_scope: str,
    customer_class: str | None = None,
) -> list[dict[str, Any]]:
    """Summarise blocking by source-to-destination transfer.

    One row is returned for each downstream node actually reached by
    customers completing service at the source node.

    Parameters
    ----------
    service_recs : list of Any
        Service records for one source node and one measurement scope.
    rep : int
        Replication index.
    source_node_id : int
        Identifier of the source node where service was completed.
    node_metadata : dict of int to dict of str to Any
        Mapping from node identifiers to node metadata.
    measure_scope : str
        Scope of the summary, typically `"overall"` or `"customer_class"`.
    customer_class : str or None, optional
        Customer class name for class-specific summaries, by default `None`.

    Returns
    -------
    list of dict of str to Any
        One transfer-blocking result row per source-to-destination pair.

    Notes:
    ------
    TM added v0.12.0

    """
    # Customers with destination -1 leave the system. They cannot be
    # blocked on a transfer to a downstream internal node, so exclude them.
    internal_transfer_recs = [
        r for r in service_recs if r.destination != -1
    ]

    # Identify the internal downstream nodes reached by at least one
    # completed service record in this replication and scope.
    destination_node_ids = sorted(
        {r.destination for r in internal_transfer_recs}
    )

    source_meta = node_metadata.get(source_node_id, {})
    rows = []

    for destination_node_id in destination_node_ids:
        # Records for one directed source -> destination transfer.
        transfer_recs = [
            r
            for r in internal_transfer_recs
            if r.destination == destination_node_id
        ]

        # A positive time_blocked value means the customer completed service
        # at the source but could not transfer immediately because the
        # receiving node had no available queue capacity.
        blocked_recs = [
            r for r in transfer_recs if r.time_blocked > 0
        ]

        n_transfers = len(transfer_recs)
        n_blocked = len(blocked_recs)

        # Unblocked transfers contribute zero delay. Summing only positive
        # times is therefore equivalent to summing all transfer blocking
        # times, while also avoiding any non-finite values defensively.
        total_blocking_delay = sum(
            r.time_blocked for r in blocked_recs
        )

        # Average blocking delay across every customer attempting this
        # particular transfer. Customers transferred immediately contribute
        # zero to this mean.
        mean_blocking_delay = (
            total_blocking_delay / n_transfers
            if n_transfers > 0
            else 0.0
        )

        # Average delay only among customers whose transfer was blocked.
        mean_blocking_delay_given_blocked = (
            total_blocking_delay / n_blocked
            if n_blocked > 0
            else 0.0
        )

        # Probability that a customer needing this specific transfer could
        # not move immediately to the downstream node.
        blocking_probability = (
            n_blocked / n_transfers
            if n_transfers > 0
            else 0.0
        )

        destination_meta = node_metadata.get(destination_node_id, {})

        rows.append(
            {
                "rep": rep,
                "measure_scope": measure_scope,
                "customer_class": (
                    customer_class
                    if customer_class is not None
                    else "All"
                ),
                "source_node_id": source_node_id,
                "source_activity_name": source_meta.get(
                    "activity_name",
                    f"Node {source_node_id}",
                ),
                "destination_node_id": destination_node_id,
                "destination_activity_name": destination_meta.get(
                    "activity_name",
                    f"Node {destination_node_id}",
                ),
                "n_transfers": n_transfers,
                "n_blocked": n_blocked,
                "blocking_probability": blocking_probability,
                "mean_blocking_delay": mean_blocking_delay,
                "mean_blocking_delay_given_blocked": (
                    mean_blocking_delay_given_blocked
                ),
            }
        )

    return rows


def _single_run(
    network: ciw.Network,
    node_metadata: dict[int, dict[str, Any]],
    customer_classes: list[str] | None = None,
    has_queue_capacities: bool = False,
    rep: int = 0,
    warmup: float = 0.0,
    runtime: float = 1000.0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run a single simulation replication and aggregate node metrics.


    Parameters
    ----------
    network : ciw.Network
        Configured Ciw network.
    node_metadata : dict of int to dict of str to Any
        Mapping from node identifiers to metadata.
    customer_classes : list of str or None, optional
        Customer class names defined in the model. If empty or `None`,
        only overall node summaries are returned.
    has_queue_capacities : bool, optional
        Whether at least one activity in the model has a finite queue
        capacity. When `True`, source-to-destination blocking results are
        also calculated, by default `False`.
    rep : int, optional
        Replication index and random seed, by default 0.
    warmup : float, optional
        Warmup period to exclude, by default 0.0.
    runtime : float, optional
        Simulation time horizon, by default 1000.0.


    Returns
    -------
    tuple of list of dict
        Tidy-format node-level result rows and transfer-level blocking
        result rows for the replication.


    Notes
    -----
    The Ciw random number generators are seeded via `ciw.seed(rep)` to
    ensure reproducibility of each replication. Warmup filtering is applied
    using the arrival times of customer records.


    """
    ciw.seed(rep)
    sim = ciw.Simulation(network)
    sim.simulate_until_max_time(runtime)


    # Pull service, reneging and arrival rejection records, since those are the
    # outcomes used by the current summary functions.
    # TM note: in ciw rejection records are produced when an arrival finds a node's queue at capacity.
    recs = sim.get_all_records(only=["service", "renege", "rejection"])

    # Warmup filter
    # TM note - is there a better way to do this in ciw?
    if warmup > 0:
        recs = [r for r in recs if r.arrival_date >= warmup]


    # ADDED v0.12.0: node-level and transfer-level results 
    # transfer results are used for blocking metrics 
    node_rows = []
    transfer_rows = []

    horizon = runtime - warmup
    customer_classes = customer_classes or []

    for node in sim.transitive_nodes:
        node_id = node.id_number
        meta = node_metadata.get(node_id, {}).copy()

        # Node-level utilisation comes directly from Ciw and should be
        # attached to the overall row only.
        meta["utilisation"] = node.server_utilisation * 100

        # First collect all records for this node.
        node_recs = [r for r in recs if r.node == node_id]

        # Always append the overall node summary.
        node_rows.append(
            _build_result_row(
                recs_subset=node_recs,
                rep=rep,
                node_id=node_id,
                meta=meta,
                horizon=horizon,
                measure_scope="overall",
                customer_class=None,
            )
        )

        # ADDED v0.12.0: If model has queue capacities
        # then calculate rejection and blocking metrics.
        if has_queue_capacities:
            service_recs = [
                r
                for r in node_recs
                if r.record_type == "service"
            ]

            transfer_rows.extend(
                _build_transfer_blocking_rows(
                    service_recs=service_recs,
                    rep=rep,
                    source_node_id=node_id,
                    node_metadata=node_metadata,
                    measure_scope="overall",
                    customer_class=None,
                )
            )


        # If customer classes are defined, also append one row per class.
        # This includes zero rows for classes that never visit a node,
        # which is useful for validating routing and service structure.
        for class_name in customer_classes:
            class_recs = [
                r for r in node_recs if r.customer_class == class_name
            ]


            node_rows.append(
                _build_result_row(
                    recs_subset=class_recs,
                    rep=rep,
                    node_id=node_id,
                    meta=meta,
                    horizon=horizon,
                    measure_scope="customer_class",
                    customer_class=class_name,
                )
            )


            # NEW: Add the equivalent source-to-destination breakdown for
            # this customer class. This uses only class-specific service
            # records because blocking occurs after service completion.
            if has_queue_capacities:
                class_service_recs = [
                    r
                    for r in class_recs
                    if r.record_type == "service"
                ]

                transfer_rows.extend(
                    _build_transfer_blocking_rows(
                        service_recs=class_service_recs,
                        rep=rep,
                        source_node_id=node_id,
                        node_metadata=node_metadata,
                        measure_scope="customer_class",
                        customer_class=class_name,
                    )
                )


    # CHANGED v0.12.0: Return both result types. multiple_replications will flatten
    # these independently into node_results and transfer_results DataFrames.
    return node_rows, transfer_rows


def _single_run_old(
    network: ciw.Network,
    node_metadata: dict[int, dict[str, Any]],
    customer_classes: list[str] | None = None,
    rep: int = 0,
    warmup: float = 0.0,
    runtime: float = 1000.0,
) -> list[dict[str, Any]]:
    """Run a single simulation replication and aggregate node metrics.

    Parameters
    ----------
    network : ciw.Network
        Configured Ciw network.
    node_metadata : dict of int to dict of str to Any
        Mapping from node identifiers to metadata.
    customer_classes : list of str or None, optional
        Customer class names defined in the model. If empty or `None`,
        only overall node summaries are returned.
    rep : int, optional
        Replication index and random seed, by default 0.
    warmup : float, optional
        Warmup period to exclude, by default 0.0.
    runtime : float, optional
        Simulation time horizon, by default 1000.0.

    Returns
    -------
    list of dict of str to Any
        Tidy-format result rows for the replication.

    Notes
    -----
    The Ciw random number generators are seeded via `ciw.seed(rep)` to
    ensure reproducibility of each replication. Warmup filtering is applied
    using the arrival times of customer records.

    """
    ciw.seed(rep)
    sim = ciw.Simulation(network)
    sim.simulate_until_max_time(runtime)

    # Pull service, reneging and arrival rejection records, since those are the
    # outcomes used by the current summary functions.
    # TM note: in ciw rejection records are produced when an arrival finds a node's queue at capacity.
    recs = sim.get_all_records(only=["service", "renege", "rejection"])

    # Warmup filter
    # TM note - is there a better way to do this in ciw?
    if warmup > 0:
        recs = [r for r in recs if r.arrival_date >= warmup]

    rows = []
    horizon = runtime - warmup
    customer_classes = customer_classes or []

    for node in sim.transitive_nodes:
        node_id = node.id_number
        meta = node_metadata.get(node_id, {}).copy()

        # Node-level utilisation comes directly from Ciw and should be
        # attached to the overall row only.
        meta["utilisation"] = node.server_utilisation * 100

        # First collect all records for this node.
        node_recs = [r for r in recs if r.node == node_id]

        # Always append the overall node summary.
        rows.append(
            _build_result_row(
                recs_subset=node_recs,
                rep=rep,
                node_id=node_id,
                meta=meta,
                horizon=horizon,
                measure_scope="overall",
                customer_class=None,
            )
        )

        # If customer classes are defined, also append one row per class.
        # This includes zero rows for classes that never visit a node,
        # which is useful for validating routing and service structure.
        for class_name in customer_classes:
            class_recs = [
                r for r in node_recs if r.customer_class == class_name
            ]

            rows.append(
                _build_result_row(
                    recs_subset=class_recs,
                    rep=rep,
                    node_id=node_id,
                    meta=meta,
                    horizon=horizon,
                    measure_scope="customer_class",
                    customer_class=class_name,
                )
            )

    return rows
