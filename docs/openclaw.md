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

## Chemical Addition

Use `pool_tracker.log_chemical_addition` for human-entered additions.

```yaml
service: pool_tracker.log_chemical_addition
data:
  chemical: dichlor
  amount: 1
  unit: Tbsp
  source: agent
```

Required fields:

- `chemical`
- `amount`
- `unit`

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
```

## Safety Boundary

OpenClaw should treat Pool Tracker as a record ledger. It must not use this integration to recommend dose sizes, control equipment, or assert that a logged addition physically occurred.
