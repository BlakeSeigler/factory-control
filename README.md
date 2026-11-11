# factory-control

A simulated plastic-pellet line with two screw feeders in series. Each feeder runs
its own OPC UA server. A supervisor (OPC UA client) logs all data to SQLite,
runs real-time fault detection, and will compute RPM setpoints from a target
line mass flow using MPC. A minimal web dashboard plots the data.

**Status: scaffold.** The full data path works end to end (simulated motor →
OPC UA → supervisor → SQLite → dashboard). The physics beyond the motor, the
analyzer rules and the MPC are interfaces with documented candidate designs,
waiting on the decisions in [`docs/decisions.md`](docs/decisions.md).

## Quick start

Requires Python ≥ 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

```bash
./scripts/dev.sh            # simulator + supervisor + dashboard; Ctrl-C stops all
```

Open http://127.0.0.1:8000. In another terminal:

```bash
uv run fc setpoint feeder_1 1200
```

```bash
uv run fc setpoint feeder_2 900
```

```bash
uv run fc fault feeder_1 screw_jam '{"severity": 0.6}'   # recorded as ground truth; no physical effect yet
```

Or run the processes separately: `uv run fc sim [--scenario config/scenarios/feeder1_jam.yaml]`,
`uv run fc supervisor`, `uv run fc dashboard`.

Tests and lint:

```bash
uv run pytest
```

```bash
uv run ruff check . && uv run ruff format --check .
```

## Layout

```
config/line.yaml            single config for every process (machines, endpoints, params)
config/scenarios/           scripted fault scenarios
docs/                       design: start with architecture.md, then decisions.md
src/factory_control/
  common/                   tag contract + message records shared by server and client
  sim/                      plant model (no OPC UA): motor, screw, hopper, thermal,
                            vibration, sensors, faults, line coupling
  machine/                  OPC UA server per machine; simulator process loop
  supervisor/               OPC UA clients, bus, historian, analyzer/, control/
  storage/                  SQLite schema + access layer
  dashboard/                FastAPI + one static page (uPlot, vendored)
  cli.py                    `fc` command
tests/                      unit tests + an end-to-end OPC UA round-trip test
```

## Documentation

| Doc | Contents |
|---|---|
| [architecture.md](docs/architecture.md) | processes, data flow, dependency rules, what is implemented |
| [opcua.md](docs/opcua.md) | how OPC UA client/server works, subscriptions, writes vs. methods, security, our address space |
| [plant-model.md](docs/plant-model.md) | equations and options for motor, screw, hopper, thermal, vibration, sensors |
| [fault-injection.md](docs/fault-injection.md) | fault mechanism, catalog, observability, scoring against ground truth |
| [analyzer.md](docs/analyzer.md) | the three rules, their failure modes and options |
| [mpc.md](docs/mpc.md) | MPC from first principles, applied to this line; measurement limits |
| [data.md](docs/data.md) | schema, report-by-exception semantics, volume, retention |
| [decisions.md](docs/decisions.md) | every open design decision with options and a recommendation |
