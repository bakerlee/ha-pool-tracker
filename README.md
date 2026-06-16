# Pool Tracker

Pool Tracker is a free, local-first Home Assistant custom integration for manual pool maintenance logging and level prediction.

It stores an append-only event log for water tests and chemical additions, exposes read-only derived sensors with uncertainty-aware predictions, and registers narrow Home Assistant service actions that dashboards, automations, OpenClaw, or other agents can call.

## Scope

Pool Tracker v1 is recordkeeping plus transparent level estimates.

It does not provide chemical recommendations, dosing calculations, pump control, heater control, switch control, valve control, lock control, alarm control, outdoor power control, or automated dosing. Predictions are estimates for display and planning context only.

Logged chemical additions are human-entered records. They are not proof that a chemical was physically added.

Pool Tracker is independent of PoolMath, Leslie's, LaMotte, PoolSense, Flipr, Hanna, SEKO PoolDose, Vistapool, and other paid, cloud, or hardware services.

## Installation

### HACS

1. Add this repository as a HACS custom repository.
2. Select category `Integration`.
3. Install `Pool Tracker`.
4. Restart Home Assistant.
5. Go to **Settings > Devices & services > Add device**.
6. Search for `Pool Tracker`.
7. Create a pool. Each configured pool appears as its own Pool Tracker device.

### Manual

1. Copy `custom_components/pool_tracker` into your Home Assistant config directory at `custom_components/pool_tracker`.
2. Restart Home Assistant.
3. Add a Pool Tracker device through **Settings > Devices & services**.

Do not configure this integration in YAML. Stable configuration is stored in a Home Assistant config entry.

## Pool Profile

Each config entry represents one pool and stores a small pool profile for future calculations and record context:

- Volume and volume unit
- Pool type, such as outdoor, indoor, spa, or swim spa
- Surface type, such as plaster, vinyl, fiberglass, tile, or painted
- Sanitizer type, such as chlorine, salt chlorine generator, or bromine
- Default water-testing method
- Whether the pool is typically covered
- Optional Home Assistant weather and cover entities

If Home Assistant has exactly one weather entity when a pool is configured, Pool Tracker preselects it. These attributes can be changed from the integration options. Optional entity values are ignored when they are missing, unavailable, or unknown. Pool Tracker still does not calculate chemical recommendations.

## Entities

Each configured pool device exposes read-only sensors derived from the event log:

- Free chlorine
- pH
- Total alkalinity
- CYA/stabilizer
- Water clarity
- Free chlorine (Predicted)
- pH (Predicted)
- Total alkalinity (Predicted)
- CYA/stabilizer (Predicted)

Each configured pool also exposes event entities for water tests and chemical additions. These fire when new records are logged.

These sensors are display surfaces. They are not mutable input fields.

## Predictions

Prediction sensors estimate numeric water-test levels from the append-only event log. They currently cover free chlorine, pH, total alkalinity, and CYA/stabilizer.

Each prediction sensor state is the current estimated value. Attributes include:

- `unit`
- `as_of`
- `last_actual_value`
- `last_actual_timestamp`
- `uncertainty`
- `lower_bound`
- `upper_bound`
- `model_inputs`

The `pool_tracker.get_prediction` action returns `actuals` and `series` for charting. `actuals` contains recent measured readings as chart points. `series` contains a bounded prediction line with `value`, `lower_bound`, `upper_bound`, `uncertainty`, and `is_actual`. Uncertainty is zero at actual reading timestamps and grows as time passes after a test. When a later reading disagrees with the prior estimate, future uncertainty increases.

The v1 model is intentionally transparent and resilient to sparse data:

- Free chlorine decays over time, faster with outdoor, uncovered, sunny, warm, or rainy context.
- Recognized chlorine additions, including dichlor, are estimated from the logged amount, unit, and pool volume, then included in the free chlorine prediction.
- pH drifts slowly toward a neutral/default target.
- Total alkalinity and CYA drift slowly, with rainfall treated as possible dilution context.
- Missing optional context falls back to neutral defaults.

Prediction sensors remain unknown until at least one actual water-test reading exists for that value. A chemical-addition record alone is not enough to invent an initial free chlorine baseline.

