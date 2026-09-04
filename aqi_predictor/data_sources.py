"""API client functions for fetching AQI and weather data."""
import logging
import sys

import pandas as pd
import requests

from aqi_predictor.config import LATITUDE, LONGITUDE

logger = logging.getLogger(__name__)

AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
WEATHER_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

AQ_VARIABLES = "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,european_aqi"
WEATHER_VARIABLES = "temperature_2m,relative_humidity_2m,wind_speed_10m,surface_pressure,precipitation"


def fetch_current_air_quality(lat: float, lon: float) -> dict:
    params = {"latitude": lat, "longitude": lon, "hourly": AQ_VARIABLES, "current": AQ_VARIABLES}
    try:
        response = requests.get(AIR_QUALITY_URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        logger.exception("Failed to fetch current air quality for (%s, %s)", lat, lon)
        raise


def fetch_current_weather(lat: float, lon: float) -> dict:
    params = {"latitude": lat, "longitude": lon, "current": WEATHER_VARIABLES}
    try:
        response = requests.get(WEATHER_FORECAST_URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        logger.exception("Failed to fetch current weather for (%s, %s)", lat, lon)
        raise


def fetch_historical_weather(lat: float, lon: float, start_date: str, end_date: str) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": WEATHER_VARIABLES,
    }
    try:
        response = requests.get(WEATHER_ARCHIVE_URL, params=params, timeout=10)
        response.raise_for_status()
        return pd.DataFrame(response.json()["hourly"]).rename(columns={"time": "timestamp"})
    except requests.RequestException:
        logger.exception("Failed to fetch historical weather for (%s, %s)", lat, lon)
        raise


def fetch_historical_air_quality(lat: float, lon: float, start_date: str, end_date: str) -> pd.DataFrame:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": AQ_VARIABLES,
    }
    try:
        response = requests.get(AIR_QUALITY_URL, params=params, timeout=10)
        response.raise_for_status()
        aq_df = pd.DataFrame(response.json()["hourly"]).rename(columns={"time": "timestamp"})
    except requests.RequestException:
        logger.exception("Failed to fetch historical air quality for (%s, %s)", lat, lon)
        raise

    weather_df = fetch_historical_weather(lat, lon, start_date, end_date)
    return aq_df.merge(weather_df, on="timestamp")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(fetch_current_air_quality(LATITUDE, LONGITUDE))
