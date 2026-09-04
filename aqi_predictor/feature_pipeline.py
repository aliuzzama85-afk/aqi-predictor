"""Hourly script: insert the latest AQI+weather feature row into Hopsworks (idempotent)."""
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import hopsworks
import pandas as pd

from aqi_predictor.config import HOPSWORKS_API_KEY, HOPSWORKS_PROJECT_NAME, LATITUDE, LONGITUDE
from aqi_predictor.data_sources import fetch_current_air_quality, fetch_current_weather, fetch_historical_air_quality
from aqi_predictor.features import build_features
from aqi_predictor.hopsworks_utils import read_with_retry

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

    # 72h of context for build_features' lag/rolling columns. End 2 days ago, matching
    # backfill.py's archive-lag buffer; the current reading below covers up to now.
    end_date = date.today() - timedelta(days=2)
    start_date = end_date - timedelta(days=3)
    context_df = fetch_historical_air_quality(LATITUDE, LONGITUDE, str(start_date), str(end_date))

    current_aq = fetch_current_air_quality(LATITUDE, LONGITUDE)["current"]
    current_weather = fetch_current_weather(LATITUDE, LONGITUDE)["current"]
    current_row = pd.DataFrame([{
        "timestamp": current_aq["time"],
        **{k: v for k, v in current_aq.items() if k in context_df.columns},
        **{k: v for k, v in current_weather.items() if k in context_df.columns},
    }])
    # Align dtypes to the historical schema - a single-value API response can come back
    # as a different int/float subtype (e.g. relative_humidity_2m) and break the insert.
    current_row = current_row.astype(context_df[current_row.columns].dtypes)

    new_row = build_features(pd.concat([context_df, current_row], ignore_index=True)).tail(1)
    new_timestamp = new_row["timestamp"].iloc[0]

    cert_folder = str(Path(tempfile.gettempdir()) / "hopsworks_certs")
    project = hopsworks.login(api_key_value=HOPSWORKS_API_KEY, project=HOPSWORKS_PROJECT_NAME, cert_folder=cert_folder)
    fg = project.get_feature_store().get_feature_group("aqi_features", version=1)

    existing = read_with_retry(lambda: fg.filter(fg.timestamp == new_timestamp).read())
    if len(existing) > 0:
        print(f"Row for {new_timestamp} already exists, skipping insert.")
    else:
        fg.insert(new_row)
        print(f"Inserted new row for {new_timestamp}.")
