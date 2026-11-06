
import random
import time
import statistics

from scheduler import schedule_charging, evaluate_schedule
from optimizer import optimize_schedule, optimize_fair_schedule


def generate_requests(count, seed=42):
    rng = random.Random(seed)
    requests = []

    for i in range(count):
        power = rng.choice([2, 3, 5])
        slots = rng.randint(1, 3)

        requests.append({
            "household": f"H{i + 1}",
            "energy": power * slots,
            "power": power,
            "deadline": rng.randint(22, 30)
        })

    return requests


def run_strategy(strategy, requests, capacity, essential_demand):

    start = time.perf_counter()

    if strategy == "ortools":
        result = optimize_schedule(
            requests,
            capacity,
            essential_demand
        )
        schedule = result["schedule"]
        metrics = result["metrics"]
        status = result["status"]

    elif strategy == "fair":
        result = optimize_fair_schedule(
            requests,
            capacity,
            essential_demand
        )
        schedule = result["schedule"]
        metrics = result["metrics"]
        status = result["status"]

    else:
        schedule = schedule_charging(
            requests,
            capacity,
            strategy,
            essential_demand
        )
        metrics = evaluate_schedule(schedule)
        status = "completed"

    runtime = (time.perf_counter() - start) * 1000

    delivered = sum(
        min(
            len(details["hours"]) * request["power"],
            request["energy"]
        )
        for request in requests
        for details in [schedule.get(request["household"], {"hours": []})]
    )

    return {
        "strategy": strategy,
        "status": status,
        "completion_rate": metrics.get("completion_rate", 0),
        "total_cost": metrics.get("total_cost", 0),
        "energy_delivered": delivered,
        "runtime_ms": runtime
    }


def benchmark(count=10, repeats=3):

    requests = generate_requests(count)

    capacity = 20

    essential_demand = {
        hour: capacity * 0.4
        for hour in range(18, 30)
    }

    strategies = [
        "fcfs",
        "edf",
        "greedy",
        "ortools",
        "fair"
    ]

    print(f"\nBENCHMARK: {count} HOUSEHOLDS")
    print(f"Community capacity: {capacity} kW")
    print("-" * 92)

    print(
        f"{'Strategy':<12}"
        f"{'Status':<20}"
        f"{'Complete %':>12}"
        f"{'Cost (Rs)':>12}"
        f"{'Energy kWh':>14}"
        f"{'Time (ms)':>14}"
    )

    print("-" * 92)

    for strategy in strategies:
        runs = [
            run_strategy(
                strategy,
                requests,
                capacity,
                essential_demand
            )
            for _ in range(repeats)
        ]

        result = runs[-1]
        median_time = statistics.median(
            run["runtime_ms"] for run in runs
        )

        print(
            f"{strategy:<12}"
            f"{result['status']:<20}"
            f"{result['completion_rate']:>12.2f}"
            f"{result['total_cost']:>12.2f}"
            f"{result['energy_delivered']:>14.2f}"
            f"{median_time:>14.3f}"
        )


if __name__ == "__main__":
    benchmark(count=25, repeats=3)