Weather context uses the configured weather entity's current attributes, and forecast attributes when the weather entity exposes them. Existing configs with explicit sunlight, rainfall, or temperature sensor entities continue to use those values when present, but new setup uses a single weather entity.

For chemical additions, Pool Tracker uses configured volume when available. If volume is missing, it falls back to a rough default by pool type and reports the volume source in `model_inputs`. This is still an estimate, not a dosing recommendation.

Example ApexCharts-style dashboard data source:

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Free chlorine estimate
series:
  - entity: sensor.pool_free_chlorine_predicted
    name: Prediction
    data_generator: |
      return entity.attributes.series.map((point) => [
        new Date(point.timestamp).getTime(),
        point.value,
      ]);
  - entity: sensor.pool_free_chlorine_predicted
    name: Actual readings
    type: scatter
    data_generator: |
      return entity.attributes.actuals.map((point) => [
        new Date(point.timestamp).getTime(),
        point.value,
      ]);
```

## Service Actions

### `pool_tracker.log_water_test`

Accepts any subset of water-test readings. At least one reading, water clarity value, or note is required.

```yaml
service: pool_tracker.log_water_test
data:
  ph: 7.2
  source: agent
```

If `testing_method` is omitted, Pool Tracker stores the pool's default testing method on the record. Override it when a specific test used a different method:

```yaml
service: pool_tracker.log_water_test
data:
  ph: 7.2
  testing_method: drop_test
  source: dashboard
```

Backfilled example:

```yaml
service: pool_tracker.log_water_test
data:
  event_timestamp: "2026-06-14T19:30:00-05:00"
  free_chlorine: 3.1
  total_alkalinity: 80
  source: dashboard
```

Omitted readings are not copied from previous tests into the new record.

### `pool_tracker.log_chemical_addition`

Requires `chemical`, `amount`, and `unit`.

```yaml
service: pool_tracker.log_chemical_addition
data:
  chemical: dichlor
  amount: 1
  unit: Tbsp
  source: agent
```

Both service actions return a `record_id` when called with Home Assistant service response support, and fire a `pool_tracker_record_created` event containing the record id, pool id, and record type.

## OpenClaw Examples

For "I just added 1 Tbsp dichlor":

```yaml
service: pool_tracker.log_chemical_addition
data:
  chemical: dichlor
  amount: 1
  unit: Tbsp
  source: agent
```

For "pH is 7.2":

```yaml
service: pool_tracker.log_water_test
data:
  ph: 7.2
  source: agent
```

## Temporary Dashboard UI

The preferred long-term UI is an integration-managed frontend surface or custom panel. V1 is backend-first, so use Home Assistant service/action cards as a temporary UI.

Example Lovelace manual water-test action:

```yaml
type: button
name: Log pH 7.2
tap_action:
  action: call-service
  service: pool_tracker.log_water_test
  data:
    ph: 7.2
    source: dashboard
```

Keep dashboard controls as service calls. Do not recreate helper-backed input fields, scripts, template sensors, or automations as storage glue.

## Storage

Events are stored in Home Assistant persistent storage owned by this integration. Recorder history is not the source of truth.

Each record includes:

- Stable record id
- Pool id
- Record type
- Event timestamp
- Creation timestamp
- Optional source
- Optional notes

Water-test fields are stored only when explicitly submitted. Chemical additions store chemical, amount, and unit.

Water-test records also store the resolved testing method when one is configured or supplied on the service call. This is intended for future method-aware accuracy handling.

Storage schema version `1` is explicit so future migrations can be handled deliberately.

## Development

Create a virtual environment with a Home Assistant-supported Python version, then install development dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements-dev.txt
```

Run checks:

```bash
ruff check .
ruff format --check .
pytest
```

Format:

```bash
ruff format .
```

## Known Limitations

- V1 supports multiple configured pools, with one Pool Tracker device per pool.
- The backend and service actions are implemented first; a full custom panel is not included yet.
- There is no chemistry guidance, dosing advice, equipment control, or verification that a logged action physically happened.
- Usage context is deferred. It is unclear whether this should be a boolean in-use/not-in-use signal, an event such as "used for 3 hours", or a more flexible proxied value. Future design should make it helpful without forcing one brittle interpretation.
