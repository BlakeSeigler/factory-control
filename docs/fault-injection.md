# Fault injection: engineering "surprise"

## 1. Mechanism

A fault never modifies a subsystem's internals. Each active fault contributes to a
single `FaultEffects` record per step (`sim/faults.py`), and subsystems read only
that record:

| Knob | Read by | Healthy value |
|---|---|---|
| `load_torque_add_nm` | motor (via screw torque) | 0 |
| `fill_factor_mult` | screw | 1 |
| `copper_loss_mult` | thermal | 1 |
| `thermal_resistance_mult` | thermal | 1 |
| `drive_accepts_setpoints` | motor/drive | True |
| `extra_vibration_tones` | vibration | [] |
| `sensor_overrides` | sensors | {} |

Why: adding a fault never edits physics code, and the complete set of things a
fault *can* change is listed in one place and can be reviewed. If a new fault
needs a knob that does not exist, adding the knob is an explicit design change.

Sources of faults:

- **Scenario files** (`config/scenarios/*.yaml`): timed, scripted, reproducible.
  Used for regression tests ("the jam scenario must raise Rule 1 within 10 s").
- **OPC UA method** `Simulation/InjectFault`: interactive, during a live run
  (`fc fault feeder_1 screw_jam '{"severity":0.6}'`).
- **Random mode (proposed)**: faults drawn from a Poisson process with a
  configurable mean time between failures, with random severity and onset. The
  operator does not know when they happen. This is the real test of "surprise".

## 2. Time profile of a fault

The onset shape matters as much as the fault type, because rules detect shapes:

| Profile | Example | What it tests |
|---|---|---|
| Step | breaker trip, sudden jam | detection delay |
| Ramp (incipient) | bearing wear over hours, fouled fan | sensitivity before a threshold is crossed; baseline drift |
| Intermittent | a sticking flight that jams once per minute | on-delay / debounce logic; alarm chatter |
| Stochastic | switch chatter | false-alarm robustness |

Proposal: every fault takes `severity ∈ [0,1]` and `profile ∈ {step, ramp(t_ramp),
intermittent(period, duty)}`.

## 3. Catalog: mechanism → observable signature → expected detection

Signatures assume the recommended models (plant-model.md §2 B, §5, §6).

| Fault | Layer | Knobs | Signature in OUR tags | Should be caught by |
|---|---|---|---|---|
| Screw jam (partial) | process | load torque ↑, fill ↓ | speed sags below setpoint once torque limit hit; temperature rises over minutes | Rule 1, later Rule 2 |
| Screw jam (hard) | process | load torque ≫ T_max | speed collapses to ~0 | Rule 1 |
| Drive unresponsive | process | setpoints ignored | speed constant after setpoint change | Rule 1 |
| Winding short | process | copper loss ↑ | temperature rises at same speed and load | Rule 2 (rate-of-rise earlier than threshold) |
| Fan blocked | process | R_th ↑ | temperature rises, mostly at low speed | Rule 2 |
| Bearing wear | process | bearing impulse train | high-frequency / envelope energy ↑ | Rule 3 |
| Misalignment | process | 2× tone ↑ | 2× order energy ↑ | Rule 3 |
| Hopper bridging | process | fill ↓ with material present | **nothing directly**. Downstream hopper drains, low switch eventually uncovers. Vibration noise floor drops. | not covered by Rules 1–3 |
| Loader failure | process | supply = 0 | feeder_1 low switch uncovers, then feeder_1 starves | not covered by Rules 1–3 |
| Sensor stuck | sensor | override | value frozen while setpoint moves | Rule 1 (false cause!) |
| Sensor drift | sensor | override offset ramp | slow bias | nothing yet |
| Switch chatter | sensor | random toggling | burst of transitions | nothing yet |

Conclusions from this table, to discuss:

1. **Several faults are invisible to the three rules with the current sensor
   set.** Bridging and loader failure only show up as level switch events much
   later. Adding **motor current** (D-04) would make jams, bridging (current
   *drops* at the same speed) and sensor-stuck faults directly visible. Real VFDs
   report current at no cost.
2. **Rule 1 cannot tell "drive unresponsive", "hard jam" and "speed sensor stuck"
   apart.** All three look like "speed does not follow setpoint". The alarm message
   must say *speed not following setpoint*, not *drive fault*, unless more signals
   are added.
3. Sensor faults are the main source of false root causes. A temperature-sensor
   step looks like a winding short unless rate-of-rise physics is used
   (temperature cannot physically jump 20 °C in 0.1 s given C_th).

## 4. Ground truth and scoring (D-12)

The simulator publishes `Simulation/ActiveFaults` in a separate namespace. The
historian stores its transitions in `sim_ground_truth`. The analyzer never reads
it; the client tags it `sim.active_faults` and the analyzer's rule inputs never
include that key.

With ground truth stored, analyzer quality can be measured per rule from the
database alone:

- **detection rate** (faults that produced an alarm)
- **detection delay** (fault onset → alarm raised)
- **false alarm rate** (alarms with no matching fault, per hour of operation)

These metrics turn tuning thresholds into an engineering decision that can be
measured.
