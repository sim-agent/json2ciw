import ciw
import math
from typing import Dict, Any, List, Optional, Tuple
from .schema import ProcessModel
import statistics
import pandas as pd

from joblib import delayed, Parallel

class CiwConverter:
    def __init__(self, model):
        self.model = model

    def generate_params(self) -> dict:
        """
        Converts the agnostic ProcessModel into a dictionary of parameters 
        compatible with ciw.create_network(**params).
        """
        
        # 1. Map Activity Names to Integer Indices
        # Ciw networks are index-based (0, 1, 2...), but our JSON is name-based.
        # We assume the order in the list is the order of the nodes.
        node_map = {act.name: i for i, act in enumerate(self.model.activities)}
        n_nodes = len(self.model.activities)

        # 2. Initialize Lists for Ciw Arguments
        number_of_servers = []
        service_distributions = []
        arrival_distributions = []

        # 3. Iterate through Activities to build Node properties
        for act in self.model.activities:
            # -- Resources (Servers) --
            number_of_servers.append(act.resource.capacity)

            # -- Service Distribution (Mandatory) --
            service_distributions.append(self._make_ciw_dist(act.service_distribution))

            # -- Arrival Distribution (Optional) --
            if act.arrival_distribution:
                arrival_distributions.append(self._make_ciw_dist(act.arrival_distribution))
            else:
                # If no arrival distribution is specified in JSON, it means no external arrivals
                # None = old NoArrivals pre ciw v3
                arrival_distributions.append(None)

        # 4. Build Routing Matrix (Process Flow -> Probability Matrix)
        # Initialize an N x N matrix with 0.0
        routing = [[0.0] * n_nodes for _ in range(n_nodes)]
        
        for t in self.model.transitions:
            # We only care about transitions between internal nodes.
            # Transitions to "Exit" are implicit in Ciw (1.0 - sum(row)).
            if t.target != "Exit":
                # Validate that nodes exist (Pydantic validates types, but not logic across lists)
                if t.source not in node_map or t.target not in node_map:
                    raise ValueError(f"Transition references unknown node: {t.source} -> {t.target}")
                
                u_idx = node_map[t.source]
                v_idx = node_map[t.target]
                routing[u_idx][v_idx] = t.probability

        # 5. Return the Dictionary
        return {
            "number_of_servers": number_of_servers,
            "arrival_distributions": arrival_distributions,
            "service_distributions": service_distributions,
            "routing": routing
        }
    
    @staticmethod
    def _normal_moments_from_lognormal(m: float, v: float) -> Tuple[float, float]:
        """
        Calculate mu and sigma of the normal distribution underlying
        a lognormal with mean m and variance v.

        Note: TM added (from sim-tools) 0.6.0
        """
        phi = math.sqrt(v + m**2)
        mu = math.log(m**2 / phi)
        sigma = math.sqrt(math.log(phi**2 / m**2))
        return mu, sigma
    
    def _extract_std(self, dist_obj, params):
        """Help to extract standard deviation from parameters
        Handles, 'sd', 'std', 'var', 'stdev'."""

        sd_alias = ["sd", "std", "stdev"]

        # check for special case of var first
        if "var" in params:
            return math.sqrt(params["var"])

        # sd aliases
        for alias in sd_alias:
            if alias in params:
                return params[alias]
         
        # throw exception if sd not supplied
        err_msg = f"{dist_obj.name} is type {dist_obj.type} and requires a" \
            + "standard deviation param. None provided. Please review distributions."
        raise AttributeError(err_msg)
            

    def _make_ciw_dist(self, dist_obj):
        """Helper to convert Pydantic Distribution model to Ciw Object"""
        p = dist_obj.parameters
        
        if dist_obj.type == "exponential":
            if "rate" in p:
                return ciw.dists.Exponential(p["rate"])
            elif "mean" in p:
                return ciw.dists.Exponential(1/p["mean"])
        elif dist_obj.type == "triangular":
            return ciw.dists.Triangular(p["min"], p["mode"], p["max"])
        elif dist_obj.type == "uniform":
            return ciw.dists.Uniform(p["min"], p["max"])
        elif dist_obj.type == "deterministic":
             return ciw.dists.Deterministic(p["value"])
        # ADDED 0.6.0: Lognormal mapping with math conversion
        elif dist_obj.type == "lognormal":
             m = p["mean"]
             v = self._extract_std(dist_obj, p) ** 2
             mu, sigma = CiwConverter._normal_moments_from_lognormal(m, v)
             # 0.7.0 fixed param: "standard_deviation" should be "sd"
             return ciw.dists.Lognormal(mean=mu, sd=sigma)
        # ADDED 0.6.0: Gamma mapping
        elif dist_obj.type == "gamma":
             return ciw.dists.Gamma(shape=p["shape"], scale=p["scale"])
        # ADDED 0.7.0: Normal mapping
        elif dist_obj.type == "normal":
            # normal expects mean and sd            
            return ciw.dists.Normal(mean=p["mean"], sd=self._extract_std(dist_obj, p))
        else:
             raise ValueError(f"Unsupported distribution type for json2ciw: {dist_obj.type}")

