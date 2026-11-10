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

Options:

| Option | What it gives | Realism |
|---|---|---|
| (a) Accept volumetric accuracy | Flow accurate to calibration (~few %) | Common for cheap feeders |
| (b) Periodic catch-weight calibration | Operator runs N revolutions into a bucket, weighs it, updates K | Standard practice for volumetric feeders |
| (c) Load cell under feeder_2 (loss-in-weight / gravimetric) | Continuous mass and flow measurement; closed-loop flow control | What precision plastics dosing actually uses |

This is the most important project decision. It changes the controller from "an
open-loop map with buffer management" (a, b) to genuine closed-loop flow control (c).
**Recommendation:** start with (a) because it is the brief, build the model so
that (c) is one extra measurement equation, and decide after we see the
behavior.

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

## 6. Is MPC justified here? (D-31)

Honest assessment: because of the triangular structure, **feed-forward
`ω_i = ṁ*/K_i` + a PI controller on estimated M₂ that trims ω₁** will do most of
the job. MPC is the better tool when:

- a constraint becomes active, e.g. feeder_1 at max speed: MPC can lower the line
  rate in a coordinated way, while the PI loop winds up;
- the target changes. MPC moves both feeders together, so the buffer is not
  disturbed;
- the problem grows: more feeders, a blend ratio, or temperature limits as
  constraints.

**Recommendation:** implement the feed-forward + PI baseline first, behind the
same `Controller` interface. Then the MPC has a benchmark, and we can measure
what MPC adds instead of assuming it.

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
