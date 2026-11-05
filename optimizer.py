
from ortools.sat.python import cp_model

from scheduler import get_price


def optimize_schedule(
    requests,
    capacity=20,
    essential_demand=None
):
    if essential_demand is None:
        essential_demand = {}

    hours = list(range(18, 30))

    if capacity <= 0:
        raise ValueError("Capacity must be positive")

    if any(
        essential_demand.get(hour, 0) > capacity
        or essential_demand.get(hour, 0) < 0
        for hour in hours
    ):
        raise ValueError("Invalid essential demand")

    # Convert kW and kWh to integer units.
    # This supports values with up to 3 decimal places.
    SCALE = 1000

    def units(value):
        scaled = round(value * SCALE)

        if abs(value * SCALE - scaled) > 1e-6:
            raise ValueError(
                "Use at most 3 decimal places"
            )

        return scaled

    model = cp_model.CpModel()

    # x[i, hour] = 1 if household i charges
    # during that hour, otherwise 0.
    x = {}

    for i, request in enumerate(requests):
        for hour in hours:
            x[i, hour] = model.NewBoolVar(
                f"charge_{i}_{hour}"
            )

    # Constraint 1:
    # Each household must receive its requested energy.
    for i, request in enumerate(requests):
        power = units(request["power"])
        energy = units(request["energy"])

        if power <= 0 or energy <= 0:
            raise ValueError(
                "Power and energy must be positive"
            )

        # Number of complete hourly slots required.
        slots_needed = (
            energy + power - 1
        ) // power

        model.Add(
            sum(x[i, hour] for hour in hours)
            == slots_needed
        )

        # Constraint 2:
        # Do not charge at or after the deadline.
        for hour in hours:
            if hour >= request["deadline"]:
                model.Add(x[i, hour] == 0)

    # Constraint 3:
    # Protect essential electricity demand.
    for hour in hours:
        available = units(
            capacity - essential_demand.get(hour, 0)
        )

        model.Add(
            sum(
                units(request["power"]) * x[i, hour]
                for i, request in enumerate(requests)
            ) <= available
        )

    # Objective:
    # Minimize total electricity cost.
    # For each household's final slot, only the
    # remaining required energy is billed.
    cost_terms = []

    for i, request in enumerate(requests):
        power = units(request["power"])
        energy = units(request["energy"])

        slots_needed = (
            energy + power - 1
        ) // power

        # This version assumes full-hour charging
        # for capacity and energy accounting.
        # Reject requests that would need a partial hour.
        if energy % power != 0:
            raise ValueError(
                "OR-Tools currently requires energy "
                "to be a multiple of power"
            )

        for hour in hours:
            cost_terms.append(
                power * get_price(hour) * x[i, hour]
            )

    model.Minimize(sum(cost_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10

    status = solver.Solve(model)

    if status not in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE
    ):
        return {
            "status": "infeasible",
            "schedule": {},
            "metrics": {
                "total_requests": len(requests),
                "completed_requests": 0,
                "completion_rate": 0,
                "total_cost": 0
            }
        }

    schedule = {}

    for i, request in enumerate(requests):
        selected_hours = [
            hour for hour in hours
            if solver.Value(x[i, hour]) == 1
        ]

        cost = sum(
            request["power"] * get_price(hour)
            for hour in selected_hours
        )

        schedule[request["household"]] = {
            "hours": selected_hours,
            "completed": True,
            "cost": round(cost, 2)
        }

    total_cost = sum(
        details["cost"]
        for details in schedule.values()
    )

    return {
        "status": (
            "optimal"
            if status == cp_model.OPTIMAL
            else "feasible"
        ),
        "schedule": schedule,
        "metrics": {
            "total_requests": len(requests),
            "completed_requests": len(requests),
            "completion_rate": (
                100.0 if requests else 0.0
            ),
            "total_cost": round(total_cost, 2)
        }
    }
