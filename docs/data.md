# Data and storage

Schema: `src/factory_control/storage/schema.sql`. Engine: SQLite in WAL mode. The
supervisor is the only writer; the dashboard opens the database read-only.

## Tables

| Table | Row means | Written by |
|---|---|---|
| `device` | a configured device, its type and endpoint | supervisor start-up |
| `sample` | scalar tag changed to `value` at `ts` (held until next row) | historian |
| `vibration_block` | one raw accelerometer block (float32 BLOB) | not yet written (D-30) |
| `setpoint_command` | a value the supervisor wrote to a writable tag, with `source` | control loop |
| `alarm_event` | rule raised/cleared | analyzer |
| `sim_ground_truth` | set of active injected faults changed | historian (sim only) |

Timestamps are unix seconds of **sim time** (OPC UA SourceTimestamp).

## D-29: narrow vs. wide samples

- **Narrow** (current): `(ts, device_id, tag, value)`. Adding a tag needs no
  migration, and report-by-exception data maps naturally onto it (each change is
  one row). Cost: more rows, and joining tags at a common time needs an
  as-of join.
- **Wide**: one row per device per tick, one column per tag. This suits analysis
  well, but it forces a fixed sampling grid and needs a migration for every new
  tag.

Narrow is the standard historian layout. We keep it and build wide views for
analysis when needed.

Rules for consumers of `sample` (report-by-exception semantics, opcua.md §2):
treat a row as a step that holds until the next row, compute time-weighted
averages, and never interpolate linearly.

## Volume estimates

- Scalars: about 11 continuously changing tags across the four devices (shredder
  weight, speed, current, temperature; extruder speed, current, temperature,
  barrel temperature, heater output; bath temperature; pelletizer speed) × up to
  10 Hz = 110 rows/s worst case (once sensor noise exists, every publish is a
  change) ≈ 9.5 M rows/day. At about 60–80 bytes per row including the index,
  that is roughly 0.7 GB/day.
  Mitigations: an absolute deadband on the subscription (D-11), and downsampled
  rollups with a retention window.
- Raw vibration (shredder and extruder): 2560 samples/s × 4 bytes = 10 kB/s per
  device ≈ 0.9 GB/day per device. Raising fs for envelope analysis multiplies this.

## D-30: vibration retention options

1. Store nothing raw; store only the analyzer's per-block features (KB/day).
2. Ring buffer: raw blocks for the last *H* hours, deleted after that.
3. Store raw only around alarms (e.g. 60 s before and after each raise).
4. Store everything (only viable for short experiments).

Recommendation: 1 + 3 for normal runs, plus a switch to enable 4 during analyzer
development so that runs can be replayed.

## When SQLite stops being enough

It is a single writer, which is fine here. Move to TimescaleDB, QuestDB or
InfluxDB if we need multiple writers, network access to the historian, or months
of retention with fast range queries. The `storage.db.Database` class is the only
place SQL lives, so the change is contained.
