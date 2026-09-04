# aqi-predictor

Forecasts AQI 3 days ahead.

## Architecture

_TBD_

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
