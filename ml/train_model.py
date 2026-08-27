import pandas as pd
import joblib

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score


# ==========================================
# 1. LOAD DATA
# ==========================================

file_path = "ml/data/anthrax_2020_2023.csv"

df = pd.read_csv(file_path)

# Remove exact duplicates
df = df.drop_duplicates().reset_index(drop=True)

print("\n========== DATASET ==========")
print("Rows:", len(df))


# ==========================================
# 2. PREPARE FEATURES
# ==========================================

features = [
    "Year",
    "Outbreaks",
    "Susceptible",
    "Attacks"
]

X = df[features]
y = df["Deaths"]


# ==========================================
# 3. SPLIT DATA
# ==========================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42
)


# ==========================================
# 4. CREATE MODEL
# ==========================================

model = RandomForestRegressor(
    n_estimators=100,
    random_state=42
)


# ==========================================
# 5. TRAIN MODEL
# ==========================================

model.fit(X_train, y_train)


# ==========================================
# 6. TEST MODEL
# ==========================================

y_pred = model.predict(X_test)

mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print("\n========== MODEL RESULTS ==========")
print("Mean Absolute Error:", round(mae, 2))
print("R2 Score:", round(r2, 2))


# ==========================================
# 7. FEATURE IMPORTANCE
# ==========================================

print("\n========== FEATURE IMPORTANCE ==========")

importance = pd.DataFrame({
    "Feature": features,
    "Importance": model.feature_importances_
})

print(importance.sort_values(
    by="Importance",
    ascending=False
))


# ==========================================
# 8. SAVE MODEL
# ==========================================

joblib.dump(model, "ml/livestock_risk_model.pkl")

print("\nModel saved successfully!")