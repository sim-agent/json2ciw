import ciw
from typing import Dict, Any, List, Optional

def create_ciw_network(json_data: Dict[str, Any]) -> ciw.network.Network:
    """
    Parses a JSON dictionary describing a discrete event simulation (DES) process 
    and generates a corresponding Ciw Network object.

    This function maps activity definitions, resource constraints, and routing 
    logic from a simplified JSON schema to Ciw's internal configuration format.

    Parameters
    ----------
    json_data : Dict[str, Any]
        A dictionary containing the simulation process definition. It is expected 
        to follow a specific schema with keys: 'process', which contains 
        'activities', 'transitions', and 'inter_arrival_time'.

    Returns
    -------
    ciw.network.Network
        An initialized Ciw Network object ready for simulation.

    Notes
    -----
    - **Arrivals**: Assumed to occur only at the first activity listed in the 
      'activities' list.
    - **Resources**: Capacity is determined by the 'number' attribute in the 
      resource definition. Defaults to 1 if 'number' is missing. Infinite 
      capacity is supported via 'type': 'infinite'.
    - **Exits**: Routing probabilities that sum to less than 1.0 imply a 
      probability of exiting the system. Explicit transitions to "Exit" are 
      handled by omitting them from the routing matrix.
    """
    process = json_data.get('process', {})
    activities = process.get('activities', [])
    transitions = process.get('transitions', [])
    arrival_config = process.get('inter_arrival_time', {})

    # 1. Map Activity Names to Node Indices (0, 1, 2...)
    # Ciw nodes are 1-indexed in the library's internal logic, but lists are 0-indexed.
    name_to_index = {act['name']: i for i, act in enumerate(activities)}
    num_nodes = len(activities)

    # 2. Initialize Ciw Configuration Lists
    arrival_distributions = [None] * num_nodes
    service_distributions = [None] * num_nodes
    number_of_servers = [1] * num_nodes  # Default capacity 1
    routing = [[0.0] * num_nodes for _ in range(num_nodes)]

    # 3. Configure Arrivals
    # Assumption: Arrivals enter the system at the first activity defined
    # Ciw uses 'None' or 'ciw.dists.NoArrivals()' for nodes with no external arrivals.
    entry_node_idx = 0
    arr_dist = arrival_config.get('distribution')
    arr_params = arrival_config.get('parameters', {})

    if arr_dist == 'exponential':
        # ciw.dists.Exponential takes 1 / 'rate'
        # Note THIS NEEDS TO BE MAMAGED IN SOME WAY AS THE AUTHORS COULD SPECIFY rate or inter-arrival time.
        arrival_distributions[entry_node_idx] = ciw.dists.Exponential(rate=1/arr_params['rate'])
    else:
        # Placeholder for other arrival distributions if needed
        arrival_distributions[entry_node_idx] = ciw.dists.Deterministic(0)

    # 4. Configure Service Distributions and Servers
    for i, activity in enumerate(activities):
        # -- Service Distribution --
        dist_type = activity.get('distribution')
        params = activity.get('parameters', {})

        if dist_type == 'exponential':
            # JSON params might use 'rate' or 'mean'. Ciw Exponential uses rate (lambda)
            # If JSON provides mean, rate = 1.0 / mean. Assuming JSON matches Ciw 'rate' here.
            rate = params.get('rate', 1.0)
            service_distributions[i] = ciw.dists.Exponential(rate=rate)
            print("Createed an exponential")
            print(service_distributions[i])

        elif dist_type == 'triangular':
            # Ciw (via Python random) typically uses (low, high, mode)
            # JSON provides {min, mode, max}
            service_distributions[i] = ciw.dists.Triangular(
                lower=params['min'],
                upper=params['max'],
                mode=params['mode']
            )
            print("Created an triangular")
            print(service_distributions[i])


        elif dist_type == 'uniform':
            service_distributions[i] = ciw.dists.Uniform(
                lower=params['min'],
                upper=params['max']
            )
            print("Created an uniform")
            print(service_distributions[i])


        elif dist_type == 'deterministic':
            service_distributions[i] = ciw.dists.Deterministic(value=params['value'])
            print("Created an deterministic")
            print(service_distributions[i])


        # -- Servers / Resources --
        # The JSON example lacks a 'capacity' field for resources.
        # We check for it, otherwise default to 1.
        resource = activity.get('resource', {})
        capacity = resource.get('number', 1)
        # If resource type is 'infinite', set servers to float('inf')
        if resource.get('type') == 'infinite':
            capacity = float('inf')

        number_of_servers[i] = capacity

    # 5. Configure Routing Matrix
    for trans in transitions:
        from_node = trans.get('from')
        to_node = trans.get('to')
        prob = trans.get('probability', 0.0)

        if from_node in name_to_index:
            row_idx = name_to_index[from_node]

            # If destination is another node, fill the matrix
            if to_node in name_to_index:
                col_idx = name_to_index[to_node]
                routing[row_idx][col_idx] = prob

            # If destination is "Exit", we do nothing.
            # In Ciw, if row sum < 1.0, the remainder is the probability of exiting.
            elif to_node == "Exit":
                pass

    # 6. Create Network
    model = ciw.create_network(
        arrival_distributions=arrival_distributions,
        service_distributions=service_distributions,
        number_of_servers=number_of_servers,
        routing=routing
    )

    return model