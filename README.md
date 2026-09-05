# aqi-predictor

Forecasts AQI 3 days ahead.

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

## Model

`aqi_predictor/training_pipeline.py` trains Ridge, RandomForest, and a small
TensorFlow model to predict `european_aqi` 72h ahead, and registers the best
(by RMSE) to the Hopsworks Model Registry as `aqi_forecast_model`. Current
production model is **Ridge, RMSE 5.59** (MAE 4.06, R² 0.23) — R² is modest,
which is expected from ~90 days of hourly data and no hyperparameter tuning.
If there's time, the natural next steps are backfilling more historical data
and further feature tuning, both of which should improve on this baseline.

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
without compiling anything:

```
python -m venv .venv
.venv\Scripts\pip install ./vendor/twofish-stub
.venv\Scripts\pip install -e .
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
