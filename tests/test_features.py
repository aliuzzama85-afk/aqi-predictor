"""Tests for aqi_predictor.features.build_features."""
import numpy as np
import pandas as pd

from aqi_predictor.features import build_features

EXPECTED_NEW_COLUMNS = {
    "hour", "day_of_week", "month", "aqi_change_rate",
    "rolling_avg_pm25_24h", "rolling_avg_pm25_72h",
    "pm2_5_lag_24h", "pm2_5_lag_48h",
    "pm10_lag_24h", "pm10_lag_48h",
    "european_aqi_lag_24h", "european_aqi_lag_48h",
}


def test_build_features_adds_expected_columns():
    n = 100
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-08-01", periods=n, freq="h").astype(str),
        "pm10": np.random.uniform(10, 50, n),
        "pm2_5": np.random.uniform(5, 30, n),
        "carbon_monoxide": np.random.uniform(100, 300, n),
        "nitrogen_dioxide": np.random.uniform(1, 20, n),
        "sulphur_dioxide": np.random.uniform(1, 10, n),
        "ozone": np.random.uniform(20, 70, n),
        "european_aqi": np.random.uniform(10, 60, n),
        "temperature_2m": np.random.uniform(20, 40, n),
        "relative_humidity_2m": np.random.uniform(20, 90, n),
        "wind_speed_10m": np.random.uniform(0, 20, n),
        "surface_pressure": np.random.uniform(990, 1020, n),
        "precipitation": np.random.uniform(0, 5, n),
    })

    result = build_features(df)

    assert EXPECTED_NEW_COLUMNS.issubset(result.columns)
