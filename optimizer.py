
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
    solver.parameters.max_time_in_seconds = 3

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


def optimize_fair_schedule(
    requests,
    capacity=20,
    essential_demand=None
):
    if essential_demand is None:
        essential_demand = {}

    hours = list(range(18, 30))
    scale = 1000

    def units(value):
        result = round(value * scale)
        if abs(value * scale - result) > 1e-6:
            raise ValueError("Use at most 3 decimal places")
        return result

    if capacity <= 0:
        raise ValueError("Capacity must be positive")

    if any(
        essential_demand.get(h, 0) < 0
        or essential_demand.get(h, 0) > capacity
        for h in hours
    ):
        raise ValueError("Invalid essential demand")

    if len({r["household"] for r in requests}) != len(requests):
        raise ValueError("Duplicate household identifiers")

    model = cp_model.CpModel()

    x = {}
    completed = {}
    allocated_slots = {}
    required_slots = {}

    for i, request in enumerate(requests):
        energy = units(request["energy"])
        power = units(request["power"])

        if energy <= 0 or power <= 0:
            raise ValueError("Energy and power must be positive")

        if energy % power != 0:
            raise ValueError(
                "Energy must be a multiple of power"
            )

        slots = energy // power
        required_slots[i] = slots

        for hour in hours:
            x[i, hour] = model.NewBoolVar(
                f"charge_{i}_{hour}"
            )

            if hour >= request["deadline"]:
                model.Add(x[i, hour] == 0)

        allocated_slots[i] = sum(
            x[i, hour] for hour in hours
        )

        model.Add(allocated_slots[i] <= slots)

        completed[i] = model.NewBoolVar(
            f"completed_{i}"
        )

        model.Add(
            allocated_slots[i] == slots
        ).OnlyEnforceIf(completed[i])

        model.Add(
            allocated_slots[i] <= slots - 1
        ).OnlyEnforceIf(completed[i].Not())

    # Reserve capacity for essential electricity demand
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

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10

    # Stage 1: maximize fully completed requests
    total_completed = sum(completed.values())
    model.Maximize(total_completed)

    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": "not_proven_optimal",
            "schedule": {},
            "metrics": {}
        }

    best_completed = sum(
    solver.Value(completed[i])
    for i in range(len(requests))
)

    model.Add(total_completed == best_completed)

    # Stage 2: maximize the minimum completion percentage
    # expressed as an integer from 0 to 1000.
    min_fraction = model.NewIntVar(
        0, 1000, "min_completion_fraction"
    )

    for i in range(len(requests)):
        model.Add(
            allocated_slots[i] * 1000
            >= min_fraction * required_slots[i]
        )

    model.Maximize(min_fraction)

    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": "not_proven_optimal",
            "schedule": {},
            "metrics": {}
        }

    best_fraction = solver.Value(min_fraction)

    model.Add(min_fraction == best_fraction)

    # Stage 3: minimize electricity cost
    total_cost = sum(
        units(request["power"])
        * get_price(hour)
        * x[i, hour]
        for i, request in enumerate(requests)
        for hour in hours
    )

    model.Minimize(total_cost)

    status = solver.Solve(model)

    if status not in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE
    ):
        return {
            "status": "infeasible",
            "schedule": {},
            "metrics": {}
        }

    schedule = {}

    for i, request in enumerate(requests):
        selected_hours = [
            hour for hour in hours
            if solver.Value(x[i, hour]) == 1
        ]

        delivered = (
            len(selected_hours) * request["power"]
        )

        schedule[request["household"]] = {
            "hours": selected_hours,
            "completed": (
                len(selected_hours) == required_slots[i]
            ),
            "energy_delivered": delivered,
            "energy_requested": request["energy"],
            "completion_percentage": round(
                delivered / request["energy"] * 100, 2
            ),
            "cost": round(
                sum(
                    request["power"] * get_price(hour)
                    for hour in selected_hours
                ), 2
            )
        }

    completed_count = sum(
        1 for value in schedule.values()
        if value["completed"]
    )

    total_requests = len(requests)

    return {
        "status": (
            "optimal"
            if status == cp_model.OPTIMAL
            else "feasible"
        ),
        "schedule": schedule,
        "metrics": {
            "total_requests": total_requests,
            "completed_requests": completed_count,
            "completion_rate": round(
                completed_count / total_requests * 100, 2
            ) if total_requests else 0,
            "total_cost": round(
                sum(r["cost"] for r in schedule.values()), 2
            ),
            "minimum_energy_completion_percentage": (
                min(
                    r["completion_percentage"]
                    for r in schedule.values()
                ) if schedule else 0
            )
        }
    }
