import ciw
from typing import Dict, Any, List, Optional
from .schema import ProcessModel
import statistics
import pandas as pd

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

    def _make_ciw_dist(self, dist_obj):
        """Helper to convert Pydantic Distribution model to Ciw Object"""
        p = dist_obj.parameters
        
        if dist_obj.type == "exponential":
            return ciw.dists.Exponential(1/p["rate"])
        elif dist_obj.type == "triangular":
            return ciw.dists.Triangular(p["min"], p["mode"], p["max"])
        elif dist_obj.type == "uniform":
            return ciw.dists.Uniform(p["min"], p["max"])
        elif dist_obj.type == "deterministic":
             return ciw.dists.Deterministic(p["value"])
        # TO DO: Add more mappings as needed (Lognormal, Gamma, etc.)
        else:
             raise ValueError(f"Unsupported distribution type for Ciw: {dist_obj.type}")

def multiple_replications(
    network: ciw.Network,
    process_model: "ProcessModel",
    num_reps: int = 50,
    runtime: float = 1000.0,
    warmup: float = 0.0
) -> pd.DataFrame:
    """
    Run multiple replications of a Ciw simulation and collect performance metrics.

    Executes independent replications of a discrete event simulation, collecting
    per-node performance measures including arrivals, waiting times, service times,
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

    records = []

    for rep in range(num_reps):
        ciw.seed(rep)
        Q = ciw.Simulation(network)
        Q.simulate_until_max_time(runtime)

        recs = Q.get_all_records()
        
        # Optional warmup filter
        if warmup > 0:
            recs = [r for r in recs if r.arrival_date >= warmup]

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

            records.append({
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

    return pd.DataFrame.from_records(records)
