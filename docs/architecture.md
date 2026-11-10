# Architecture

## 1. What the system does

A simulated plastic-pellet line with two screw feeders in series. Each feeder is
exposed as its own OPC UA server. A supervisor connects to both as an OPC UA client,
stores everything in SQLite, raises alarms in real time, and (later) computes RPM
setpoints for both feeders from a target line mass flow with MPC. A small web
dashboard reads the database.

```
                         SIMULATOR PROCESS (fc sim)
  ┌──────────────────────────────────────────────────────────────────────┐
  │  supply ──► [feeder_1: hopper → screw] ──► [feeder_2: hopper → screw] ──► line output
  │                  │  plant model (sim/)          │                     │
  │           FeederServer :4841             FeederServer :4842           │
  └──────────────────┼──────────────────────────────┼─────────────────────┘
                     │ OPC UA (opc.tcp)             │ OPC UA (opc.tcp)
  ┌──────────────────┼──────────────────────────────┼─────────────────────┐
  │           MachineClient                  MachineClient                │
  │                  └──────────┬───────────────────┘                     │
  │                        Bus (fan-out)                                  │
  │          ┌──────────────┬──┴───────────┬───────────────┐             │
  │      Historian      StateCache    AnalyzerEngine    (alarms)          │
  │          │               │              │                             │
  │          │          Controller ─► setpoint writes via MachineClient   │
  │          ▼                                                            │
  │       SQLite  ◄──────────────── alarms, setpoint commands             │
  │                    SUPERVISOR PROCESS (fc supervisor)                 │
  └──────────┼────────────────────────────────────────────────────────────┘
             │ read-only
       DASHBOARD PROCESS (fc dashboard) ── HTTP ──► browser
```

## 2. Package layout and dependency rule

```
src/factory_control/
  config.py              typed config (pydantic) loaded from config/line.yaml
  common/                contracts shared by both sides: tags, message records
  sim/                   plant model; numpy only, knows nothing about OPC UA
  machine/               OPC UA server per machine + simulator process loop
  supervisor/            OPC UA clients, bus, historian, analyzer/, control/
  storage/               SQLite schema and access
  dashboard/             FastAPI app + static page
  cli.py                 `fc` entry point
```

Dependency direction is one-way: `sim` ← `machine`; `storage` ← `supervisor`,
`dashboard`; everything ← `common`, `config`. **`supervisor` never imports `sim`.**
That rule is what keeps the supervisor honest: it can only know what a real
supervisor connected to real machines could know. The single exception is the
sim-only ground-truth channel (D-12), which arrives over OPC UA like everything
else and is quarantined by tag name.

## 3. Key structural decisions (detail in decisions.md)

| ID | Decision | Current choice |
|----|----------|----------------|
| D-01 | Line topology | Series: feeder_1 fills feeder_2's hopper |
| D-05 | Simulator process layout | One process, one asyncio loop, two independent OPC UA servers |
| D-07 | Time base | Sim clock; every SourceTimestamp is sim time; `time_scale` configurable |
| D-12 | Fault ground truth | Separate OPC UA namespace, logged to its own table, never read by the analyzer |
| D-16 | Historian layout | Narrow table (ts, machine, tag, value), report-by-exception |
| D-18 | Internal bus | Per-consumer bounded queues, drop-oldest on overflow |
| D-19 | Analyzer clock | Sample (source) time, so live, accelerated and replay runs behave the same |

### Why one simulator process hosting two servers (D-05)

The two feeders are coupled by *material*, not by data: feeder_1's discharge is
feeder_2's inflow at every physics step. That coupling belongs inside one
integrator with one clock. If each machine ran in its own process, we would need
a second channel to move mass between them and would have to synchronize two
clocks. That is extra machinery with no modeling benefit. The supervisor still sees two
independent servers on two ports with two sessions, which is indistinguishable
from two physical machines. Cost: one simulator crash takes down both "machines".
For a simulator that is acceptable.

### Why one supervisor process

Clients, historian, analyzer and controller share one asyncio loop and talk through
an in-process bus. That makes deployment simple, adds no serialization, and gives
one place to reason about timing. Each component consumes its own queue and has no
reference to the others, so splitting one out later (e.g. the analyzer as its own
OPC UA client) is a local change. If any component task crashes, the supervisor
exits instead of continuing with a silently dead historian or analyzer.

### Why the dashboard only reads the database

It cannot issue commands because it has no connection to the machines (D-40).
Being read-only by construction is a stronger guarantee than read-only by policy.

## 4. Responsibilities that are deliberately NOT in the supervisor

In a real plant, protective functions (motor thermal trip, high-level stop of the
upstream feeder, E-stop) run in the machine's own PLC/drive, because they must
work when the network or the supervisor is down. Our analyzer only *flags*.
Whether the simulator should model these local protections is D-41. It should,
because their effects (a tripped motor) are part of what the supervisor observes.

## 5. Status of each part

| Part | Status |
|------|--------|
| Config, tags contract, CLI | Implemented |
| OPC UA servers (address space, setpoint write path, sim methods) | Implemented |
| OPC UA clients (subscribe, reconnect, write) | Implemented |
| Historian (scalar samples, ground truth, alarms, commands) | Implemented |
| Dashboard (RPM chart) | Implemented (placeholder) |
| Motor model | Placeholder first-order lag + ramp limit |
| Screw, hopper, thermal, vibration, sensors | Interfaces only; values held constant |
| Fault injection | Data model, scenario player and OPC UA methods; faults have no physical effect yet |
| Analyzer rules | Interfaces + routing; rules return no alarms yet |
| Controller | Manual (no-op) works; MPC, model and estimator are stubs |
