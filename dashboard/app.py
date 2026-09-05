"""Streamlit dashboard: current AQI, 3-day forecast, SHAP explanation, and 7-day trend
for CITY_NAME. All model-loading/prediction logic stays in inference.py; this file only
loads, caches, and renders it."""
import pandas as pd
import streamlit as st

from aqi_predictor.config import CITY_NAME
from aqi_predictor.inference import (
    FORECAST_HORIZONS,
    FORECAST_OFFSETS,
    get_latest_features,
    get_production_model_info,
    load_production_model,
    login,
    predict_next_3_days,
)
import components as dc

st.set_page_config(layout="wide", page_title="Karachi AQI Forecast", page_icon="🌫️")
st.markdown(dc.inject_css(), unsafe_allow_html=True)


@st.cache_resource(ttl=1800)
def get_project():
    return login()


# Leading underscore on `_project` tells st.cache_data/cache_resource to use it as-is
# rather than trying to hash it (it's a live Hopsworks session, not cacheable data).
@st.cache_data(ttl=1800)
def load_history(_project, hours: int = 168) -> pd.DataFrame:
    return get_latest_features(_project, hours=hours)


@st.cache_data(ttl=1800)
def load_forecast(_project) -> pd.DataFrame:
    return predict_next_3_days(_project)


@st.cache_resource(ttl=1800)
def load_model(_project):
    return load_production_model(_project)


@st.cache_data(ttl=3600)
def load_model_info(_project) -> dict:
    return get_production_model_info(_project)


st.title(f"{CITY_NAME} Air Quality Forecast")

try:
    project = get_project()
    history = load_history(project)
    forecast = load_forecast(project)
except Exception as exc:
    st.error(f"Couldn't load data from Hopsworks: {exc}")
    st.stop()

recent = history.tail(72).reset_index(drop=True)
latest = recent.iloc[-1]
current_category = dc.categorize(latest["european_aqi"])

alerts = []
if latest["european_aqi"] >= dc.ALERT_THRESHOLD:
    alerts.append(f"Current AQI is {current_category} ({latest['european_aqi']:.0f}).")
worst = forecast.loc[forecast["predicted_aqi"].idxmax()]
if worst["predicted_aqi"] >= dc.ALERT_THRESHOLD:
    when = pd.to_datetime(worst["timestamp"]).strftime("%a %H:%M UTC")
    alerts.append(f"Forecast reaches {worst['aqi_category']} ({worst['predicted_aqi']:.0f}) by {when}.")
if alerts:
    st.markdown(dc.alert_banner_html(alerts), unsafe_allow_html=True)

st.caption(f"Latest reading: {pd.to_datetime(latest['timestamp'])} UTC")

cols = st.columns([1.7, 1, 1, 1], gap="medium")
with cols[0]:
    st.markdown(dc.stat_card_html("Current AQI", f"{latest['european_aqi']:.0f}", current_category, anchor=True), unsafe_allow_html=True)
for col, (_, row), horizon in zip(cols[1:], forecast.iterrows(), FORECAST_HORIZONS):
    with col:
        st.markdown(dc.stat_card_html(f"+{horizon}h", f"{row['predicted_aqi']:.0f}", row["aqi_category"]), unsafe_allow_html=True)

st.caption(
    "Uses the European Air Quality Index scale (0-100+), which differs from the "
    "familiar US AQI scale (0-500): a reading of 40 here is \"Moderate\" on this scale."
)

st.subheader("3-day forecast")
st.plotly_chart(dc.build_forecast_chart(recent, forecast, current_category), use_container_width=True)

with st.expander("Why this forecast"):
    horizon_choice = st.radio("Horizon", FORECAST_HORIZONS, format_func=lambda h: f"+{h}h", horizontal=True)
    offset = FORECAST_OFFSETS[FORECAST_HORIZONS.index(horizon_choice)]
    instance_row = recent.iloc[offset]
    model, scaler, feature_cols = load_model(project)
    values = dc.compute_shap_contributions(model, scaler, feature_cols, recent, instance_row)
    if values is None:
        st.info(f"SHAP explanations aren't available for this model type ({type(model).__name__}).")
    else:
        st.plotly_chart(dc.build_shap_chart(values, feature_cols), use_container_width=True)

st.subheader("Last 7 days")
st.plotly_chart(dc.build_trend_chart(history), use_container_width=True)

try:
    model_info = load_model_info(project)
    created = model_info["created"]
    created_ts = pd.to_datetime(created, unit="ms") if isinstance(created, (int, float)) else pd.to_datetime(created)
    trained = created_ts.strftime("%Y-%m-%d %H:%M UTC")
except Exception:
    trained = "unavailable"

feature_refresh = pd.to_datetime(history["timestamp"].max())
st.markdown(
    f'<div style="color:{dc.MUTED};font-size:0.82rem;margin-top:1.5rem;">'
    f"Features last refreshed: {feature_refresh} UTC &nbsp;&middot;&nbsp; Model trained: {trained}</div>",
    unsafe_allow_html=True,
)
