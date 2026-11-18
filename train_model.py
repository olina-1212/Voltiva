
import pandas as pd
import joblib

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# 1. Load dataset
df = pd.read_csv("energy_data.csv")

# 2. Select input features
features = [
    "hour",
    "day_of_week",
    "temperature"
]

X = df[features]
y = df["essential_demand"]

# 3. Chronological train-test split
split = int(len(df) * 0.8)

X_train = X.iloc[:split]
X_test = X.iloc[split:]

y_train = y.iloc[:split]
y_test = y.iloc[split:]

# 4. Create model
model = RandomForestRegressor(
    n_estimators=100,
    max_depth=10,
    random_state=42
)

# 5. Train model
model.fit(X_train, y_train)

# 6. Make predictions
predictions = model.predict(X_test)

# 7. Evaluate model
mae = mean_absolute_error(y_test, predictions)
rmse = mean_squared_error(y_test, predictions) ** 0.5
r2 = r2_score(y_test, predictions)

print("\nMODEL EVALUATION")
print("------------------------")
print("Training records:", len(X_train))
print("Testing records:", len(X_test))
print("MAE:", round(mae, 3), "kW")
print("RMSE:", round(rmse, 3), "kW")
print("R2 Score:", round(r2, 3))

# 8. Save model
joblib.dump(model, "demand_model.pkl")

print("\nModel saved successfully!")
