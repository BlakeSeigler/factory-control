# Line control: from a target mass flow to RPM setpoints

## 1. What MPC is

Model Predictive Control repeats the following steps every control period `Ts`
(e.g. 1 s):

1. **Estimate** the current state x̂ₖ of the plant from measurements.
2. **Predict.** Using a model `x[j+1] = f(x[j], u[j])`, express the plant's future
   over a horizon of N steps as a function of a candidate input sequence
   `u[0..N−1]`.
3. **Optimize.** Choose the input sequence that minimizes a cost (tracking error +
   control effort) subject to constraints (actuator limits, rate limits, safe
   state ranges).
4. **Apply only u[0].** Discard the rest. At the next period, re-measure and
   re-solve from the new state. This is the *receding horizon*.

Feedback enters only through step 1. The optimizer is open-loop over the horizon,
but re-solving from fresh measurements every period closes the loop. A poor
estimator therefore makes MPC poor, however good the optimizer is.

Compared with PID: a PID loop reacts to the *current* error of *one* variable. It
cannot handle constraints except by clipping afterwards (which causes windup), and
it does not know about coupling between loops. MPC handles multiple inputs and
outputs with explicit coupling, enforces constraints inside the decision, and can
act on predicted future problems, e.g. "the buffer will overflow in 40 s if I
keep this up". The cost is a model, an estimator, a solver and tuning.

## 2. What we can and cannot measure (D-03). Read this first.

Available tags: speeds, setpoints, temperatures, binary level switches,
vibration. **No tag measures mass flow.** Line flow is
`ṁ_line = K₂ · ω₂ · η_fill,2`, and `K₂ = ρ_b·V_d/(60·i)` depends on bulk
density, which varies by a few percent.

Consequences:

- **Absolute line-flow accuracy is fundamentally open-loop.** It equals our
  knowledge of K₂. No controller, MPC included, can correct an error in K₂ with
  these sensors, because nothing observes it.
- The level switches on feeder_2 do carry information, but only about the
  **difference** between the two feeders (K₁ω₁ − K₂ω₂), and only at the rare
  instants when a switch changes (hours apart in steady state, plant-model.md §4).

### Do industrial lines measure mass flow?

It depends on what an error costs. Resin is usually the largest cost in plastics
processing, so wherever throughput or dosing ratio decides product quality or
material giveaway (film/pipe/profile wall thickness, masterbatch and additive
ratios, compounding), gravimetric measurement is standard. Simple
conveying/buffering stages, and cheap products with loose tolerances, run
volumetric.

**Where the measurement sits:** at the **last** device before the process (the
dosing point, usually the extruder throat), because accuracy there is the
accuracy of the product. Intermediate transfer stages (loaders, our feeder_1) are
almost never weighed. Their only job is to keep the dosing device supplied, and
level switches are enough for that. One measurement per material stream at the
dosing point, not one per machine.

Ways to measure, all at feeder_2 / the process inlet:

| Method | How it works | Typical accuracy | Notes for our line |
|---|---|---|---|
| Loss-in-weight (LIW) feeder | Hopper + screw on load cells; flow = −dM/dt; controller trims screw speed | best of these, well under 1 % short-term (vendor claims vary) | **Conflicts with continuous refill**: while feeder_1 is filling the weighed hopper, dM/dt = in − out, so out cannot be measured. LIW feeders refill in batches and hold speed volumetrically during refill. feeder_1 would become an on/off refill device |
| Throughput weigh hopper ("gravimetric extrusion control") | Weighed hopper above the throat; measures consumption, adjusts extruder or feeder speed | ~1 % | Same refill conflict; same batch refill pattern |
| Solids flow meter at discharge | Pellet stream hits an impact/curved plate or passes a Coriolis wheel; force → flow | impact ~1–2 %, Coriolis ~0.5 % | Measures **outflow directly**, so it is unaffected by how the hopper is refilled; keeps feeder_1 continuous. Needs free-fall/chute geometry and a minimum flow rate |
| Catch-weight calibration (manual) | Run N revolutions into a bucket, weigh, update K | as good as the last calibration | No hardware; drifts between calibrations |