def multiple_replications(
    network: ciw.Network,
    process_model: "ProcessModel",
    num_reps: int = 50,
    runtime: float = 1000.0,
    warmup: float = 0.0,
    n_jobs: int = -1,
) -> pd.DataFrame:
    """
    Run multiple replications of a Ciw simulation and collect performance metrics.

    Executes independent replications of a discrete event simulation, collecting
    node performance measures including arrivals, waiting times, service times,
    utilisation, and queue lengths. Activity and resource names from the process
    model are included in the output.

    Parameters
    ----------
    network : ciw.Network
        A configured Ciw network object defining the queueing system structure,
        service distributions, and routing.
    process_model : ProcessModel
        Pydantic model containing activity and resource metadata. Used to map
        node IDs to human-readable activity and resource names.
    num_reps : int, default 50
        Number of independent replications to run. Each replication uses a
        the replication number as a random seed.
    runtime : float, default 1000.0
        Simulation time horizon for each replication. Units match the time
        units used in service and arrival distributions.
    warmup : float, default 0.0
        Warmup period to exclude from statistics. Records with arrival times
        before this value are filtered out to reduce initialization bias.
    n_jobs: int, default -1
        Number of cores to use for parallel replications. Use -1 for all cores.

    Returns
    -------
    pd.DataFrame
        DataFrame with one row per node per replication containing:
        
        - rep : int
            Replication number (0-indexed)
        - node_id : int
            Ciw node identifier (1-indexed)
        - activity_name : str
            Name of the activity from process model
        - resource_name : str
            Name of the resource from process model
        - resource_capacity : int
            Number of servers at this node
        - arrivals : int
            Number of completed visits to this node
        - mean_wait : float
            Mean waiting time (queueing time before service)
        - mean_service : float
            Mean service time
        - utilisation : float
            Time-averaged server utilisation (fraction busy)
        - mean_Lq : float
            Time-averaged mean number of customers in queue

    Examples
    --------
    >>> process_model = ProcessModel.model_validate(json_data)
    >>> network = build_ciw_network(process_model)
    >>> df_raw = run_replications_general(
    ...     network, 
    ...     process_model, 
    ...     num_reps=100, 
    ...     runtime=1000
    ... )
    >>> summary = summarise_results(df_raw)
    """
    # Build a mapping from node_id (1-indexed) to activity/resource info
    node_metadata = {}
    for idx, activity in enumerate(process_model.activities):
        node_id = idx + 1  # Ciw uses 1-based indexing
        node_metadata[node_id] = {
            "activity_name": activity.name,
            "resource_name": activity.resource.name,
            "resource_capacity": activity.resource.capacity,
        }

    # Run independent replications in parallel, one per seed
    results = Parallel(n_jobs=n_jobs)(
        delayed(_single_run)(
            network=network,
            node_metadata=node_metadata,
            rep=rep,
            warmup=warmup,
            runtime=runtime,
        )
        for rep in range(num_reps)

    )
    # Flatten list-of-lists of row dicts
    records = [row for rep_rows in results for row in rep_rows]

    return pd.DataFrame.from_records(records)


