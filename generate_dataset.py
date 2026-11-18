
import pandas as pd
import numpy as np

from datetime import datetime, timedelta

rng = np.random.default_rng(42)

records = []

start_date = datetime(2026, 1, 1)

# Generate 90 days of hourly demand data
for day in range(90):

    current_date = start_date + timedelta(days=day)

    for hour in range(24):

        day_of_week = current_date.weekday()

        # Simulated temperature
        temperature = (
            26
            + 5 * np.sin(2 * np.pi * hour / 24)
            + rng.normal(0, 1.5)
        )

        # Typical household electricity demand pattern
        if 6 <= hour <= 9:
            base_demand = 12
        elif 18 <= hour <= 22:
            base_demand = 16
        elif 23 <= hour or hour <= 5:
            base_demand = 8
        else:
            base_demand = 10

        # Higher usage during weekends
        weekend_extra = 2 if day_of_week >= 5 else 0

        # Simulated temperature effect
        temperature_extra = max(
            0, temperature - 28
        ) * 0.3

        noise = rng.normal(0, 0.8)

        demand = (
            base_demand
            + weekend_extra
            + temperature_extra
            + noise
        )

        demand = max(0, demand)

        records.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "hour": hour,
            "day_of_week": day_of_week,
            "temperature": round(temperature, 2),
            "essential_demand": round(demand, 2)
        })

df = pd.DataFrame(records)

df.to_csv("energy_data.csv", index=False)

print("Dataset generated successfully!")
print("Total records:", len(df))
print(df.head())
