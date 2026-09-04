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
