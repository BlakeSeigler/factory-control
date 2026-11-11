# factory-control

A simulated plastics recycling line:

```
batch refill → shredder unit → extruder unit → water bath → pelletizer → pellets
```

Each device has its own (simulated) PLC hosting its own OPC UA server. A
supervisor (one OPC UA client session per PLC) logs everything to SQLite,
will run real-time fault detection and compute setpoints from a target pellet
output (baseline control, then MPC). A minimal web dashboard plots the data.

**Status: scaffold only.** The infrastructure carries data end to end for all four
devices: plant → PLC → OPC UA → supervisor → SQLite → dashboard. Nothing behind it is
implemented. The physics are placeholders (motor speed equals its setpoint
immediately; every other value is held constant). PLC logic, analyzer rules and
controllers are empty interfaces. Designs are discussed in [`docs/`](docs/) and
decided in [`docs/decisions.md`](docs/decisions.md); the phases are in
[`docs/plan.md`](docs/plan.md).

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
uv run fc write extruder motor.speed_setpoint_rpm 900
```

```bash
uv run fc write extruder barrel.temperature_setpoint_c 210
```

```bash
uv run fc fault shredder shredder_jam '{"severity": 0.8}'   # recorded only; faults have no effect yet
```

Lint:

```bash
uv run ruff check . && uv run ruff format --check .
```

## Layout

```
config/line.yaml       single config for every process (devices, endpoints, parameters)
config/scenarios/      scripted fault scenarios
docs/                  design docs; start with architecture.md, decisions.md, plan.md
src/factory_control/
  common/              tag contract per device type + message records
  sim/                 plant models: components/ (motor, hopper, sensors, ...),
                       devices/ (shredder, extruder, water bath, pelletizer), line coupling, faults
  plc/                 simulated PLCs (OPC UA server + scan cycle), PID block (stub), runner
  supervisor/          OPC UA clients, bus, historian, analyzer/, control/
  storage/             SQLite schema + access
  dashboard/           FastAPI + one static page (uPlot, vendored)
  cli.py               `fc` command
```

## Documentation

| Doc | Contents |
|---|---|
| [architecture.md](docs/architecture.md) | the line, devices and tags, processes, layers, status |
| [plan.md](docs/plan.md) | implementation phases and the order in which we discuss topics |
| [decisions.md](docs/decisions.md) | every open design decision with options and a recommendation |
| [plant-model.md](docs/plant-model.md) | physics of each device, sensors, losses, recycled-material effects |
| [control.md](docs/control.md) | control layers, PIDs, measurement and estimation, baseline, pellet-size law, MPC |
| [fault-injection.md](docs/fault-injection.md) | fault mechanism, catalog with signatures, scoring |
| [analyzer.md](docs/analyzer.md) | the three rules and their failure modes |
| [opcua.md](docs/opcua.md) | OPC UA client/server, subscriptions, writes vs. methods, security, address space |
| [data.md](docs/data.md) | schema, report-by-exception semantics, volume, retention |
