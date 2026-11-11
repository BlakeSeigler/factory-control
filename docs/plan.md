# Plan

Each phase ends with something that runs and is tested. Physics comes before
detection and control, because rules and controllers can only be judged against a
plant that behaves plausibly.

| Phase | Content | Depends on decisions | Done when |
|---|---|---|---|
| 0 | **Scaffold** (done): config, tag contract, four PLC servers, supervisor, historian, dashboard, PID block, pelletizer geometry | — | `pytest` green; dashboard shows motor speeds |
| 1 | **Mass flow physics**: hoppers, batch refill, shredder and extruder throughput, pelletizer pass-through | D-02, D-16, D-17, D-21 | mass-balance test: refill in = pellets out + inventory change + losses, to numerical precision |
| 2 | **Drives and thermal**: motor model B (torque, current), motor thermal, barrel heat balance with shear coupling | D-15, D-18, D-23 | a jam stalls the motor; the barrel heats to setpoint under the PID |
| 3 | **PLC logic**: barrel PID tuning, cold-start interlock, shredder auto-reverse, state tag | D-07, D-26, D-27, D-28 | scenario tests: cold start, jam → reverse → recover |
| 4 | **Sensors and faults**: imperfections (incl. load-cell vibration coupling), fault effects, scenario library, random-fault mode | D-21, D-22, D-24, D-25 | each catalog fault produces its documented signature |
| 5 | **Analyzer**: rules 1–3 (+ cheap extras), replay harness, scoring against ground truth | D-32 … D-39 | detection rate, delay and false-alarm rate reported per rule |
| 6 | **Estimator + baseline control**: Kalman filter, feed-forward + trim, pellet-size ratio law | D-40, D-42, D-43, D-45 | target step: output settles, pellet mass within ±x % |
| 7 | **MPC** on the shredder + extruder section, benchmarked against phase 6 on the same scenarios | D-41, D-44, D-08 | measured improvement (or not) on defined scenarios |
| 8 | **Dashboard**: real views, alarms, target input | D-37, D-46 | — |

## Discussion order

We talk through each topic before implementing it. Topics in the order we need them:

1. **Confirmations** (short): bath before cutter, cutter PLC and sensors, vibration
   sensors, shredder type, refill delay model (D-09, D-10, D-16, D-02).
2. **Mass-flow physics** (phase 1): hoppers and bridging, shredder throughput,
   extruder output (drag/pressure flow), losses.
3. **Drives and thermal** (phase 2): motor model, barrel heat balance, why shear
   heating couples the loops.
4. **PLC behavior** (phase 3): PID tuning approach, interlock, auto-reverse, state tag.
5. **Synthetic sensors and surprise** (phase 4): imperfection models, fault
   mechanisms and time profiles, random-fault mode.
6. **Analyzer** (phase 5): each rule's design and failure modes, scoring.
7. **Estimation and control** (phases 6–7): estimator, baseline, MPC formulation,
   tuning.
