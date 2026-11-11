# Decision register

Every open design choice has an ID that the code and docs refer to (`TODO(D-xx)`).
Status: **Open** = to discuss; **Provisional** = scaffolded this way, revisit;
**Decided** = agreed.

## System and topology

| ID | Question | Options | Recommendation | Status |
|---|---|---|---|---|
| D-01 | How are the two machines related? | series buffer stage / parallel blend (ratio control) / independent | series (as briefed); confirm | Provisional |
| D-02 | What feeds feeder_1's hopper? | infinite / constant / loader on switches / batch refill on low | **batch refill when feeder_1's low switch uncovers**; open: fixed vs. random response delay, overflow handling | Decided |
| D-03 | Is mass flow measured, and where? | none / catch-weight / LIW on feeder_2 / weigh hopper at extruder / flow meter / weighed bin on feeder_1 | **load cell under feeder_1's bin**; gives ṁ₁ between refills and long-run line throughput (mpc.md §2) | Decided |
| D-04 | Add motor current tag? | no / yes | `Motor/Current` added; sim value 0 until torque model (D-10) | Decided |
| D-05 | Simulator process layout | one process, two servers / one process per machine + material channel | one process, two servers | Provisional |
| D-07 | Time base and speed | real time / accelerated (`time_scale`) / shortened time constants | sim clock everywhere (done); accelerate for thermal tests | Provisional |
| D-41 | Model machine-local protection (thermal trip, interlocks)? | no / yes | yes. A real supervisor observes trips | Open |

## OPC UA

| ID | Question | Options | Recommendation | Status |
|---|---|---|---|---|
| D-06 | Subscription parameters | defaults / per-tag sampling interval, queue, deadband | per-tag; absolute deadband on noisy analogs | Open |
| D-08 | Security | None / Sign / SignAndEncrypt + certificates | None on localhost only; SignAndEncrypt before any real network | Provisional |
| D-09 | Out-of-range setpoint write | clamp silently (current) / reject `BadOutOfRange` / write back clamped / add `AppliedSetpoint` tag | reject + `AppliedSetpoint` | Open |
| D-12 | Fault ground truth | separate namespace + table, quarantined from analyzer / not exposed | separate namespace (done) | Provisional |

## Plant model

| ID | Question | Options | Recommendation | Status |
|---|---|---|---|---|
| D-10 | Motor/drive fidelity | first-order lag (current) / speed loop + torque limit + mechanics / full induction machine | speed loop + torque limit | Open |
| D-11 | Screw flow and torque | constant fill / fill vs. level, OU bulk density, pulsation | fill vs. level + OU density; pulsation optional | Open |
| D-13 | Hopper switch model | ideal mass threshold (current) / threshold + hysteresis + debounce + crossing jitter / full geometry | thresholds in kg + hysteresis + debounce + jitter | Open |
| D-14 | Sensor imperfections | ideal (current) / per-sensor models, switchable | per-sensor, switchable one at a time | Open |
| D-15 | What "motor temperature" is | winding RTD / frame thermocouple; 1-node / 2-node | 2-node model, choose sensor location explicitly | Open |
| D-21 | Vibration sampling | fs, block length (resolution vs. time resolution vs. speed smear) | depends on D-22 (envelope analysis needs higher fs) | Open |

## Data

| ID | Question | Options | Recommendation | Status |
|---|---|---|---|---|
| D-16 | Historian layout | narrow (current) / wide | narrow | Provisional |
| D-17 | Vibration retention | none / ring buffer / around alarms / everything | features + around alarms; full capture as a dev switch | Open |
| D-18 | Bus overflow policy | drop oldest (current) / block / lossless for historian | drop oldest, but count and alarm; revisit if historian completeness matters | Provisional |

## Analyzer

| ID | Question | Options | Recommendation | Status |
|---|---|---|---|---|
| D-19 | Analyzer clock and stale data | sample time (current) + separate comm-loss condition | as recommended | Provisional |
| D-20 | Rule 1 timing | fixed timeout (now 15 s) / timeout from drive dynamics / model residual | dynamics-based first, residual later | Open |
| D-22 | Rule 3 method | band z-scores / Mahalanobis / spectral distance / ML; baseline policy | order-band z-scores, speed-binned baseline learned on command, ISO backstop | Open |
| D-23 | Rule 2 extras | thresholds only / + rate of rise / + model residual | thresholds + rate-of-rise | Open |
| D-24 | Alarm lifecycle | raise/clear (current) / + ack / + shelving | add ack before alarms reach the dashboard | Open |
| D-25 | Current-based detection | absolute limit / sustained rise / none | **none**; current is logged only (analyzer.md §4) | Decided |
| D-26 | Load cell model and refill handling | ideal / noise + screw-vibration coupling + drift; freeze vs. model-based flow during refill | noise + vibration coupling; freeze-and-hold during refill (industry practice) | Open |

## Control

| ID | Question | Options | Recommendation | Status |
|---|---|---|---|---|
| D-30 | How the line target is set | CLI / DB row / supervisor HTTP / supervisor as OPC UA server | supervisor HTTP endpoint | Open |
| D-31 | Baseline controllers | Tier 0 switch logic / Tier 1 feed-forward + PI / straight to MPC | build Tiers 0 and 1 first as benchmarks (mpc.md §6) | Open |
| D-32 | Prediction model | linear (+ disturbance state) / nonlinear | linear + disturbance state | Open |
| D-33 | Hopper mass estimator | dead reckoning / KF with event updates + projection / MHE | KF + projection | Open |
| D-34 | MPC tooling | cvxpy+OSQP / raw OSQP / CasADi / do-mpc | cvxpy+OSQP | Open |
| D-35 | Ts, horizon, static motors | — | Ts = 1 s, N·Ts ≈ minutes; discuss static-motor simplification | Open |

## Dashboard

| ID | Question | Options | Recommendation | Status |
|---|---|---|---|---|
| D-40 | Dashboard scope and coupling | read-only DB reader (current) / talks to supervisor | read-only, by construction | Provisional |
