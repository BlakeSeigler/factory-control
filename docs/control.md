# Control: from a target pellet output to every setpoint

## 1. Control layers: who controls what

Industrial control is layered. Each layer gives setpoints to the layer below and
runs faster than the layer above:

| Layer | Where | Period | Loops in this line |
|---|---|---|---|
| 0. Drives | inside each VFD | ~ms | motor speed loops (shredder, extruder, pelletizer) |
| 1. Regulatory / local | each device's PLC | 10–100 ms scan | barrel temperature PID; extruder cold-start interlock; shredder overload auto-reverse; batch-refill request |
| 2. Supervisory | supervisor (this repo) | ~1 s | throughput coordination: extruder speed, shredder speed (buffer), pelletizer speed (pellet size); possibly barrel setpoint |
| 3. Planning | out of scope | minutes–days | production targets, recipes |

Rule: **a layer never bypasses the one below it.** The supervisor writes a barrel
*setpoint*, never a heater duty. Layers 0 and 1 must keep the equipment safe even
when the supervisor or the network is down. That is why interlocks belong in
the PLC.

## 2. Do you need to write the PIDs?

**On real equipment, mostly no.**

- **Motor speed loops** run inside the VFD. You set parameters (motor nameplate
  data, acceleration ramps, current limit, often an autotune run). You do not
  write code.
- **Barrel temperature PID**: every PLC platform ships a standard PID function
  block with anti-windup and usually autotuning (Siemens PID_Compact /
  PID_Temp, Rockwell PIDE, the CODESYS PID library). You place it, wire
  thermocouple → block → heater output, and **tune** it. Tuning is the real work:
  barrel zones have long lags, so aggressive gains cause sustained oscillation.
- Logic such as interlocks and auto-reverse is written, typically in IEC 61131-3
  languages (ladder, structured text) on the PLC.

**In this simulation, yes, once.** There is no PLC, so `plc/pid.py` plays the
role of that standard block. It is implemented and tested: derivative on
measurement (no kick on setpoint changes), anti-windup by conditional integration,
and output clamping. The extruder PLC already runs it for the barrel. Drive speed
loops are part of the motor model (plant-model.md §2.1). What remains is tuning,
which needs the barrel thermal model first (D-18, D-26).

## 3. What is measured, and what must be estimated

| Quantity | How we know it |
|---|---|
| Shredder feed rate ṁ_s | **measured**: −dM_s/dt from the hopper load cell, valid between refills |
| Extruder output ṁ_e (≈ pellet output) | **estimated**: K̂_ext·N_screw (fast); K̂_ext re-calibrated slowly (below) |
| Extruder hopper mass M_e | **estimated**: integrate ṁ_s − ṁ_e; bounded by switch states; corrected at transitions |
| Pellet mass | **inferred** from ṁ_e and pelletizer speed (plant-model.md §3.5); not measured |

**Why the first-hopper measurement is a long-run measurement.** Two buffers sit
between the scale and the pellets: the extruder hopper and the barrel. Short-term,
the shredder can run faster or slower than the extruder, so ṁ_s ≠ ṁ_e. But over
any interval that starts and ends at the **same extruder-hopper switch
transition**, the extruder hopper holds the same mass at both ends, so

    ∫ ṁ_e dt  =  ∫ ṁ_s dt − losses           (measured by the scale)
    K̂_ext     =  ∫ ṁ_s dt / ∫ N_screw dt      (re-calibrates the fast estimate)

The scale therefore measures line throughput on long timescales and keeps
calibrating the fast estimate K̂_ext·N used on short timescales. Losses
(moisture, fines, rejects) bias it (plant-model.md §1). During a refill the scale
reads inflow and outflow mixed together. Standard practice is to hold the last
good flow value until the pour ends and the scale settles (D-21).

Estimator design (D-42): a Kalman filter with M_e and K_ext (plus a loss
fraction) as states. Its prediction is the mass balance, and its corrections come
from scale readings and switch transitions. A switch transition is an exact-level
event, and between transitions the switch states bound M_e.

## 4. Baseline supervisory controller (no MPC) (D-40)

With target pellet output m*:

    extruder    N_e   = m* / K̂_ext                                   feed-forward
    pelletizer  n_p   = ṁ̂_e / (s · z · b · m_p*)                      ratio (section 5)
    shredder    N_s   = m* / K̂_shr + Kp·(M_e,ref − M̂_e) + Ki·∫(...)   buffer trim
    barrel      setpoint from recipe/operator; the PLC's PID holds it

Why each piece works:

- **Feed-forward** puts every device at its steady-state speed immediately, so a
  target change moves the whole line together.
- **The buffer trim** is needed because M_e integrates the mismatch ṁ_s − ṁ_e.
  A P term gives first-order return to the reference, with time constant
  `1/(K_shr·Kp)`. The I term removes the offset that a constant mismatch would
  leave.
- **Switch-only version** (simplest, no estimator): shredder at +b % when the
  extruder hopper's low switch uncovers, −b % when the high switch covers. This
  is what a PLC programmer would write, and it is a legitimate first step.

## 5. Pellet size control (D-43)

From plant-model.md §3.5, `m_p = ṁ_e / (s·z·b·n)`, so holding m_p at m_p* needs

    n_pelletizer = ṁ_e / (s · z · b · m_p*)

This is **ratio control**: the cutter follows throughput. It has no dynamics worth
optimizing. The question is which ṁ_e to use:

- The load-cell flow is two buffers upstream and, short-term, wrong. Using it
  directly would change pellet size every time the shredder speeds up.
- **Use the fast estimate K̂_ext·N_screw** (feed-forward from what the extruder
  is actually doing), with K̂_ext calibrated slowly by the scale (§3). Add the
  extruder's transport delay (melt residence time) so the cutter changes speed
  when the material actually arrives.

