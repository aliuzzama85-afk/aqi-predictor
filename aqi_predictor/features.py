"""Feature engineering for the merged hourly AQI/weather dataframe."""
import pandas as pd


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Adds forecasting features to the merged hourly AQI/weather dataframe.

    Adds these columns:
        hour, day_of_week, month: calendar parts derived from timestamp
        aqi_change_rate: european_aqi minus its value 1 hour earlier
        rolling_avg_pm25_24h, rolling_avg_pm25_72h: rolling mean of pm2_5
        pm2_5_lag_24h, pm2_5_lag_48h: pm2_5 shifted 24h/48h
        pm10_lag_24h, pm10_lag_48h: pm10 shifted 24h/48h
        european_aqi_lag_24h, european_aqi_lag_48h: european_aqi shifted 24h/48h
    """
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["month"] = df["timestamp"].dt.month

    df["aqi_change_rate"] = df["european_aqi"].diff()

    df["rolling_avg_pm25_24h"] = df["pm2_5"].rolling(window=24, min_periods=1).mean()
    df["rolling_avg_pm25_72h"] = df["pm2_5"].rolling(window=72, min_periods=1).mean()

    for col in ["pm2_5", "pm10", "european_aqi"]:
        df[f"{col}_lag_24h"] = df[col].shift(24)
        df[f"{col}_lag_48h"] = df[col].shift(48)

    return df