**Cost.** I searched and found no published prices; vendors quote per
application. My order-of-magnitude estimates (not verified, get quotes before
relying on them): a bare load cell is hundreds of USD, but a complete LIW feeder
or gravimetric throughput system (weigh frame, isolation, controller, software)
is in the **low-to-mid five figures USD per stream**, and a solids flow meter is
similar. A volumetric screw feeder costs a fraction of that. The business case
is resin savings: running closer to minimum wall thickness instead of
over-dosing to stay safe.

**Recommendation:** keep the brief (volumetric, no flow sensor) as the baseline.
Add one optional measurement on feeder_2 behind a config switch:
a solids flow meter at the discharge (simplest, because it does not change feeder_1's
role), or LIW (more realistic for plastics, but it turns feeder_1 into a batch
refill device). Comparing "with" and "without" in simulation is the most
convincing way to see what the sensor is worth.

## 3. Prediction model (D-32, D-35)

States `x = [ω₁, ω₂, M₁, M₂]`, inputs `u = [ω_sp,1, ω_sp,2]`, discrete with
period Ts:

    ω_i[k+1] = a_i·ω_i[k] + (1 − a_i)·u_i[k],           a_i = exp(−Ts/τ_i)
    M₁[k+1]  = M₁[k] + Ts·(ṁ_supply − K₁·ω₁[k])
    M₂[k+1]  = M₂[k] + Ts·(K₁·ω₁[k] − K₂·ω₂[k])
    ṁ_line   = K₂·ω₂

This is linear, `x[k+1] = A·x[k] + B·u[k]`, so the optimization is a convex
quadratic program (QP), which can be solved reliably in milliseconds.

Simplifications to consider:

- **Treat the motors as static (D-35).** With τ = 0.8 s and Ts = 1 s,
  a = e^(−1.25) ≈ 0.29. The motor settles within about one control period. If we
  drop ω from the state (ω = u), the model is two hopper integrators and is easier
  to reason about. The cost is that the motor's ramp limit can no longer be
  represented, so it would have to be added as a rate constraint on u.
- **Nonlinearities ignored:** starve feeding (η_fill drops as M → 0) and hopper
  saturation. If the controller keeps hoppers in their normal band, the linear
  model is valid there. A nonlinear MPC is unnecessary unless we deliberately
  operate near empty.

Structure worth noticing: ω₂ alone sets line flow, and ω₁ − ω₂ alone sets
the buffer M₂. The system is nearly **triangular**: feeder_2 serves the process,
and feeder_1 serves feeder_2's hopper.

Steady state for target ṁ*: `ω₂* = ṁ*/K₂` and `ω₁* = ṁ*/K₁`. With placeholder
K ≈ 0.41 (kg/h)/rpm, 300 kg/h → about 727 rpm on both. Feasibility limits:
`ṁ* ≤ K·ω_max ≈ 742 kg/h`, and **sustained** `ṁ* ≤ ṁ_supply` (400 kg/h loader in
config). Above the supply rate, feeder_1's hopper drains no matter what the
controller does. The MPC should report a target above the supply rate as
infeasible, rather than track it until the line starves.

## 4. State estimation with binary switches (D-33)

The MPC needs M₁ and M₂, and no sensor measures them. Approach:

- **Predict** with the model mass balance every step (dead reckoning). It drifts at
  the calibration-error rate.
