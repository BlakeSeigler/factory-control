# Decision register

This register replaces the earlier two-feeder register entirely. Each open design
choice has an ID that the code and docs refer to (`TODO(D-xx)`).

**Status:** Open = to discuss; Provisional = scaffolded this way, revisit;
Decided = agreed with Blake.

## System

| ID | Question | Options | Recommendation | Status |
|---|---|---|---|---|
| D-01 | Line composition | — | refill → shredder unit → extruder unit → water bath → pelletizer (bath before cutter, confirmed) | Decided |
| D-02 | Refill of the shredder hopper | — | batch on low switch, brought by **a person: random delay**. Open: delay distribution, overflow handling | Decided / detail open |
| D-03 | Throughput measurement | load cell on shredder hopper | decided; output = feed − losses over switch-to-switch intervals (control.md §3) | Decided |
| D-04 | PLC/supervisor topology | one OPC UA server per device; one supervisor with one session per PLC / client process per device | one supervisor, one session per PLC | Provisional |
| D-05 | Simulator layout | one process with four servers / one process per device + material channel | one process (material coupling needs one clock) | Provisional |
| D-06 | Time base and speed | real time / accelerated / shortened time constants | sim clock everywhere; accelerate for thermal tests | Provisional |
| D-07 | Publish PLC state (Running / Reversing / Interlocked / Faulted) | yes / no | **yes**: needed so Rule 1 does not flag auto-reverse and interlocks | Open |
| D-08 | Extra extruder sensors at the die | melt pressure / melt temperature / both; barrel temperature stays either way | add both; **keep barrel temperature** (it is what the barrel PID controls) | Open: awaiting Blake |
| D-09 | Vibration sensors on shredder and extruder | — | yes | Decided |
| D-10 | Pelletizer: drive arrangement and sensors | — | one motor driving feed rolls and rotor; sensors: speed, motor current, motor temperature. strand-break detector added (D-47) | Decided |

## OPC UA

| ID | Question | Options | Recommendation | Status |
|---|---|---|---|---|
| D-11 | Subscription parameters | defaults / per-tag sampling, queue, deadband | per-tag; absolute deadband on noisy analogs | Open |
| D-12 | Security | None / Sign / SignAndEncrypt + certificates | None on localhost only; SignAndEncrypt before any real network | Provisional |
| D-13 | Out-of-range writes | clamp (current) / reject BadOutOfRange / write back / AppliedSetpoint tag | reject + applied-value tag | Open |
| D-14 | Fault ground truth | separate namespace + table, quarantined from analyzer | as is | Provisional |

## Plant model (plant-model.md)

| ID | Question | Options | Recommendation | Status |
|---|---|---|---|---|
| D-15 | Motor/drive | first-order lag (current) / speed loop + torque limit / full machine model | speed loop + torque limit | Open |
| D-16 | Shredder type and model | — | **single-shaft** (rotor + hydraulic ram + screen); stochastic torque and jam model still to design | Decided / model open |
| D-17 | Extruder output model | K·N / drag − pressure flow with die and screen / + starve and feed-limited intake | drag − pressure + starve + feed cap | Open |
| D-18 | Barrel thermal model | one lumped zone (as specified) / multi-zone; shear coupling; cooling? | one zone with shear coupling; note the lack of cooling | Open |
| D-19 | Strand dynamics | none (current) / draw-down, sag, breaks | draw-down + break probability | Open |
| D-20 | Water bath model | pass-through (current) / heat balance | deferred as requested | Open |
| D-21 | Hopper, switch and load-cell models | ideal (current) / hysteresis, bridging, scale noise and **vibration coupling**, refill hold | all of these | Open |
| D-22 | Sensor imperfections | ideal / per-sensor, switchable | per-sensor, switchable one at a time | Open |
| D-23 | Motor thermal model and sensor location | 1-node / 2-node; winding / frame | 2-node; decide location | Open |
| D-24 | Vibration signal model and sampling | tones / impulse-resonance bearings / shredder impacts; fs, block length | impulse model + shredder impacts; fs set by D-36 | Open |
| D-25 | Recycled-material model and losses | constant / per-batch lots; moisture, fines, rejects | per-batch lot properties + loss fraction | Open |

