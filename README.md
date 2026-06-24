# Pool Tracker

Pool Tracker is a free, local-first Home Assistant custom integration for manual pool maintenance logging and level prediction.

It stores an event log for water tests and chemical additions, exposes read-only derived sensors with uncertainty-aware predictions, and registers narrow Home Assistant service actions that dashboards, automations, OpenClaw, or other agents can call.

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
- Total chlorine
- Combined chlorine
- Total bromine
- pH
- Total alkalinity
- Calcium hardness
- Total hardness
- CYA/stabilizer
- Salt
- Total dissolved solids
- Phosphates
- Copper
- Iron
- Water temperature
- Water clarity
- Free chlorine (Predicted)
- pH (Predicted)
- Total alkalinity (Predicted)
- CYA/stabilizer (Predicted)

Each configured pool also exposes event entities for water tests and chemical additions. These fire when new records are logged.

These sensors are display surfaces. They are not mutable input fields.

## Predictions

Prediction sensors estimate numeric water-test levels from the event log. They currently cover free chlorine, pH, total alkalinity, and CYA/stabilizer.

Each prediction sensor state is the current estimated value. Attributes include:

- `unit`
- `as_of`
- `last_actual_value`
- `last_actual_timestamp`
- `uncertainty`
- `lower_bound`
- `upper_bound`
- `model_inputs`

Prediction sensor attributes include `actuals`, `series`, and `chemical_additions` for charting. `actuals` contains recent measured readings as chart points. `series` contains an hourly bounded prediction line with `value`, `lower_bound`, `upper_bound`, `uncertainty`, and `is_actual`. `chemical_additions` contains recent chemical-event markers with the event timestamp, summary, and a chart `value` when the event can be placed against the current reading prediction. The `pool_tracker.get_prediction` action returns the same chart data for callers that prefer a service response. Uncertainty is zero at actual reading timestamps and grows as time passes after a test. When a later reading disagrees with the prior estimate, future uncertainty increases.

The v1 model is intentionally transparent and resilient to sparse data:

- Free chlorine decays over time, faster with outdoor, uncovered, sunny, warm, or rainy context.
- Recognized chlorine additions, including dichlor, are estimated from the logged amount, unit, and pool volume, then included in the free chlorine prediction.
- pH drifts slowly toward a neutral/default target.
- Total alkalinity and CYA drift slowly, with rainfall treated as possible dilution context.
- Missing optional context falls back to neutral defaults.

Prediction sensors remain unknown until at least one actual water-test reading exists for that value. A chemical-addition record alone is not enough to invent an initial free chlorine baseline.

Weather context uses the configured weather entity's current attributes, and forecast attributes when the weather entity exposes them.

For chemical additions, Pool Tracker uses configured volume when available. If volume is missing, it falls back to a rough default by pool type and reports the volume source in `model_inputs`. This is still an estimate, not a dosing recommendation.

## Prepackaged UI

When Home Assistant frontend support is available, the integration registers a
`Pool Tracker` sidebar panel automatically. The panel opens as a normal
storage-mode Lovelace dashboard with concrete cards under `views` and `cards`,
so users can edit, remove, reorder, and copy the generated Lovelace elements
instead of being stuck with a single opaque strategy entry. Until the dashboard
is edited and saved, Pool Tracker regenerates the default card set from current
entities.

The sidebar panel is assembled from standard Lovelace cards for summaries,
latest readings, recent records, repeat-chemical actions, and recent-record
delete buttons. Pool Tracker does not register custom Lovelace cards or
strategies. If you edit and save the dashboard, Pool Tracker preserves your
layout. Use `pool_tracker.reset_dashboard` to discard saved dashboard edits and
return to the generated default layout.

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
  total_chlorine: 3.3
  total_alkalinity: 80
  total_hardness: 275
  source: dashboard
```

Omitted readings are not copied from previous tests into the new record.

Pool Tracker stores `event_timestamp` as the time the test happened and
`created_timestamp` as the time Home Assistant logged it. Home Assistant event
entities and Logbook entries are emitted when the service call is processed, so
their displayed state/change time can still say "now" for a backfilled record.
Use the Pool Tracker `event_timestamp` attribute for the actual historical test
time.

### `pool_tracker.log_chemical_addition`

Requires `chemical`, `amount`, and `unit`. `chemical` is selected from Pool
Tracker's supported chemical list, and `unit` is a Home Assistant mass or volume
unit, plus `Tbsp` for small-pool additions.

```yaml
service: pool_tracker.log_chemical_addition
data:
  chemical: dichlor
  amount: 1
  unit: Tbsp
  source: agent
```

Both log service actions return a `record_id` when called with Home Assistant service response support, and fire a `pool_tracker_record_created` event containing the record id, pool id, record type, event timestamp, and creation timestamp.

### `pool_tracker.delete_record`

Deletes one Pool Tracker record by exact `record_id`. This is intended for
corrections such as accidental dashboard taps. Deleting a record removes it from
Pool Tracker's source ledger and updates derived sensors and prediction data.

`confirm` must be `true`. `pool_id` is optional unless a manually supplied
record id exists in more than one pool.

```yaml
service: pool_tracker.delete_record
data:
  record_id: 3be90f44f47645929880ea7b0b89d86a
  confirm: true
```

Successful deletes return the deleted `record_id`, `pool_id`, and record `type`,
and fire a `pool_tracker_record_deleted` event. Home Assistant Recorder history
for earlier entity/event state changes is not rewritten.

### `pool_tracker.reset_dashboard`

Discards saved edits to the Pool Tracker Lovelace dashboard and returns the
sidebar panel to the generated default layout. `confirm` must be `true`.

```yaml
service: pool_tracker.reset_dashboard
data:
  confirm: true
```

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

## Dashboard Actions

Data entry stays backend-first through Home Assistant services. Use standard
Lovelace button/action cards for fixed or repeat actions instead of helper-backed
input fields, scripts, template sensors, or automations as storage glue.

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

Water-test fields are stored only when explicitly submitted. Supported water-test
readings include sanitizer, pH, alkalinity, hardness, stabilizer, salt, total
dissolved solids, phosphates, copper, iron, water temperature, and water clarity.
Chemical additions store chemical, amount, and unit.

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
- The bundled frontend is display-only; data entry still uses service actions.
- There is no chemistry guidance, dosing advice, equipment control, or verification that a logged action physically happened.
- Usage context is deferred. It is unclear whether this should be a boolean in-use/not-in-use signal, an event such as "used for 3 hours", or a more flexible proxied value. Future design should make it helpful without forcing one brittle interpretation.