Holding n ∝ ṁ also keeps the strand draw-down constant, which prevents breaks and
sagging (plant-model.md §3.5). One law serves both goals.

## 6. MPC in one page

Every control period (e.g. 1 s):

1. **Estimate** the current state from measurements (§3).
2. **Predict** the plant's future over a horizon of N steps with a model, as a
   function of a candidate sequence of future setpoints.
3. **Optimize**: choose the sequence that minimizes a cost (tracking error +
   control effort) **subject to constraints** (speed and ramp limits, motor
   temperature, heater not saturated, hopper levels).
4. **Apply only the first move**, then repeat from fresh measurements next period
   (receding horizon).

Feedback enters only through step 1: a poor estimator gives a poor MPC.

PID versus MPC: PID applies a fixed rule (gain × error) to one variable and
handles limits by clipping afterwards. MPC chooses the best future moves for **all**
actuators **within** the limits, with explicit priorities. Industrially, MPC is a
**supervisory layer that writes setpoints to PID loops**, which is exactly layer 2 above.

## 7. Is MPC justified for this line?

MPC earns its complexity when one or more of these is true:

1. constraints are active in normal operation;
2. real multivariable coupling exists;
3. explicit trade-offs are needed ("protect X, give up some Y");
4. future changes are known in advance (preview);
5. dead time is significant relative to the dynamics.

The earlier two-feeder line met almost none of these. This line meets several:

| Criterion | In this line |
|---|---|
| Active constraints | Pushing throughput runs into shredder torque (jams), extruder motor current/temperature, and **barrel heater saturation at 0 %** (shear heating at high screw speed, no cooling). These limits are where the economic optimum sits. |
| Coupling | Screw speed drives both output *and* barrel temperature (shear heating). The barrel PID and the throughput loop interact. Mass flow is still a chain (shredder → buffer → extruder → cutter), but the thermal coupling is a genuine 2×2 interaction. |
| Trade-offs | Throughput against melt temperature, motor limits and buffer safety. |
| Preview | Refill timing: the time a batch takes to arrive is known when the hopper goes low. MPC can slow the line before the shredder starves instead of reacting after. |
| Dead time | Melt residence in the barrel and strand transport delay output changes by a minute or more. |

**Verdict:** MPC is justified for the **shredder + extruder throughput section**
when the line is run near its limits. Two caveats:
- The thermal side of the model is weakly observed. We measure barrel temperature
  but not melt temperature or pressure, so predictions of the shear-heating
  interaction will be uncertain. A melt pressure and a melt temperature sensor at
  the die (standard on extruders) would strengthen this considerably (D-08).
- The baseline (§4) still comes first, so we can *measure* what MPC adds.

## 8. Whole system or parts? (D-41)

Industrial practice is **not** one MPC for a whole plant. MPCs are applied per
**unit or section** where interactions and constraints are strong. They are
coordinated hierarchically by passing targets between them, under a slower
optimization layer. Reasons:
- **Model quality:** one huge model is harder to identify and maintain, and
  an error anywhere degrades everything.
- **Robustness:** if one section's MPC is switched off (maintenance, model
  failure), the rest keeps running.
- **Understandability:** operators must be able to predict what the controller
  will do. Smaller scopes help.
- **Time scales:** fast algebraic relations (the cutter ratio) gain nothing from a
  horizon-based optimizer and would only add tuning burden.

**Recommendation for this line:**

| Part | Controlled by |
|---|---|
| Shredder speed, extruder speed (+ barrel setpoint, optionally) | **one MPC** over the throughput section |
| Pelletizer speed | ratio follower of the estimated extruder output (§5), outside the MPC |
| Barrel heater duty | PLC PID (layer 1), never the MPC |
| Water bath | nothing yet (sensor only) |

## 9. Candidate MPC formulation (section MPC)

States `x = [M_e, N_s, N_e, T_b, d]`: extruder hopper mass, shredder and extruder
speeds, barrel temperature with its PID loop closed, and a disturbance/calibration
state d (offset-free MPC). Optional slow states: motor temperatures.

Inputs `u = [N_s,sp, N_e,sp, (T_b,sp)]`. Measured disturbance: shredder hopper
mass and refill status.

    minimize   Σₖ q_f·(ṁ_e[k] − m*)² + q_m·(M_e[k] − M_ref)² + q_T·(T_b[k] − T_ref)² + ΔuᵀRΔu
    subject to model;  speed and ramp limits;
               I_motor ≤ I_max;  T_motor ≤ T_max;  0 < heater duty < 100 (soft);
               M_low ≤ M_e ≤ M_high (soft);  ṁ_e ≤ sustainable supply (from refill timing)

The model is linear in the mass balance and mildly nonlinear in the thermal
coupling. Start linear: linearize around the operating point and add disturbance
states. Constraints on states are soft (slack variables), so the QP never becomes
infeasible after a disturbance.

## 10. Tooling (D-44)

| Option | Pros | Cons |
|---|---|---|
| cvxpy + OSQP | formulation reads like the math; compile once with Parameters | hides the QP matrices |
| OSQP directly | you own every matrix | more code, easy indexing mistakes |
| CasADi (+ IPOPT) | nonlinear MPC if the thermal coupling needs it | heavier to learn |
| do-mpc | framework with estimator and simulator built in | its conventions to learn |

Recommendation: cvxpy first, so the math stays readable. Move to CasADi only if
linear models prove inadequate.

## 11. How the target gets in (D-45)

Open: a CLI command, a database row the supervisor polls, an HTTP endpoint on the
supervisor, or an OPC UA server on the supervisor. Recommendation: a small HTTP
endpoint on the supervisor. The dashboard stays read-only by design.
