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

    def generate_params(self) -> dict:
        """Generate Ciw network parameters from the process model.

        Returns
        -------
        dict of str to Any
            Parameters compatible with `ciw.create_network`.

        """
        # 1. Map Activity Names to Integer Indices
        # Ciw networks are index-based (0, 1, 2...), but our JSON is name-based
        # We assume the order in the list is the order of the nodes.
        node_map = {act.name: i for i, act in enumerate(self.model.activities)}
        n_nodes = len(self.model.activities)

        # 2. Initialize Lists for Ciw Arguments
        number_of_servers = []
        service_distributions = []
        arrival_distributions = []
        reneging_time_distributions = []

        # 3. Iterate through Activities to build Node properties
        for act in self.model.activities:
            # -- Resources (Servers) --
            number_of_servers.append(act.resource.capacity)

            # -- Service Distribution (Mandatory) --
            service_distributions.append(
                self._make_ciw_dist(act.service_distribution)
            )

            # -- Arrival Distribution (Optional) --
            if act.arrival_distribution:
                arrival_distributions.append(
                    self._make_ciw_dist(act.arrival_distribution)
                )
            else:
                # If no arrival distribution is specified in JSON, it means no
                # external arrivals
                # None = old NoArrivals pre ciw v3
                arrival_distributions.append(None)

            # -- Renege Distribution (Optional) --
            if act.renege_distribution:
                reneging_time_distributions.append(
                    self._make_ciw_dist(act.renege_distribution)
                )
            else:
                reneging_time_distributions.append(None)

        # 4. Build Routing Matrix (Process Flow -> Probability Matrix)
        # Initialize an N x N matrix with 0.0
        routing = [[0.0] * n_nodes for _ in range(n_nodes)]

        for t in self.model.transitions:
            # We only care about transitions between internal nodes.
            # Transitions to "Exit" are implicit in Ciw (1.0 - sum(row)).
            if t.target != "Exit":
                # Validate that nodes exist (Pydantic validates types, but not
                # logic across lists)
                if t.source not in node_map or t.target not in node_map:
                    msg = (
                        "Transition references unknown node: "
                        f"{t.source} -> {t.target}"
                    )
                    raise ValueError(msg)

                u_idx = node_map[t.source]
                v_idx = node_map[t.target]
                routing[u_idx][v_idx] = t.probability

        return {
            "number_of_servers": number_of_servers,
            "arrival_distributions": arrival_distributions,
            "service_distributions": service_distributions,
            "reneging_time_distributions": reneging_time_distributions,
            "routing": routing,
        }

    @staticmethod
    def normal_moments_from_lognormal(
        mean: float, variance: float
    ) -> tuple[float, float]:
        """Convert lognormal moments to normal moments.

        TM added (from sim-tools) 0.6.0.

        Parameters
        ----------
        mean : float
            Mean of the lognormal distribution.
        variance : float
            Variance of the lognormal distribution.

        Returns
        -------
        tuple of float
            Mean and standard deviation of the underlying normal distribution.

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
        # ADDED 0.6.0: Lognormal mapping with math conversion
        if dist_obj.type == "lognormal":
            m = p["mean"]
            v = self._extract_std(dist_obj, p) ** 2
            mu, sigma = CiwConverter.normal_moments_from_lognormal(m, v)
            # 0.7.0 fixed param: "standard_deviation" should be "sd"
            return ciw.dists.Lognormal(mean=mu, sd=sigma)
        # ADDED 0.6.0: Gamma mapping
        if dist_obj.type == "gamma":
            return ciw.dists.Gamma(shape=p["shape"], scale=p["scale"])
        # ADDED 0.7.0: Normal mapping
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
) -> pd.DataFrame:
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
    pandas.DataFrame
        One row per node per replication.

    """
    # Build a mapping from node_id (1-indexed) to activity/resource info
    node_metadata = {}
    for idx, activity in enumerate(process_model.activities):
        node_id = idx + 1  # Ciw uses 1-based indexing
        node_metadata[node_id] = {
            "activity_name": activity.name,
            "resource_name": activity.resource.name,
            "resource_capacity": activity.resource.capacity,
            "has_reneging": activity.renege_distribution is not None,
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
    node_metadata: dict[int, dict[str, Any]],
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
    rep : int, optional
        Replication index and random seed, by default 0.
    warmup : float, optional
        Warmup period to exclude, by default 0.0.
    runtime : float, optional
        Simulation time horizon, by default 1000.0.

    Returns
    -------
    list of dict of str to Any
        One result row per transitive node.

    Notes
    -----
    The Ciw random number generators are seeded via `ciw.seed(rep)` to
    ensure reproducibility of each replication. Warmup filtering is applied
    using the arrival times of customer records. This potentially needs
    modifying at some point.

    """
    ciw.seed(rep)
    sim = ciw.Simulation(network)
    sim.simulate_until_max_time(runtime)

    recs = sim.get_all_records(only=["service", "renege"])

    # Warmup filter
    if warmup > 0:
        recs = [r for r in recs if r.arrival_date >= warmup]

    rows = []
    horizon = runtime - warmup

    for node in sim.transitive_nodes:
        node_id = node.id_number
        meta = node_metadata.get(node_id, {})

        node_recs = [r for r in recs if r.node == node_id]
        service_recs = [r for r in node_recs if r.record_type == "service"]
        renege_recs = [r for r in node_recs if r.record_type == "renege"]

        service_waits = [r.waiting_time for r in service_recs]
        renege_waits = [r.waiting_time for r in renege_recs]
        all_waits = [r.waiting_time for r in node_recs]

        service_times = [r.service_time for r in service_recs]

        n_service = len(service_recs)
        n_renege = len(renege_recs)

        mean_wait_service = (
            statistics.mean(service_waits) if service_waits else 0.0
        )
        mean_wait_renege = (
            statistics.mean(renege_waits) if renege_waits else 0.0
        )
        mean_wait_all = statistics.mean(all_waits) if all_waits else 0.0
        mean_service = statistics.mean(service_times) if service_times else 0.0

        util = node.server_utilisation

        total_wait_all = sum(all_waits)
        mean_lq = total_wait_all / horizon if horizon > 0 else 0.0

        row = {
            "rep": rep,
            "node_id": node_id,
            "activity_name": meta.get("activity_name", f"Node {node_id}"),
            "resource_name": meta.get("resource_name", "Unknown"),
            "resource_capacity": meta.get("resource_capacity", 0),
            "n_service": n_service,
            "mean_wait": mean_wait_service,
            "mean_service": mean_service,
            "utilisation": util * 100,
            "mean_Lq": mean_lq,
        }

        # if add in renege wait if needed.
        if meta.get("has_reneging", False):
            row.update(
                {
                    "n_renege": n_renege,
                    "mean_wait_renege": mean_wait_renege,
                    "mean_wait_all": mean_wait_all,
                }
            )

        rows.append(row)

    return rows
