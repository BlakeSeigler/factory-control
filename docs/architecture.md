# Architecture

## 1. The line

A plastics recycling line. Cleaned plastic goes in, pellets come out:

```
 batch refill
     │  (when the shredder hopper's LOW switch uncovers)
     ▼
┌───────────────────────────┐    ┌──────────────────────────────────┐
│ SHREDDER UNIT        PLC 1│    │ EXTRUDER UNIT               PLC 2│
│ hopper on load cells      │───►│ hopper ─► screw ─► heated barrel │──► strands
│ (2 level switches)        │    │ (2 level switches)               │      │
│ rotor + motor             │    │ motor; barrel heater + PID       │      │
└───────────────────────────┘    └──────────────────────────────────┘      │
                                                                           ▼
                         ┌───────────────────────┐    ┌───────────────────────────┐
         pellets out ◄───│ PELLETIZER       PLC 4│◄───│ WATER BATH           PLC 3│
                         │ feed rolls + rotor    │    │ cools strands             │
                         │ (one motor)           │    │ water temperature sensor  │
                         └───────────────────────┘    └───────────────────────────┘
```

| Device | Actuators (writable over OPC UA) | Sensors / published values |
|---|---|---|
| Shredder | motor speed setpoint | hopper low/high switches, **hopper weight**, motor speed, current, temperature, vibration |
| Extruder | motor speed setpoint, **barrel temperature setpoint** | hopper low/high switches, motor speed, current, temperature, vibration, barrel temperature, heater output (PID output) |
| Water bath | none | water temperature |
| Pelletizer | motor speed setpoint | motor speed (more sensors to decide: D-10) |

**Line output** is the pellet mass flow leaving the pelletizer. It is measured
**indirectly** from the shredder hopper's weight (D-03, control.md §3).

Assumptions to confirm (decisions.md): strands pass through the bath *before*
the cutter (a standard strand-pelletizing line), the cutter is its own device with
its own PLC (D-10), and vibration sensors carry over from the earlier design to the
shredder and extruder (D-09).

## 2. Processes and data flow

```
SIMULATOR PROCESS  (fc sim)
  plant models (sim/) ── coupled by material flow ──────────────────────────────
     │            │              │              │
  PLC shredder  PLC extruder  PLC water_bath  PLC pelletizer       (plc/)
  :4841         :4842         :4843           :4844   ← one OPC UA server each
     │            │              │              │
═════╪════════════╪══════════════╪══════════════╪══════ OPC UA (opc.tcp) ═════
     │            │              │              │
SUPERVISOR PROCESS  (fc supervisor)
  DeviceClient × 4 (one session per PLC)
        └──► Bus (fan-out) ──► Historian ──► SQLite
                           ├─► StateCache ──► Controller ──► writes via DeviceClient
                           └─► AnalyzerEngine ──► alarms ──► Historian

DASHBOARD PROCESS  (fc dashboard): reads SQLite only ──► browser
```

### PLC = OPC UA server; supervisor = client

On real equipment each device has its own PLC, and modern PLCs host the OPC UA
server themselves (Siemens S7-1500, Beckhoff TwinCAT, CODESYS-based PLCs and others).
So each PLC is a **server**. The supervisor is **one client process with one
session per PLC**: four independent connections. Separate client *processes* per
device would add deployment and coordination cost and give no isolation benefit,
because one session already fails independently of the others.

### What runs where

| Layer | Runs in | Examples |
|---|---|---|
| Plant (physics) | `sim/` | motor dynamics, hopper mass balance, barrel heat balance |
| Device control | `plc/` | barrel temperature PID, cold-start interlock, shredder auto-reverse |
| Supervisory | `supervisor/` | analyzer, historian, line controller (baseline / MPC) |
| Presentation | `dashboard/` | charts |

The plant has only actuators and sensors. All control logic is in a PLC or the
supervisor. This mirrors reality, and it keeps physics code free of control
decisions.

## 3. Package layout and dependency rule

```
src/factory_control/
  config.py          typed config; devices are a discriminated union by type
  common/            tag contract (per device type) + message records
  sim/
    components/      motor, motor thermal, hopper, sensors, vibration
    devices/         shredder, extruder, water_bath, pelletizer plant models
    line.py          material coupling + batch refill;  faults.py
  plc/               generic PLC (OPC UA server + scan cycle), PID block,
                     extruder/shredder PLC logic, simulator runner
  supervisor/        DeviceClient, bus, historian, state, analyzer/, control/
  storage/           SQLite schema and access
  dashboard/         FastAPI + one static page
  cli.py             `fc` entry point
```

Dependencies point one way: `sim` ← `plc`; `storage` ← `supervisor`,
`dashboard`; everything ← `common`, `config`. **`supervisor` never imports `sim`
or `plc`**, so it can only know what a real supervisor connected to real PLCs could
know. The only exception is the simulator's ground-truth channel (D-14). It arrives
over OPC UA and is quarantined by tag name.

## 4. Structural decisions (detail in decisions.md)

| ID | Decision | Current choice |
|---|---|---|
| D-01 | Line composition | shredder → extruder → water bath → pelletizer |
| D-04 | PLC/supervisor topology | one OPC UA server per device; one supervisor with a session per PLC |
| D-05 | Simulator layout | one process, one asyncio loop, four servers: material coupling needs one integrator and one clock |
| D-06 | Time base | sim clock; every SourceTimestamp is sim time |
| D-14 | Ground truth | separate OPC UA namespace, own table, never read by the analyzer |

## 5. Status: scaffold only

| Part | Status |
|---|---|
| Config, tag contract, CLI | infrastructure, working |
| PLC plumbing: OPC UA servers, write handling, scan cycle, sim methods | infrastructure, working |
| Supervisor plumbing: clients, bus, historian, rule routing per device | infrastructure, working |
| Dashboard (motor speeds) | infrastructure, placeholder page |
| All physics (motor, hoppers, shredder, extruder, barrel, bath, pelletizer, sensors, refill, vibration) | **not implemented**: placeholders (speed = setpoint; all else held constant) |
| PLC logic (PID, interlock, auto-reverse, state tag) | **not implemented** |
| Fault effects and scenario playback | **not implemented** (faults can be injected and are recorded, but have no effect) |
| Analyzer rules | **not implemented** (routing only) |
| Estimator, baseline controller, MPC | **not implemented** |
| Tests | none, by request |
