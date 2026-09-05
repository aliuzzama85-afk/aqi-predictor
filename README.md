# aqi-predictor

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://aqi-predictor-bzskyencn2jnwghb6m7dzu.streamlit.app/)

**Live app: https://aqi-predictor-bzskyencn2jnwghb6m7dzu.streamlit.app/**

Forecasts AQI 3 days ahead for Karachi, Pakistan. Two scheduled GitHub Actions
pipelines keep a Hopsworks feature store and model registry current; a Streamlit
dashboard reads from both to show the forecast, alerts, and SHAP explanations.

## Architecture

Two scheduled GitHub Actions jobs keep Hopsworks up to date; the dashboard only ever reads from it.

```
 GitHub Actions (hourly)             GitHub Actions (daily)
 feature_pipeline.py                 training_pipeline.py
 fetch latest AQI + weather,         train Ridge / RandomForest / TF,
 engineer features, insert           register best model by RMSE
         |                                    |
         | insert                             | register
         v                                    v
 +----------------------------------------------------------+
 |                         Hopsworks                         |
 |   Feature Store (aqi_features)     Model Registry         |
 |                                     (aqi_forecast_model)   |
 +----------------------------------------------------------+
                            |
                            | read (aqi_predictor/inference.py)
                            v
                +--------------------------------+
                |      Streamlit dashboard        |
                |      dashboard/app.py           |
                |  3-day forecast, SHAP, history   |
                +--------------------------------+
```

- **Hourly** (`.github/workflows/feature_pipeline.yml`): fetches the latest AQI/weather
  reading, builds features, and inserts one row into the `aqi_features` feature group
  (idempotent - skips if that timestamp already exists).
- **Daily** (`.github/workflows/training_pipeline.yml`): reads the full feature view,
  trains Ridge/RandomForest/a small TF model, and registers whichever has the lowest
  RMSE as `aqi_forecast_model`.
- **Dashboard**: `aqi_predictor/inference.py` logs in once per load and reads the
  latest features + production model straight from Hopsworks - no pipeline writes to it.

## Getting started (local)

Needs **Python 3.12** (matches `pyproject.toml`, both GitHub Actions workflows, and
the Streamlit Cloud deploy) and a Hopsworks account/project (the free tier works).

1. Clone the repo and create a virtualenv:
   ```
   python -m venv .venv
   ```
   On Windows, read "Windows setup notes" below *before* the next step - `hopsworks`
   pulls in a dependency that otherwise needs a C compiler to install.
2. Install the package:
   ```
   .venv\Scripts\pip install -e .
   ```
   Run `.venv\Scripts\pip install -e ".[notebook]"` instead if you also want to
   run `notebooks/eda.ipynb`.
3. Copy `.env.example` to `.env` and fill in the required values - `config.py` raises
   `EnvironmentError` on startup if any are missing:
   ```
   HOPSWORKS_API_KEY=...
   HOPSWORKS_PROJECT_NAME=...
   CITY_NAME=Karachi
   LATITUDE=24.8607
   LONGITUDE=67.0011
   ```
   (`.env.example` also lists `OPENWEATHER_API_KEY`, but nothing currently reads it -
   all AQI/weather data comes from Open-Meteo, which needs no key.)
4. One-time backfill - populates the Hopsworks feature group with ~90 days of history
   (Windows: create `C:\tmp` first - see "Hopsworks backfill" under Windows setup notes):
   ```
   python -m aqi_predictor.backfill
   ```
5. Run either pipeline by hand (both also run automatically on the GitHub Actions
   schedules described above):
   ```
   python -m aqi_predictor.feature_pipeline
   python -m aqi_predictor.training_pipeline
   ```
6. Run the dashboard:
   ```
   streamlit run dashboard/app.py
   ```

## Model

`aqi_predictor/training_pipeline.py` trains Ridge, RandomForest, and a small
TensorFlow model to predict `european_aqi` 72h ahead, and registers the best
(by RMSE) to the Hopsworks Model Registry as `aqi_forecast_model`. Current
production model is **Ridge, RMSE 5.59** (MAE 4.06, R² 0.23) — R² is modest,
which is expected from ~90 days of hourly data and no hyperparameter tuning.
If there's time, the natural next steps are backfilling more historical data
and further feature tuning, both of which should improve on this baseline.

