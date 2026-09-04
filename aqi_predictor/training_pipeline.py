"""Trains Ridge, RandomForest, and a small TF model to predict AQI 3 days ahead."""
import sys
import tempfile
from pathlib import Path

import hopsworks
import joblib
import pandas as pd
import tensorflow as tf
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

from aqi_predictor.config import HOPSWORKS_API_KEY, HOPSWORKS_PROJECT_NAME
from aqi_predictor.hopsworks_utils import read_with_retry

TARGET_HOURS_AHEAD = 72


def evaluate(name, y_test, y_pred):
    rmse = mean_squared_error(y_test, y_pred) ** 0.5
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    return {"model": name, "rmse": rmse, "mae": mae, "r2": r2}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

    cert_folder = str(Path(tempfile.gettempdir()) / "hopsworks_certs")
    project = hopsworks.login(api_key_value=HOPSWORKS_API_KEY, project=HOPSWORKS_PROJECT_NAME, cert_folder=cert_folder)
    fs = project.get_feature_store()
    fg = fs.get_feature_group("aqi_features", version=1)
    fv = fs.get_or_create_feature_view(name="aqi_features_view", version=1, query=fg.select_all())

    df = read_with_retry(lambda: fv.get_batch_data())
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Predict european_aqi 72h ahead; drop rows with no future target or incomplete lag/rolling history.
    df["target"] = df["european_aqi"].shift(-TARGET_HOURS_AHEAD)
    df = df.dropna().reset_index(drop=True)

    feature_cols = [c for c in df.columns if c not in ("timestamp", "target")]
    X, y = df[feature_cols], df["target"]

    # Time-based split: last 20% of rows (by time) is the test set, not a random split.
    split = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    scaler = StandardScaler().fit(X_train)
    X_train_s, X_test_s = scaler.transform(X_train), scaler.transform(X_test)

    results = []

    ridge = Ridge()
    ridge.fit(X_train_s, y_train)
    results.append((evaluate("Ridge", y_test, ridge.predict(X_test_s)), ridge))

    rf = RandomForestRegressor(n_estimators=200, random_state=42)
    rf.fit(X_train_s, y_train)
    results.append((evaluate("RandomForest", y_test, rf.predict(X_test_s)), rf))

    tf_model = tf.keras.Sequential([
        tf.keras.Input(shape=(X_train_s.shape[1],)),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(16, activation="relu"),
        tf.keras.layers.Dense(1),
    ])
    tf_model.compile(optimizer="adam", loss="mse")
    tf_model.fit(X_train_s, y_train, epochs=30, verbose=0)
    tf_pred = tf_model.predict(X_test_s, verbose=0).flatten()
    results.append((evaluate("TensorFlow", y_test, tf_pred), tf_model))

    metrics_df = pd.DataFrame([r[0] for r in results]).set_index("model")
    print("\n" + metrics_df.to_string(float_format=lambda v: f"{v:.3f}"))

    best_metrics, best_model = min(results, key=lambda r: r[0]["rmse"])
    print(f"\nBest model: {best_metrics['model']} (RMSE={best_metrics['rmse']:.3f})")

    model_dir = Path(tempfile.mkdtemp()) / "aqi_forecast_model"
    model_dir.mkdir(parents=True)
    joblib.dump(scaler, model_dir / "scaler.pkl")
    joblib.dump(feature_cols, model_dir / "feature_cols.pkl")

    mr = project.get_model_registry()
    metrics_payload = {k: v for k, v in best_metrics.items() if k != "model"}

    if best_metrics["model"] == "TensorFlow":
        best_model.save(model_dir / "model.keras")
        hw_model = mr.tensorflow.create_model(name="aqi_forecast_model", metrics=metrics_payload)
    else:
        joblib.dump(best_model, model_dir / "model.pkl")
        hw_model = mr.sklearn.create_model(name="aqi_forecast_model", metrics=metrics_payload)

    hw_model.save(str(model_dir))
    print(f"Registered {best_metrics['model']} as aqi_forecast_model in the Hopsworks Model Registry.")
