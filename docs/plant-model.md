# Plant model: equations, options and open questions

Status: **draft for discussion.** Implemented: motor speed placeholder (§2.1 A)
and the pelletizer geometry (§3.5, exact). Everything else is an interface that
holds its value constant. Every number in `config/line.yaml` is a placeholder until
it is justified here.

Notation: n = motor speed [rpm], N = driven-shaft speed (rotor or screw) [rpm],
i = gear ratio (motor/shaft), M = hopper mass [kg], ṁ = mass flow [kg/s or kg/h],
T = temperature [°C].

## 0. Design principles

1. **Physics first, sensors second.** Plant models compute *true* state. A separate
   measurement layer (`sim/components/sensors.py`) turns it into instrument
   readings. Process faults act on physics and sensor faults on measurements, and
   ground truth records which. This is what makes it possible to score the
   analyzer later.
2. **Every effect has a mechanism.** "The shredder motor heats up during a jam"
   must follow from torque → current → copper loss → heat, not a scripted ramp.
   Unscripted combinations then still behave plausibly. That is the basis of
   "surprise" testing.
3. **Fidelity only where a decision depends on it.** For each detail, ask which
   rule, controller or estimator depends on it. If none does, keep it simple.
4. **Deterministic given a seed.** One seed, child generators per device (wired in
   `sim/line.py`).
5. **No control logic in the plant.** PIDs, interlocks and auto-reverse live in
   `plc/`. The plant has actuators and sensors only.

## 1. Mass path and losses

```
refill ─► M_s (shredder hopper, weighed) ─► rotor ─► M_e (extruder hopper) ─► screw/barrel ─► strands ─► bath ─► cutter ─► pellets
```

Two buffers carry mass between stages: the shredder hopper (weighed) and the extruder
hopper (switches only). The barrel holds a roughly constant melt inventory at steady state.
Strands in transit are a small inventory.

**Mass is not conserved from input to pellets**, and the model should say where
it goes (D-25):
- moisture from washed feedstock evaporates in the barrel (vented extruders remove
  it deliberately);
- volatiles and degradation products leave through the vent;
- fines and dust from shredding;
- melt filter (screen) rejects;
- start-up and strand-break scrap.

This matters because throughput is measured at the shredder hopper (D-03). Pellet
output = shredder feed − losses − accumulation. A constant loss fraction can be
calibrated away; a variable one (for example moisture varying by batch) cannot
be seen with our sensors.

## 2. Shared components

### 2.1 Motor and drive (shredder, extruder, pelletizer) (D-15)

**A. First-order lag + ramp limit (implemented placeholder).**
`dn/dt = clamp((n_sp − n)/τ, −a_max, +a_max)`. Load has no effect, so a jam cannot
slow the motor and current cannot be computed.

**B. Speed loop + torque limit + mechanics (recommended).**

    T_m  = clamp(Kp·e + Ki·∫e, −T_max, +T_max),   e = n_ramp − n
    J_eff·dω/dt = T_m − T_load/(i·η_gear) − B·ω,   J_eff = J_motor + J_load/i²
    I ≈ sqrt(I_mag² + (T_m/k_t)²)

`T_max` is the drive's current limit. Below it, speed tracks the setpoint. Above it
(jam), speed collapses while torque and current sit at the limit. That gives the
setpoint-tracking rule a physical cause, and current and heating follow from load.
The speed loop is **inside the drive**: it is configured, not programmed (control.md §2).

### 2.2 Motor thermal (shredder, extruder) (D-23)

    C_th·dT/dt = 3·I²·R(T) + P_fe(n) − (T − T_amb)/R_th(n)
    R(T) = R_20·(1 + 0.00393·(T − 20))           copper resistance rises with T
    R_th(n) = R_0/(k_0 + k_1·n/n_rated)            shaft fan cools less at low speed

The shredder runs at **high torque and low speed**, which is the classic way a
self-cooled motor on a VFD overheats. Time constants are tens of minutes for
motors of this size, so overheating tests need `time_scale > 1` or deliberately
shortened τ (D-06). Open: is the sensor in the winding (fast, near the hot spot)
or on the frame (slow, cooler)? Alarm thresholds depend on it.

### 2.3 Vibration (shredder, extruder) (D-24)

