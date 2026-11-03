
def get_price(hour):
    if 18 <= hour < 21:
        return 10
    elif 21 <= hour < 24:
        return 6
    else:
        return 4


def schedule_charging(
    requests,
    capacity=20,
    strategy="fcfs",
    essential_demand=None
):
    schedule = {}

    hours = list(range(18, 30))

    if essential_demand is None:
        essential_demand = {}

    # Reserve electricity for essential household usage
    available = {}

    for hour in hours:
        essential = essential_demand.get(hour, 0)
        available[hour] = max(0, capacity - essential)

    if strategy == "edf":
        ordered_requests = sorted(
            requests,
            key=lambda r: r["deadline"]
        )
    else:
        ordered_requests = requests

    for request in ordered_requests:
        household = request["household"]
        remaining = request["energy"]
        power = request["power"]
        deadline = request["deadline"]

        possible_hours = [
            hour for hour in hours
            if hour < deadline
        ]

        if strategy == "greedy":
            possible_hours.sort(key=get_price)

        allocated = []
        cost = 0

        for hour in possible_hours:
            if remaining <= 0:
                break

            if available[hour] >= power:
                delivered = min(power, remaining)

                available[hour] -= power
                remaining -= delivered
                allocated.append(hour)

                cost += delivered * get_price(hour)

        schedule[household] = {
            "hours": sorted(allocated),
            "completed": remaining <= 0,
            "cost": cost
        }

    return schedule



def evaluate_schedule(schedule):
    total = len(schedule)

    completed = sum(
        1 for details in schedule.values()
        if details["completed"]
    )

    total_cost = sum(
        details["cost"] for details in schedule.values()
    )

    return {
        "total_requests": total,
        "completed_requests": completed,
        "completion_rate": round(
            completed / total * 100, 2
        ) if total else 0,
        "total_cost": total_cost
    }