## Local control (PLC)

| ID | Question | Options | Recommendation | Status |
|---|---|---|---|---|
| D-26 | Barrel PID | structure (PID / PI), time-proportioning cycle, tuning method | PI + time-proportioning; tune on the model | Open |
| D-27 | Shredder overload auto-reverse | thresholds, reverse time, retries, fault after N | standard routine; parameters to choose | Open |
| D-28 | Extruder cold-start interlock | screw blocked below min barrel temperature (+ soak time?) | yes, with soak time | Open |

## Data

| ID | Question | Options | Recommendation | Status |
|---|---|---|---|---|
| D-29 | Historian layout | narrow (current) / wide | narrow | Provisional |
| D-30 | Vibration retention | none / ring / around alarms / everything | features + around alarms; full capture as a dev switch | Open |
| D-31 | Bus overflow | drop oldest (current) / block / lossless historian | drop oldest with counters | Provisional |

## Analyzer (analyzer.md)

| ID | Question | Options | Recommendation | Status |
|---|---|---|---|---|
| D-32 | Analyzer clock and stale data | sample time + separate comm-loss condition | as recommended | Provisional |
| D-33 | Rule 1 timing | fixed 15 s (current) / from drive dynamics / model residual | dynamics-based first | Open |
| D-34 | Rule 1 vs. PLC overrides | suppress on PLC state / re-derive PLC logic | suppress on state (needs D-07) | Open |
| D-35 | Rule 2 thresholds and extensions; barrel-deviation rule | thresholds / + rate-of-rise / + barrel rule | thresholds + rate-of-rise; add barrel rule | Open |
| D-36 | Rule 3 method and baseline | band z-scores / robust stats / envelope; shredder baseline by throughput | robust, binned by speed and throughput | Open |
| D-37 | Alarm lifecycle | raise/clear (current) / + acknowledge / + shelve | add acknowledge before the dashboard shows alarms | Open |
| D-38 | Current-based detection | none / overload / sustained rise | none; current logged only | Decided |
| D-39 | Additional cheap rules from fault-injection.md §3 | heater saturation, refill late, estimator consistency, strand count dropped | discuss | Open |

## Supervisory control (control.md)

| ID | Question | Options | Recommendation | Status |
|---|---|---|---|---|
| D-40 | Baseline supervisory controller | switch logic / feed-forward + PI trim | build first as the benchmark | Open |
| D-41 | MPC scope | whole line / shredder + extruder section / none | section MPC; pelletizer as a ratio follower outside it | Open |
| D-42 | Estimator | dead reckoning / Kalman filter with switch events and scale | Kalman filter | Open |
| D-43 | Pellet-size law: which throughput signal | load-cell flow / K̂·N with slow calibration | K̂·N + transport delay | Open |
| D-44 | MPC tooling | cvxpy + OSQP / OSQP / CasADi / do-mpc | cvxpy + OSQP | Open |
| D-45 | Line target input | CLI / DB row / HTTP on supervisor / OPC UA server on supervisor | HTTP on supervisor | Open |

## Dashboard

| ID | Question | Options | Recommendation | Status |
|---|---|---|---|---|
| D-46 | Dashboard coupling | read-only DB reader (current) / talks to supervisor | read-only by construction | Provisional |

## Added after the assumption review

| ID | Question | Options | Recommendation | Status |
|---|---|---|---|---|
| D-47 | Strand-break detection on the pelletizer | — | **added**: one presence sensor per strand (`Strands/Present`), PLC publishes `Strands/Count`. Open: what the PLC does on a break (alarm / slow / stop) | Decided / reaction open |
