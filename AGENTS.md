# Repository Guidelines

## Project Structure & Module Organization

This repository contains a Home Assistant custom integration for Pool Tracker. Core integration code lives in `custom_components/pool_tracker/`: config flow, sensors, events, storage, prediction logic, services, translations, and the HACS manifest. The bundled dashboard/card module is `custom_components/pool_tracker/frontend/pool-tracker-frontend.js`. Brand assets are in `custom_components/pool_tracker/brand/`, documentation is in `README.md` and `docs/`, and tests live in `tests/` with one `test_*.py` file per behavior area.

## Build, Test, and Development Commands

Create the local environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements-dev.txt
```

Run the standard checks before committing:

```bash
.venv/bin/python -m ruff format --check .
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest
node --check custom_components/pool_tracker/frontend/pool-tracker-frontend.js
```

Use `.venv/bin/python -m ruff format .` to apply Python formatting.

## Coding Style & Naming Conventions

Python targets 3.14 with Ruff line length 88, double quotes, space indentation, and lint rules `B`, `E`, `F`, `I`, `N`, `UP`, and `W`. Follow Home Assistant integration conventions: constants in `const.py`, config entry setup in `__init__.py`, entity behavior in focused modules, and service schemas in `services.yaml`. Keep frontend code in the existing plain JavaScript module style. Prefer explicit, typed models and clear service contracts over hidden fallback behavior.

## Testing Guidelines

Tests use `pytest`, `pytest-asyncio`, and `pytest-homeassistant-custom-component`. Add or update tests in `tests/test_<feature>.py` when changing services, config flow, sensors, storage, prediction behavior, or frontend output. Keep initial chemistry states `unknown` until real readings exist, and preserve append-only event history as the source of truth.

## Commit & Pull Request Guidelines

Recent commits use concise imperative subjects, for example `Enhance pool tracker card logging` and `Constrain chemical addition action inputs`. Make atomic commits after each completed piece of work. Pull requests should describe the user-facing behavior, list verification commands run, link relevant issues when available, and include screenshots or short clips for visible frontend changes.

## Agent-Specific Instructions

This is a brand-new integration; do not add migration or legacy compatibility paths unless explicitly requested. Keep dashboard controls service-backed, avoid helper/template storage glue, and treat logged chemical additions as records rather than proof of physical dosing.
