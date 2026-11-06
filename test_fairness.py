
from optimizer import optimize_fair_schedule

requests = [
    {
        "household": "H1",
        "energy": 10,
        "power": 5,
        "deadline": 22
    },
    {
        "household": "H2",
        "energy": 10,
        "power": 5,
        "deadline": 22
    },
    {
        "household": "H3",
        "energy": 10,
        "power": 5,
        "deadline": 22
    }
]

# Only 5 kW is available in each of four hours.
# Total available energy = 20 kWh.
essential_demand = {
    18: 15,
    19: 15,
    20: 15,
    21: 15
}

result = optimize_fair_schedule(
    requests=requests,
    capacity=20,
    essential_demand=essential_demand
)

print("STATUS:", result["status"])

for household, details in result["schedule"].items():
    print(household, details)

print("METRICS:", result["metrics"])