- **Correct at switch transitions.** A transition is an exact-level event ("M₂
  crossed 5 kg at t"), with uncertainty from switch hysteresis and heaping.
- **Constrain between transitions.** "Low covered, high uncovered" means
  `5 ≤ M₂ ≤ 25`, so the estimate is projected into that interval.
- **Estimate the bias.** Add the flow mismatch `d = K₁ω₁ − K₂ω₂ − (model)` as a
  slowly varying extra state. Each transition says something about `d`. This is
  the standard *offset-free MPC* construction: augment the model with a
  disturbance state, estimate it, and the controller removes steady-state bias
  automatically.

A Kalman filter with event-based updates does this, and its covariance shows
honestly how uncertain M₂ is between events. A moving-horizon estimator (MHE)
handles the inequality information natively but is more machinery. Recommendation:
KF + projection first.

## 5. Optimization problem

Over horizon N (e.g. 60 steps of 1 s):

    minimize   Σₖ  q_f·(ṁ_line[k] − ṁ*)²  +  q_m·(M₂[k] − M₂_ref)²  +  Δuᵀ·R·Δu
    subject to x[k+1] = A·x[k] + B·u[k],      x[0] = x̂
               ω_min ≤ u[k] ≤ ω_max
               |u[k] − u[k−1]| ≤ Δu_max
               M_low − s ≤ M₂[k] ≤ M_high + s,  s ≥ 0, penalized by ρ·s   (soft)

What each term does:

- `q_f` is the line-flow tracking weight. It is the main objective.
- `q_m` keeps the buffer near the middle of the switch band, which leaves room
  both ways for disturbances.
- `R` penalizes setpoint moves. It provides smoothness, and its ratio to the other
  weights sets how aggressive the controller is.
- **Soft** state constraints use slack variable `s`. Hard state constraints can
  make the QP *infeasible* after a disturbance (no input sequence can satisfy
  them), and an infeasible controller outputs nothing. Slack converts "impossible"
  into "expensive".
- Horizon N·Ts must cover the slowest dynamics that matter here, which is the buffer
  response (minutes). The motor dynamics need only a few steps.

Tuning is choosing the weight ratios, N and Ts. We will do it in simulation by
comparing step responses and disturbance rejection.

## 6. Controllers without MPC, and when MPC is worth it (D-31)

### 6.1 The non-MPC controller, in three tiers

**Tier 0: switch logic (what a PLC programmer would write).**

    ω₂ = ṁ*/K₂                                   (line flow, open loop)
    ω₁ = ṁ*/K₁ · (1 + b)   once feeder_2's LOW switch uncovers
    ω₁ = ṁ*/K₁ · (1 − b)   once feeder_2's HIGH switch covers
    (hold the last choice in between; b ≈ 5–10 %)

No model, no estimator. The buffer saws between the switches, and line flow is
exactly as accurate as K₂. Robust and easy to commission. With binary level
sensors this is a fully legitimate design.

**Tier 1: feed-forward + PI on estimated buffer mass.**

    ω₂ = ṁ*/K̂₂
    ω₁ = ṁ*/K̂₁ + Kp·e + Ki·∫e dt,      e = M₂_ref − M̂₂   (M̂₂ from the §4 estimator)

Why it works: M₂ is a pure integrator, `dM₂/dt = K₁ω₁ − K₂ω₂`. Substituting the
P term gives `dM₂/dt = K₁Kp·(M₂_ref − M₂) + d`, where d is the flow mismatch.
That is a first-order system with time constant `1/(K₁Kp)`. P alone leaves a
steady offset `d/(K₁Kp)`; the integral term removes it. Example: K₁ ≈ 0.41
(kg/h)/rpm and a 15-minute closed-loop time constant (`K₁Kp = 4 /h`) give
`Kp ≈ 9.7 rpm per kg`. Add anti-windup (stop integrating while ω₁ is at a limit)
and clamp to the rpm and rate limits.

Feed-forward does most of the work: when the target changes, both feeders move
at once, so the buffer barely notices. The PI only corrects the slow mismatch.
Caveat: with switches only, M̂₂ is mostly a model prediction, so the PI acts on
an estimate that improves only at switch events. MPC has exactly the same
limitation, because no controller has information the sensors do not provide.

**Tier 2: MPC** (§5).

### 6.2 What MPC adds, and when it is worth the cost

Both controllers are feedback loops. The difference is how they choose a move:

- **PID** applies a fixed rule (gain × error) to *one* variable. It has no idea
  what is coming, what the limits are, or what its move does to other loops.
  Limits are applied afterwards by clipping.
- **MPC** solves "which future sequence of moves for *all* actuators gives the
  best predicted outcome *within* the limits", every period. Limits, coupling and
  priorities are part of the decision, not patched on afterwards.

That difference only shows up in specific situations. Use MPC when one or more of
these is true:

1. **Constraints are active in normal operation.** Plants often run at a limit
   on purpose, because that is where the money is: max throughput, minimum wall
   thickness. PID plus clipping is good away from limits and poor at them.
2. **Real multivariable coupling.** Several actuators affect several outputs
   in overlapping ways, so tuning loops independently makes them fight. If the
   coupling is triangular, as in our line, cascaded PID handles it.
3. **Explicit trade-offs.** "If both cannot be met, protect the buffer and give up
   2 % of line rate" is a weight in an MPC cost function. In PID it becomes
   override logic and selectors, which get fragile as the logic grows.
4. **Known future changes (preview).** A scheduled rate change or a known upcoming
   disturbance can be acted on before it happens. PID only reacts to error that
   already exists.
5. **Long dead time** relative to the dynamics. MPC's model handles it naturally;
   PID needs a Smith predictor or must be detuned.

How industry uses this: the large majority of loops are PID. MPC is used as a
**supervisory layer that writes setpoints to PID loops**, in refineries,
chemicals and polymer reactors, where conditions 1–3 are true and a fraction of a
percent of throughput is worth a lot. That is our architecture: each VFD
has its own inner speed loop, and the supervisor writes speed setpoints.

### 6.3 Applied to this line

As briefed, the line meets almost none of the criteria. The coupling is
triangular (2 is false), and the rpm limits are not active at normal rates
(1 is false). A target change is handled by feed-forward (so 4 adds little). The
places where MPC clearly beats Tier 1:

- **A target above what the supply can sustain** (e.g. 450 kg/h with a 400 kg/h
  loader). Tier 1 runs feeder_2 at 450 while feeder_1 empties its own hopper,
  and the line collapses minutes later. MPC with the supply constraint in its
  model either holds the highest sustainable rate, or runs 450 for exactly as
  long as the buffers allow and then ramps down in a planned way.
- **Unequal feeders**, e.g. feeder_1 smaller and close to its max rpm. MPC lowers
  the line rate in advance; PI winds up and then overshoots.
- **Extensions**: a blend with ratio constraints, motor temperature as a
  constraint ("never exceed 120 °C, even if that costs rate"), more feeders.

**Recommendation (unchanged, now justified):** build Tier 0 and Tier 1 behind the
same `Controller` interface, then MPC, and run all three through the same scenarios
(target steps, supply above and below demand, calibration error, jams). The MPC
work is fully worthwhile as a learning goal. The comparison will show where it
earns its complexity, instead of us assuming it does.

## 7. Tooling (D-34)

Problem size: 4–5 states, 2 inputs, N ≈ 60. Every serious solver handles it in
milliseconds.

| Option | Pros | Cons |
|---|---|---|
| cvxpy + OSQP | Formulation reads like the math above; `Parameter`s let it compile once | Abstraction hides the QP matrices |
| OSQP directly (build H, A by hand) | You see and own every matrix, so the method is fully exposed | More code; easy to make indexing mistakes |
| CasADi (+ IPOPT / qpOASES) | Handles nonlinear MPC if we need it later | Heavier; more to learn up front |
| do-mpc | MPC framework on top of CasADi (estimator, simulator included) | Framework conventions to learn |

Recommendation for learning: cvxpy first, so that the math is readable. Then
optionally rebuild the condensed QP by hand once, to see what the solver
actually receives.

## 8. How the line target gets in (D-30)

Not decided: CLI command, a row in the database the supervisor polls, an HTTP
endpoint on the supervisor, or an OPC UA server *on the supervisor* (it would then
be both client and server, as an aggregating server is). The cleanest for now is a
small HTTP endpoint on the supervisor, because the dashboard is read-only by design.
