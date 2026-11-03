
from scheduler import schedule_charging, evaluate_schedule

requests = [
    {"household": "H1", "energy": 10, "power": 5, "deadline": 30},
    {"household": "H2", "energy": 15, "power": 5, "deadline": 29},
    {"household": "H3", "energy": 5, "power": 5, "deadline": 28}
]

capacity = 20

# Simulated essential electricity demand
essential_demand = {
    18: 15,
    19: 15,
    20: 15,
    21: 12,
    22: 12,
    23: 10,
    24: 8,
    25: 8,
    26: 10,
    27: 10,
    28: 12,
    29: 12
}

for strategy in ["fcfs", "edf", "greedy"]:
    result = schedule_charging(
        requests,
        capacity=capacity,
        strategy=strategy,
        essential_demand=essential_demand
    )

    print(f"\n===== {strategy.upper()} =====")

    for household, details in result.items():
        print(household, details)

    metrics = evaluate_schedule(result)

    print("Completed:", metrics["completed_requests"])
    print("Completion Rate:", metrics["completion_rate"], "%")
    print("Total Cost: Rs.", metrics["total_cost"])
