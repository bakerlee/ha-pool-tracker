# OpenClaw Contract

Pool Tracker is prepared for future OpenClaw integration through Home Assistant service calls only. This repo does not install an OpenClaw skill.

## Agent Surface

Agents should call:

- `pool_tracker.log_water_test`
- `pool_tracker.log_chemical_addition`

Agents should not write Home Assistant helpers, mutate Pool Tracker sensors, call equipment-control services, or infer dosing advice.

## Water Test

Use `pool_tracker.log_water_test` for partial readings.

```yaml
service: pool_tracker.log_water_test
data:
  ph: 7.2
  source: agent
```

Supported fields:

- `event_timestamp`
- `source`
- `notes`
- `free_chlorine`
- `ph`
- `total_alkalinity`
- `cya`
- `water_clarity`

At least one reading, clarity value, or note is required.

When backfilling, pass `event_timestamp` for when the test happened. Pool Tracker
will store that historical time, even though Home Assistant's event entity and
Logbook surfaces record the service call at the time it is processed.

## Chemical Addition

Use `pool_tracker.log_chemical_addition` for human-entered additions.

```yaml
service: pool_tracker.log_chemical_addition
data:
  chemical: dichlor
  amount: 0.5
  unit: oz
  source: agent
```

Required fields:

- `chemical`
- `amount`
- `unit`

`chemical` must be one of Pool Tracker's supported chemical values, and `unit`
must be a Home Assistant mass or volume unit such as `oz`, `lb`, `g`, `kg`,
`fl. oz.`, `mL`, `L`, or `gal`.

Optional fields:

- `event_timestamp`
- `source`
- `notes`

## Responses And Events

Services return a `record_id` when Home Assistant service responses are requested.

Every successful append fires `pool_tracker_record_created`:

```yaml
record_id: "..."
pool_id: pool
type: water_test
event_timestamp: "2026-06-15T00:30:00+00:00"
created_timestamp: "2026-06-16T14:00:00+00:00"
```

## Safety Boundary

OpenClaw should treat Pool Tracker as a record ledger. It must not use this integration to recommend dose sizes, control equipment, or assert that a logged addition physically occurred.
