"""One-off script: backfill the last 90 days of AQI/weather data into Hopsworks."""
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import hopsworks

from aqi_predictor.config import (
    CITY_NAME,
    HOPSWORKS_API_KEY,
    HOPSWORKS_PROJECT_NAME,
    LATITUDE,
    LONGITUDE,
)
from aqi_predictor.data_sources import fetch_historical_air_quality
from aqi_predictor.features import build_features

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

    # Open-Meteo's archive has a few days of lag, so end 2 days ago rather than today.
    end_date = date.today() - timedelta(days=2)
    start_date = end_date - timedelta(days=90)

    print(f"Fetching {start_date} to {end_date} for {CITY_NAME} ({LATITUDE}, {LONGITUDE})")
    raw_df = fetch_historical_air_quality(LATITUDE, LONGITUDE, str(start_date), str(end_date))
    print(f"Fetched {len(raw_df)} rows")

    features_df = build_features(raw_df)
    print(f"Built features: {features_df.shape[1]} columns")

    # hopsworks' default cert_folder ("/tmp") doesn't resolve on Windows; override
    # with a real cross-platform temp dir so cert download works everywhere.
    cert_folder = Path(tempfile.gettempdir()) / "hopsworks_certs"
    project = hopsworks.login(
        api_key_value=HOPSWORKS_API_KEY,
        project=HOPSWORKS_PROJECT_NAME,
        cert_folder=str(cert_folder),
    )
    fs = project.get_feature_store()

    try:
        feature_group = fs.get_or_create_feature_group(
            name="aqi_features",
            version=1,
            description="Hourly AQI + weather features for 3-day-ahead forecasting",
            primary_key=["timestamp"],
            event_time="timestamp",
            time_travel_format="HUDI",  # DELTA needs the optional 'deltalake' package
        )
        feature_group.insert(features_df)
        print(f"Inserted {len(features_df)} rows into aqi_features v1")
    except Exception as exc:
        raise RuntimeError(
            "Hopsworks feature group create/insert failed - this can be flaky on "
            "first use (project/topic provisioning); wait a moment and retry."
        ) from exc
