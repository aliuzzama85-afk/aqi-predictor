"""Loads the production model and produces the 3-day AQI forecast. The only place
model-loading/prediction logic lives - the dashboard just imports and calls
predict_next_3_days()."""
import tempfile
import time
from pathlib import Path

import hopsworks
import joblib
import numpy as np
import pandas as pd

from aqi_predictor.config import HOPSWORKS_API_KEY, HOPSWORKS_PROJECT_NAME
from aqi_predictor.hopsworks_utils import read_with_retry

MODEL_CACHE_DIR = Path(tempfile.gettempdir()) / "aqi_forecast_model_cache"

# Rows -49h/-25h/-1h ago; each predicts 72h past itself, giving 24h/48h/72h-ahead forecasts.
FORECAST_OFFSETS = [-49, -25, -1]
FORECAST_HORIZONS = [24, 48, 72]


def login():
    """Single Hopsworks login, meant to be called once per dashboard load (e.g. cached
    with @st.cache_resource) and passed into the functions below, instead of each one
    logging in independently."""
    cert_folder = str(Path(tempfile.gettempdir()) / "hopsworks_certs")
    t0 = time.perf_counter()
    project = hopsworks.login(api_key_value=HOPSWORKS_API_KEY, project=HOPSWORKS_PROJECT_NAME, cert_folder=cert_folder)
    print(f"[timing] hopsworks.login(): {time.perf_counter() - t0:.2f}s")
    return project


def get_latest_features(project, hours: int = 72) -> pd.DataFrame:
    fs = project.get_feature_store()
    fg = fs.get_feature_group("aqi_features", version=1)
    fv = fs.get_or_create_feature_view(name="aqi_features_view", version=1, query=fg.select_all())
    t0 = time.perf_counter()
    df = read_with_retry(lambda: fv.get_batch_data())
    print(f"[timing] feature view read (get_batch_data): {time.perf_counter() - t0:.2f}s")
    return df.sort_values("timestamp").reset_index(drop=True).tail(hours)


def get_production_model_info(project) -> dict:
    """Registry metadata (version/training date/metrics) for the production model."""
    mr = project.get_model_registry()
    best = mr.get_best_model(name="aqi_forecast_model", metric="rmse", direction="min")
    return {"version": best.version, "created": best.created, "metrics": best.training_metrics}


def load_production_model(project):
    t0 = time.perf_counter()
    if not any(MODEL_CACHE_DIR.glob("model.*")):
        mr = project.get_model_registry()
        best = mr.get_best_model(name="aqi_forecast_model", metric="rmse", direction="min")
        best.download(local_path=str(MODEL_CACHE_DIR))
    scaler = joblib.load(MODEL_CACHE_DIR / "scaler.pkl")
    feature_cols = joblib.load(MODEL_CACHE_DIR / "feature_cols.pkl")
    if (MODEL_CACHE_DIR / "model.pkl").exists():
        model = joblib.load(MODEL_CACHE_DIR / "model.pkl")
    else:
        import tensorflow as tf  # only reached if the production model isn't sklearn-based
        model = tf.keras.models.load_model(MODEL_CACHE_DIR / "model.keras")
    print(f"[timing] load_production_model(): {time.perf_counter() - t0:.2f}s")
    return model, scaler, feature_cols


def _categorize(value: float) -> str:
    for threshold, label in [(20, "Good"), (40, "Fair"), (60, "Moderate"), (80, "Poor")]:
        if value < threshold:
            return label
    return "Very Poor"


def predict_next_3_days(project) -> pd.DataFrame:
    model, scaler, feature_cols = load_production_model(project)
    df = get_latest_features(project)
    X = scaler.transform(df.iloc[FORECAST_OFFSETS][feature_cols])
    preds = np.asarray(model.predict(X)).flatten()
    now = pd.to_datetime(df["timestamp"].iloc[-1])
    result = pd.DataFrame({
        "timestamp": [now + pd.Timedelta(hours=h) for h in FORECAST_HORIZONS],
        "predicted_aqi": preds,
    })
    result["aqi_category"] = result["predicted_aqi"].apply(_categorize)
    return result


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(predict_next_3_days(login()).to_string(index=False))
