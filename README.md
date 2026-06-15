# Pool Tracker

Pool Tracker is a free, local-first Home Assistant custom integration for manual pool maintenance logging.

It stores an append-only event log for water tests and chemical additions, exposes read-only derived sensors, and registers narrow Home Assistant services that dashboards, automations, OpenClaw, or other agents can call.

## Scope

Pool Tracker v1 is recordkeeping only.

It does not provide chemical recommendations, dosing calculations, pump control, heater control, switch control, valve control, lock control, alarm control, outdoor power control, or automated dosing.

Logged chemical additions are human-entered records. They are not proof that a chemical was physically added.

Pool Tracker is independent of PoolMath, Leslie's, LaMotte, PoolSense, Flipr, Hanna, SEKO PoolDose, Vistapool, and other paid, cloud, or hardware services.

## Installation

### HACS

1. Add this repository as a HACS custom repository.
2. Select category `Integration`.
3. Install `Pool Tracker`.
4. Restart Home Assistant.
5. Go to **Settings > Devices & services > Add integration**.
6. Search for `Pool Tracker`.
7. Create the first pool. The integration entry is named `Pool Tracker`; the pool device display name defaults to `Pool`.

### Manual

1. Copy `custom_components/pool_tracker` into your Home Assistant config directory at `custom_components/pool_tracker`.
2. Restart Home Assistant.
3. Add the integration through **Settings > Devices & services**.

Do not configure this integration in YAML. Stable configuration is stored in a Home Assistant config entry.

## Pool Profile

The config entry stores a small pool profile for future calculations and record context:

- Volume and volume unit
- Pool type, such as outdoor, indoor, spa, or swim spa
- Surface type, such as plaster, vinyl, fiberglass, tile, or painted
- Sanitizer type, such as chlorine, salt chlorine generator, or bromine
- Default water-testing method

These attributes can be changed from the integration options. They are context only in v1; Pool Tracker still does not calculate chemical recommendations.

## Entities

Pool Tracker exposes read-only sensors derived from the event log:

- Last water test
- Last chemical addition
- Free chlorine
- pH
- Total alkalinity
- CYA/stabilizer
- Water clarity
- Chemical addition summary

These sensors are display surfaces. They are not mutable input fields.

## Services

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

Both services return a `record_id` when called with Home Assistant service response support, and fire a `pool_tracker_record_created` event containing the record id, pool id, and record type.

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

- V1 supports one configured pool, stored in a multi-pool-ready config shape.
- The backend and services are implemented first; a full custom panel is not included yet.
- There is no chemistry guidance, dosing advice, equipment control, or verification that a logged action physically happened.