Speed-proportional tones (1× motor, 2×, gear mesh, bearing defect orders) plus noise.
For bearings, an impulse train exciting a structural resonance is more realistic than
a pure tone, and it makes envelope analysis necessary (analyzer.md §3).

**The shredder is a special case:** cutting is impulsive and random by nature
(each knife hitting a chunk). Its healthy vibration is non-stationary and heavy-tailed.
A baseline-plus-z-score detector tuned on the extruder would alarm on the shredder
constantly. The shredder model needs a stochastic cutting-impact component whose
rate and intensity scale with throughput and material toughness.

### 2.4 Sensors (D-22)

| Sensor | Imperfections to model |
|---|---|
| Speed (VFD estimate) | quantization, small noise |
| Current | drive-internal filtering, noise |
| Motor/barrel/bath temperature | sensor lag, noise, open-circuit failure (thermocouple reads full scale or a fixed fault value) |
| Level switch | crossing offset (material heaps, flakes bridge), hysteresis, debounce delay |
| Load cell (shredder hopper) | noise, **vibration of the shredder coupled into the scale** (large: a shredder is a violent machine on the same frame), zero drift, invalid while a batch pours in (D-21) |
| Accelerometer | noise floor, band limit |

The load-cell coupling deserves attention. A shredder's vibration and impact
forces show up directly in a scale mounted on its own hopper. Real installations
mechanically isolate the weighed hopper and filter heavily. Our simulation must
include this coupling, or the flow measurement will look far better than it
would in reality.

## 3. Devices

### 3.1 Hoppers, switches, load cell, refill (D-02, D-21)

Mass balance: `dM/dt = ṁ_in − ṁ_out`, with `0 ≤ M ≤ capacity` and overflow counted as spill.

Switch thresholds are defined in kg (point switches only need thresholds, not
geometry). Recycled **flakes bridge** much more readily than pellets: material
hangs over the outlet, the screw starves, and the switch still reads "covered".
This is a process fault the extruder hopper model should support.

Refill (decided): when the shredder hopper's LOW switch uncovers, a batch of
`batch_kg` arrives after `response_delay_s` and pours at `pour_rate_kg_h`. Open:
fixed delay (automatic loader) or random (a person with a forklift or bale)? And what
happens if the batch overflows the hopper?

### 3.2 Shredder (D-16)

Recycling lines commonly use a **single-shaft shredder with a hydraulic ram**
(pushes material against the rotor, with a screen below that sets the output size) or a
**twin-shaft shredder** (slow, high torque, no screen). Which one we model
changes the torque profile and the jam behavior. Proposal: single-shaft with screen.

Throughput:

    ṁ_s = min( ṁ_available(M_s, ram),  C_rated · (N/N_rated) · η_knife )

Material stays in the cutting chamber until it is small enough to pass the
screen, so output lags input and the chamber is a small extra buffer.

Cutting torque is the defining feature: `T = T_0 + k·ṁ_s·(1 + σ·ξ(t)) + impacts`,
where ξ is random and impacts are sporadic large spikes (thick chunks). A **jam**
occurs when torque exceeds what the drive can deliver: the rotor stalls, and the
PLC's auto-reverse routine (D-27) reverses briefly and retries. Knife wear
lowers η_knife (less throughput) and raises torque per kg.

### 3.3 Extruder (D-17, D-18)

**Output.** For a flood-fed single screw (classic shallow-channel, Newtonian result):

    Q_drag     = ½ · π² · D² · N · H · sinφ · cosφ             (N in rev/s)
    Q_pressure = π · D · H³ · sin²φ · ΔP / (12 · μ · L)
    Q_die      = k_die · ΔP / μ
    ⇒ operating point:  Q = Q_drag · k_die / (k_die + k_screw),   k_screw = π D H³ sin²φ / (12 L)

D is the screw diameter, H the channel depth, φ the helix angle, L the metering
length, μ the viscosity, ΔP the die pressure. The useful conclusions:

- Output is **proportional to screw speed**, and for a Newtonian melt the
  viscosity cancels. So `ṁ_e ≈ K_ext · N` is a sound first model.
- A **clogging melt filter** lowers k_die. Output per rpm drops and pressure
  rises. We have **no melt pressure sensor**, so this fault is only visible as
  output drift (via the load cell, slowly) and as rising motor current (D-08).
