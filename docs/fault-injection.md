# Fault injection: engineering "surprise"

## 1. Mechanism

A fault never edits a subsystem's internals. Each active fault contributes to one
`FaultEffects` record per device per step (`sim/faults.py`), and plant components
read only that record:

| Knob | Read by | Healthy |
|---|---|---|
| `load_torque_add_nm` | motor (via shredder rotor / extruder screw torque) | 0 |
| `throughput_mult` | shredder rotor, extruder intake | 1 |
| `heater_power_mult` | extruder barrel | 1 |
| `copper_loss_mult`, `thermal_resistance_mult` | motor thermal | 1 |
| `drive_accepts_setpoints` | motor/drive | True |
| `extra_vibration_tones` | vibration | [] |
| `sensor_overrides` | measurement layer | {} |

Adding a fault never edits physics code, and the full set of things a fault can
change is listed in one place. A fault that needs a new knob is an explicit design
change.

Fault sources:
- **Scenario files** (`config/scenarios/*.yaml`): timed and reproducible (file
  format defined; playback not implemented).
- **OPC UA method** `Simulation/InjectFault` on any device:
  `fc fault shredder shredder_jam '{"severity": 0.8}'`.
- **Random mode (proposed)**: a Poisson process per fault type with configurable
  mean time between failures, random severity and onset. The operator does not
  know when a fault happens. This is the real "surprise" test.

## 2. Time profile

| Profile | Example | What it tests |
|---|---|---|
| Step | heater band burns out, hard jam | detection delay |
| Ramp (incipient) | knife wear, screen clogging, bearing wear | sensitivity before a limit is crossed; baseline drift |
| Intermittent | a chunk that jams the shredder once a minute | on-delays, alarm chatter |
| Stochastic | switch chatter on flowing flakes | false-alarm robustness |

Every fault takes `severity ∈ [0,1]` and `profile ∈ {step, ramp(t), intermittent(period, duty)}`.

## 3. Catalog: mechanism → signature in OUR tags → who catches it

Signatures assume the recommended models (plant-model.md). "Rule 1/2/3" = setpoint
tracking / motor overtemp / vibration (analyzer.md).

| Fault | Device | Signature | Caught by |
|---|---|---|---|
| Shredder jam | shredder | current to limit; speed collapses; PLC auto-reverses (speed goes negative, then recovers) | Rule 1, **but** auto-reverse looks identical unless the PLC publishes its state (D-07, D-34) |
| Knife wear | shredder | slow: weight-loss rate per rpm falls; current per kg rises | nothing yet (trend on load-cell flow vs. speed) |
| Hopper bridging | extruder | output falls below K·N; extruder hopper "covered" yet the shredder-side balance stops adding up; current drops | estimator inconsistency (control.md §3); no rule yet |
| Heater failure | extruder | barrel temperature falls; **heater output pinned at 100 %** | nothing yet; "PID saturated + error growing" is an easy rule to add |
| Screen blockage | extruder | output per rpm falls slowly; current rises; **pressure would show it directly, but there is no pressure sensor** | nothing direct (D-08) |
| Winding short / fan blocked | shredder, extruder | motor temperature rises at same load | Rule 2 (rate-of-rise detects it earlier) |
| Bearing wear / misalignment | shredder, extruder | envelope / 2× energy | Rule 3 (shredder baseline is hard: plant-model.md §2.3) |
| Drive unresponsive | any motor | speed constant after setpoint change; current unchanged | Rule 1 |
| Strand break | pelletizer | nothing in our tags (pellets per strand change, line keeps running) | not observable (D-10: strand-break detector?) |
| Bath overheat | water bath | water temperature rises | sensor only for now |
| Refill late | shredder | low switch uncovered, weight keeps falling toward 0 | "low and no refill" rule on weight (proposed) |
| Sensor stuck / drift | any | frozen or biased value | Rule 1 false cause; cross-checks (current vs. speed) |
| Thermocouple open | extruder, motors | temperature reads full scale or a fault value; **barrel PID then cuts the heater** | plausibility check (an impossible rate of change) |

Conclusions to discuss:

1. **The three rules miss about half the catalog.** The cheapest additions are
   heater-saturation, refill-late, and an estimator-consistency check. All use
   tags we already have.
2. **PLC state must be published (D-07).** Shredder auto-reverse and the extruder
   cold-start interlock both make "speed ≠ setpoint" *correct* behavior. Without a
   state tag (Running / Reversing / Interlocked / Faulted), Rule 1 raises false
   alarms on every self-clearing jam.
3. **Sensor faults cause wrong root causes.** An open thermocouple looks like a
   barrel at 1000 °C and makes the PID cut the heaters. Real PLCs detect it as a
   wiring fault. Our PLC model should too.

## 4. Ground truth and scoring (D-14)

Each PLC exposes `Simulation/ActiveFaults` in a separate namespace. The historian
stores its transitions in `sim_ground_truth`, and the analyzer never reads it.
Per-rule metrics then come from the database alone: detection rate, detection
delay, and false alarms per hour.
