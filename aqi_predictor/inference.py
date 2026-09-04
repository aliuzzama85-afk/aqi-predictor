"""Loads the production model and produces the 3-day AQI forecast. The only place
model-loading/prediction logic lives - the dashboard just imports and calls
predict_next_3_days()."""
import tempfile
from pathlib import Path

import hopsworks
import joblib
import numpy as np
import pandas as pd

from aqi_predictor.config import HOPSWORKS_API_KEY, HOPSWORKS_PROJECT_NAME
from aqi_predictor.hopsworks_utils import read_with_retry

MODEL_CACHE_DIR = Path(tempfile.gettempdir()) / "aqi_forecast_model_cache"


def _login():
    cert_folder = str(Path(tempfile.gettempdir()) / "hopsworks_certs")
    return hopsworks.login(api_key_value=HOPSWORKS_API_KEY, project=HOPSWORKS_PROJECT_NAME, cert_folder=cert_folder)


def get_latest_features() -> pd.DataFrame:
    fs = _login().get_feature_store()
    fg = fs.get_feature_group("aqi_features", version=1)
    fv = fs.get_or_create_feature_view(name="aqi_features_view", version=1, query=fg.select_all())
    df = read_with_retry(lambda: fv.get_batch_data())
    return df.sort_values("timestamp").reset_index(drop=True).tail(72)


def load_production_model():
    if not any(MODEL_CACHE_DIR.glob("model.*")):
        mr = _login().get_model_registry()
        best = mr.get_best_model(name="aqi_forecast_model", metric="rmse", direction="min")
        best.download(local_path=str(MODEL_CACHE_DIR))
    scaler = joblib.load(MODEL_CACHE_DIR / "scaler.pkl")
    feature_cols = joblib.load(MODEL_CACHE_DIR / "feature_cols.pkl")
    if (MODEL_CACHE_DIR / "model.pkl").exists():
        model = joblib.load(MODEL_CACHE_DIR / "model.pkl")
    else:
        import tensorflow as tf
        model = tf.keras.models.load_model(MODEL_CACHE_DIR / "model.keras")
    return model, scaler, feature_cols


def _categorize(value: float) -> str:
    for threshold, label in [(20, "Good"), (40, "Fair"), (60, "Moderate"), (80, "Poor")]:
        if value < threshold:
            return label
    return "Very Poor"


def predict_next_3_days() -> pd.DataFrame:
    model, scaler, feature_cols = load_production_model()
    df = get_latest_features()
    offsets, horizons = [-49, -25, -1], [24, 48, 72]  # rows 48h/24h/0h ago; each predicts 72h past itself
    X = scaler.transform(df.iloc[offsets][feature_cols])
    preds = np.asarray(model.predict(X)).flatten()
    now = pd.to_datetime(df["timestamp"].iloc[-1])
    result = pd.DataFrame({
        "timestamp": [now + pd.Timedelta(hours=h) for h in horizons],
        "predicted_aqi": preds,
    })
    result["aqi_category"] = result["predicted_aqi"].apply(_categorize)
    return result


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(predict_next_3_days().to_string(index=False))