- When the extruder hopper empties or bridges, the screw becomes **starve-fed**:
  output falls below K_ext·N and surges. That is a quality problem.
- Recycled feed with low bulk density (flakes, film) can limit intake well below
  the drag-flow capacity. Real lines use crammer or force feeders for this.
  Placeholder: a feed-limited cap on output.

**Barrel heat balance (single zone, as specified).**

    C_b · dT_b/dt = P_heater·duty + P_shear→barrel − P_to_melt − h_a·(T_b − T_amb)
    P_to_melt ≈ ṁ_e · (c_p·(T_melt − T_in) + ΔH_fusion)

Energy for melting comes from **two** sources: the heaters, and viscous shear
from the screw (the motor). At higher screw speed, shear supplies more of it and
the barrel PID backs the heaters off. At high enough speed the heaters reach 0 %
and temperature rises with nothing to pull it down, because we have no barrel
cooling. **This is the main coupling in the line**: extruder speed and barrel
temperature are not independent loops (control.md §7).

Real extruders have 3–6 barrel zones, each with a heater, a thermocouple and often
a cooling blower. You specified one zone with one heater and one sensor. That is fine
for the model, with two caveats: the dynamics are slower and lumped, and there is
no cooling (D-18).

Heater actuation: a solid-state relay switched on and off within a fixed cycle
(time-proportioning, typically a few seconds); PID output = duty. The thermocouple
sits in the barrel wall, so there is significant lag between heater and sensor.
This is why barrel loops are tuned slowly.

### 3.4 Water bath (D-20, deferred as requested)

    C_w · dT_w/dt = ṁ·(c_p·(T_melt − T_out) + ΔH) − ṁ_water·c_w·(T_w − T_supply) − UA·(T_w − T_amb)

Effects to model later: a warm bath leaves strands soft, so the cutter smears them
(tails, stuck pellets); a cold bath can make some polymers brittle (fines). For now
it is a pass-through with a sensor.

### 3.5 Pelletizer: exact geometry and strand dynamics (D-10, D-19)

One motor (speed n) drives the feed rolls (strand speed `v = a·n`) and the rotor
(`n_r = b·n`) with `z` knives. With `s` strands:

    pellet length   L   = v / (z · n_r) = a / (z · b)               fixed by gearing
    pellet mass     m_p = ṁ / (s · z · n_r)                          follows mass flow
    strand diameter d   = sqrt( 4ṁ / (π · s · ρ · v) )

These follow from geometry and are **implemented and tested**. With the
placeholder config (a = 0.075 m/min per rpm, z = 24, b = 1), L ≈ 3.1 mm; at
250 kg/h and 1000 rpm, d ≈ 3.0 mm.

Consequence: with fixed gearing, **only pellet mass varies**, through strand
diameter, and it varies in proportion to ṁ/n. Equal pellets therefore require
`n ∝ ṁ`. That is the "match cutting timing to mass flow" requirement, and it is a
ratio control law (control.md §5).

Strand dynamics (not implemented):
- pulling faster than the extruder pushes → strands thin, then **break**;
- pulling slower → strands sag and bunch in the bath, and can be pulled under or
  tangle.

So the pelletizer speed must track throughput for strand stability, not only for
pellet size. A strand break is a common event; the cutter keeps running with one
fewer strand.

Open (D-10): one motor with fixed ratios (assumed), or separate feed-roll and
rotor drives (allows changing pellet length too)? Which sensors does the
pelletizer have (current? a strand-break detector)?

## 4. Material model (D-25)

Recycled feed varies by bale and lot: polymer type and grade (viscosity), moisture,
contamination, and bulk density (flakes far below pellets). Proposal: a "lot"
object with slowly drifting properties and step changes at refills. Each
batch can differ, which is realistic and is a disturbance the controller must
reject.

## 5. Open questions (priority order)

1. Confirm the assumptions: bath before cutter; cutter has its own PLC; vibration
   sensors on shredder and extruder (D-09, D-10).
2. Shredder type: single-shaft with ram and screen, or twin-shaft (D-16)?
3. Refill delay: fixed or random (D-02)?
4. Add a melt pressure sensor at the die (D-08)? It is standard on extruders, and
   it makes screen clogging, and over-pressure (a safety issue), observable.
5. Motor model B (D-15): current and heating depend on it.