`notebooks/eda.ipynb` has exploratory analysis of the backfilled data (AQI over time,
pollutant/weather correlations, hour-of-day and day-of-week patterns) - see "Getting
started" above for the extra install it needs.

## Deployment

The dashboard reads all its configuration from environment variables via `config.py`,
so [Streamlit Community Cloud](https://share.streamlit.io) needs no code changes:

1. Push this repo to GitHub (already done).
2. On share.streamlit.io, click "New app" and point it at this repo with
   `dashboard/app.py` as the main file path.
3. Click "Advanced settings" **before** deploying and pick **Python 3.12** from the
   "Python version" dropdown - this is the only way to pin it; Community Cloud has no
   `runtime.txt`/`.python-version` file mechanism, and the version can't be changed on
   an already-deployed app without deleting and redeploying it.
4. In the same Advanced settings dialog, add Secrets - paste the same five values
   from `.env`, in TOML format:
   ```toml
   HOPSWORKS_API_KEY = "..."
   HOPSWORKS_PROJECT_NAME = "..."
   CITY_NAME = "Karachi"
   LATITUDE = 24.8607
   LONGITUDE = 67.0011
   ```
5. Deploy. Streamlit Cloud exposes these secrets as real environment variables, so
   `config.py`'s `os.getenv(...)` calls pick them up exactly like `.env` does locally.

## Windows setup notes

`hopsworks` depends on `pyjks`, which depends on `twofish` — a package that only
ships a source tarball (no wheel) and needs a C compiler to build. `twofish` is
only used by `pyjks` for decrypting legacy BKS-format Java keystores, a path
Hopsworks Serverless never exercises (its auth is REST/API-key based, not
JKS-based). Rather than requiring MSVC Build Tools, this repo installs a stub
`twofish` package from `vendor/twofish-stub/` that satisfies the dependency
without compiling anything. Run this between steps 1 and 2 of "Getting started" above:

```
.venv\Scripts\pip install ./vendor/twofish-stub
```

If a future feature actually needs BKS-keystore support, `pip uninstall
twofish` and install the real package (requires a C compiler) instead.

### Hopsworks backfill (`aqi_predictor/backfill.py`)

Running the backfill script against a real Hopsworks project surfaced three
more Windows-only quirks in the `hopsworks` client. None of these affect
Linux/GitHub Actions — they only matter for local Windows dev.

- **Hardcoded `/tmp` path.** `hopsworks_common.client.base._write_pem()`
  writes cert files to `os.path.join("/tmp", ...)` with no override
  parameter. On Windows this resolves relative to the current drive root
  (e.g. `C:\tmp\...`), so create that folder once:
  ```
  mkdir C:\tmp
  ```
  (`hopsworks.login()`'s own `cert_folder` argument, which `backfill.py`
  already sets to a proper temp dir, only covers a *different* cert path —
  it doesn't fix this second hardcoded one deeper in the Kafka/PEM-writing
  code. On Linux, `/tmp` already exists, so this is a no-op there.)

- **HUDI vs Delta.** `get_or_create_feature_group()` defaults to
  `time_travel_format="DELTA"`, which requires the optional `deltalake`
  package (not installed). `backfill.py` passes `time_travel_format="HUDI"`
  instead rather than adding a new dependency — this is unrelated to OS,
  just a dependency choice.

- **`confluent-kafka` is required, not optional.** Inserting into a feature
  group via the plain Python engine (no Spark) needs `confluent-kafka` for
  materialization-job checkpointing; without it, `insert()` fails with
  `ModuleNotFoundError`. It's pinned in `pyproject.toml`. A prebuilt wheel
  exists for Windows, so no compiler is needed.

Backfill confirmed working end to end: 2184 hourly rows fetched, feature-
engineered, and verified present in the `aqi_features` v1 feature group via
a read-back (independent of the client's own success message, since the
Hopsworks materialization job can report `FAILED` on a transient backend
statistics-computation error even after the actual data write succeeded).
