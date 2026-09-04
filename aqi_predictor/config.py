"""Loads and validates environment variables, exposes project constants."""
import os

from dotenv import load_dotenv

load_dotenv()

REQUIRED_VARS = [
    "HOPSWORKS_API_KEY",
    "HOPSWORKS_PROJECT_NAME",
    "CITY_NAME",
    "LATITUDE",
    "LONGITUDE",
]

for _var in REQUIRED_VARS:
    if not os.getenv(_var):
        raise EnvironmentError(f"Missing required environment variable: {_var}")

HOPSWORKS_API_KEY = os.getenv("HOPSWORKS_API_KEY")
HOPSWORKS_PROJECT_NAME = os.getenv("HOPSWORKS_PROJECT_NAME")
CITY_NAME = os.getenv("CITY_NAME")
LATITUDE = float(os.getenv("LATITUDE"))
LONGITUDE = float(os.getenv("LONGITUDE"))
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