def _single_run(
    network: ciw.Network,
    node_metadata: dict[int, Dict[str, Any]],
    rep: int = 0,
    warmup: float = 0.0,
    runtime: float = 1000.0,
):
    """
    Run a single Ciw replication and aggregate node-level performance metrics.

    Executes one independent replication of the queueing network, collecting
    time-averaged and per-customer measures for each transitive node. Results
    include arrivals, waiting times, service times, utilisation, and mean
    queue length, with node identifiers mapped to activity and resource
    metadata.

    Parameters
    ----------
    network : ciw.Network
        Configured Ciw network defining the queueing system structure,
        service and arrival processes, and routing.
    node_metadata : dict[int, dict]
        Mapping from Ciw node identifiers (1-indexed) to metadata dictionaries
        containing activity and resource information. Expected keys include
        ``"activity_name"``, ``"resource_name"``, and ``"resource_capacity"``.
    rep : int, optional
        Replication index used both as an identifier in the output and as the
        random seed for the simulation. Default is 0.
    warmup : float, optional
        Length of the warmup period to exclude from statistics. Records with
        arrival times strictly less than this value are filtered out to reduce
        initialization bias. Default is 0.0.
    runtime : float, optional
        Simulation time horizon for this replication. Units must match those
        used in the arrival and service time distributions. Default is 1000.0.

    Returns
    -------
    list[dict]
        List of row dictionaries, one per transitive node, containing:
        
        - ``"rep"`` : int
          Replication index.
        - ``"node_id"`` : int
          Ciw node identifier (1-indexed).
        - ``"activity_name"`` : str
          Human-readable activity name for this node.
        - ``"resource_name"`` : str
          Name of the resource associated with this node.
        - ``"resource_capacity"`` : int
          Number of servers at this node.
        - ``"arrivals"`` : int
          Number of completed visits to this node.
        - ``"mean_wait"`` : float
          Mean waiting time before service for completed customers.
        - ``"mean_service"`` : float
          Mean service time for completed customers.
        - ``"utilisation"`` : float
          Time-averaged server utilisation at this node, as a percentage.
        - ``"mean_Lq"`` : float
          Time-averaged mean number of customers in queue over the effective
          horizon ``runtime - warmup``.

    Notes
    -----
    The Ciw random number generators are seeded via ``ciw.seed(rep)`` to
    ensure reproducibility of each replication. Warmup filtering is applied
    using the arrival times of customer records, consistent with Ciw usage
    examples.[web:39][web:48]
    """
    ciw.seed(rep)
    Q = ciw.Simulation(network)
    Q.simulate_until_max_time(runtime)
    
    recs = Q.get_all_records()
    
    # Optional warmup filter. 
    # Ciw examples uses arrival times of entities
    if warmup > 0:
        recs = [r for r in recs if r.arrival_date >= warmup]
        
    rows = []
    # Loop over transitive nodes (service centres)
    for node in Q.transitive_nodes:
        node_id = node.id_number
        meta = node_metadata.get(node_id, {})

        node_recs = [r for r in recs if r.node == node_id]
        waits = [r.waiting_time for r in node_recs]
        services = [r.service_time for r in node_recs]

        arrivals = len(node_recs)
        mean_wait = statistics.mean(waits) if waits else 0.0
        mean_service = statistics.mean(services) if services else 0.0

        # Ciw server_utilisation gives time-averaged busy fraction
        util = node.server_utilisation

        # Time-weighted mean number in queue (Lq)
        horizon = runtime - warmup
        total_wait = sum(waits)
        mean_Lq = total_wait / horizon if horizon > 0 else 0.0

        rows.append({
            "rep": rep,
            "node_id": node_id,
            "activity_name": meta.get("activity_name", f"Node {node_id}"),
            "resource_name": meta.get("resource_name", "Unknown"),
            "resource_capacity": meta.get("resource_capacity", 0),
            "arrivals": arrivals,
            "mean_wait": mean_wait,
            "mean_service": mean_service,
            "utilisation": util * 100,
            "mean_Lq": mean_Lq,
            })
        
    return rows