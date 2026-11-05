
from optimizer import optimize_schedule

requests = [
    {
        "household": "H1",
        "energy": 10,
        "power": 5,
        "deadline": 30
    },
    {
        "household": "H2",
        "energy": 15,
        "power": 5,
        "deadline": 29
    },
    {
        "household": "H3",
        "energy": 5,
        "power": 5,
        "deadline": 28
    }
]

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

result = optimize_schedule(
    requests=requests,
    capacity=20,
    essential_demand=essential_demand
)

print("STATUS:", result["status"])
print("SCHEDULE:", result["schedule"])
print("METRICS:", result["metrics"])
