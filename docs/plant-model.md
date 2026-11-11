# Plant model: equations, options and open questions

Status: **draft for discussion.** Only §2 option A is implemented (as a
placeholder). Every parameter in `config/line.yaml` is a placeholder until it is
justified here.

Notation: ω = motor speed [rpm], n = screw speed [rpm], i = gear ratio (motor/screw),
M = hopper mass [kg], ṁ = mass flow [kg/s], T = temperature [°C].

## 0. Design principles for the simulator

1. **Physics first, sensors second.** The model computes *true* state. A separate
   measurement layer (`sim/sensors.py`) turns it into what instruments report. Faults
   act on one layer or the other, and we log which one. This is the only way to
   score the analyzer later: we need to know what *really* happened.
2. **Each effect needs a mechanism.** "Temperature goes up during a jam" must follow
   from torque → current → copper loss → heat, not from a scripted ramp. Then
   fault combinations and unexpected operating points produce plausible results we
   did not script. That matters for "surprise" testing.
3. **Fidelity only where a decision depends on it.** For each subsystem, ask which
   rule or controller behavior depends on this detail. If none does, keep it simple.
4. **Deterministic given a seed.** All randomness comes from one seed with
   per-machine child generators (already wired in `sim/line.py`), so any run,
   including a failing one, can be reproduced exactly.

## 1. Mechanical chain

```
VFD ──► motor (ω) ──► gearbox (i) ──► screw (n = ω / i) ──► pellets
```

Reflected quantities at the motor shaft:
`J_eff = J_motor + J_screw / i²`,  `T_load,motor = T_screw / (i · η_gear)`.

## 2. Motor and drive (D-10)

**A. First-order lag + ramp limit (implemented placeholder)**

    dω/dt = clamp((ω_sp − ω) / τ, −a_max, +a_max)

Good: matches what a speed-controlled VFD looks like from outside when it is
unloaded, and it is trivial. Bad: **load has no effect**. A jam cannot slow the
motor, and torque or current cannot be computed, so heating cannot follow from load.

**B. Speed loop + torque limit + mechanics (recommended)**

    T_m  = clamp( Kp·e + Ki·∫e ,  −T_max, +T_max ),   e = ω_ramp − ω
    J_eff · dω/dt = T_m − T_load,motor − B·ω
    ω_ramp follows ω_sp at the VFD's configured acceleration

`T_max` represents the drive's current limit. When load stays below it, speed
tracks the setpoint as in model A. When a jam pushes load above it, speed collapses
while torque, current and heat stay at the limit. That is the real jam signature,
and it makes Rule 1 ("speed not following setpoint") fire for a physical reason.

Current (needed for heating): `I ≈ sqrt(I_mag² + (T_m / k_t)²)`, with magnetizing
current `I_mag` and torque constant `k_t`.

**C. Full induction-machine model (d-q axes, slip).** Rejected: high
fidelity at timescales we never observe through a 10 Hz tag.

## 3. Screw conveyance (D-11)

Volumetric delivery:

    ṁ = ρ_b · V_d · (n / 60) · η_fill

- `V_d` [m³/rev]: swept volume per revolution (geometry).
- `ρ_b` [kg/m³]: bulk density of the material. For virgin polyolefin pellets it
  is about 500–650. This is a **recycling** line, and flake, regrind and
  re-pelletized material have lower and much more variable bulk density than
  virgin pellets. Model a wider band and occasional step changes (a new bale or
  lot). It varies with pellet shape, regrind fraction and moisture. **This
  variation is the main reason volumetric feeders are inaccurate.** Proposed
  model: a slow Ornstein–Uhlenbeck random walk of a few percent around nominal.
- `η_fill` ∈ [0, 1]: fill efficiency. About 1 with adequate head of material.
  It drops as the hopper approaches empty (starve feeding) and collapses under
  bridging (a fault).

With the placeholder config: `ρ_b·V_d = 550 × 250e-6 = 0.1375 kg/rev` of the screw.
At ω = 1750 rpm and i = 20, n = 87.5 rpm, giving ṁ ≈ 722 kg/h at full fill. The
line gain per motor rpm is `K = ρ_b·V_d/(60·i) ≈ 0.41 (kg/h)/rpm`.

Screw torque (feeds §2 B):

    T_screw = T_0 + k_c · ρ_b · η_fill · (n-dependent friction term) + T_jam

The exact form is open. Requirements are that it rises with fill, is non-zero
when empty (bearing and seal friction), and allows a fault-driven jam term.

Optional: **flow pulsation** at the screw-flight discharge frequency. It is small
for most applications, but it is a real feature of screw feeders.

## 4. Hopper and level switches (D-02, D-13)

Mass balance, with spill accounting:

    dM/dt = ṁ_in − ṁ_out,      0 ≤ M ≤ M_cap,  overflow → spilled_kg

Switches are **point-level** sensors (capacitive or vibrating fork). Things to
model:

- **Threshold in mass, not height.** A switch is at a height, and pellets heap at
  their angle of repose, so the mass at which the switch covers depends on hopper
  geometry and flow pattern. Proposal: define thresholds directly in kg and add a
  small random offset per crossing. Geometry would only matter if we wanted a
  continuous level, and we do not have a continuous level sensor.
- **Hysteresis and debounce.** Real switches have an adjustable switching delay
  (seconds) so that flowing pellets do not make them chatter. Without it, the
  supervisor sees bursts of transitions.
- **Fail-safe polarity.** Low-level switches are usually wired so that a broken
  wire reads "uncovered" and raises an alarm. Our tag convention is
  `True = material present`.

**Series coupling.** `ṁ_in` of feeder_2 is `ṁ_out` of feeder_1. In steady state
**the two flows must be exactly equal**, or feeder_2's hopper drifts to empty or to
overflow. With identical calibrations and a 2% real mismatch (e.g. bulk density
difference) at 300 kg/h, the drift is 6 kg/h. Feeder_2's 20 kg switch band then
gives one switch event roughly every 3.3 h. **Level switch transitions are rare
events. They are not a level measurement.** This drives the estimator design (mpc.md §4).

**What feeds feeder_1 (D-02, decided): batch refill.** When feeder_1's low switch
uncovers, a batch of `batch_kg` is requested. It starts pouring after
`response_delay_s` and pours in at `pour_rate_kg_h`. Open: is the delay fixed
(automatic loader) or random (a person with a forklift)? And what happens if a
batch would overflow the bin? That is a real spill risk.

**Load cell on feeder_1's bin (D-03, decided; model is D-26).** It reports net
material mass. Imperfections to model:
- resolution and electronic noise;
- **mechanical coupling**: the turning screw and the motor vibrate the weighed
  frame, which adds noise at their frequencies. Real loss-in-weight controllers
  filter heavily for this reason;
- slow zero drift (temperature);
- invalid flow readings while a batch pours in and until the scale settles.

Flow is derived as `ṁ₁ = −dM₁/dt`, which is a derivative of a noisy signal. The
filter that computes it (window length versus noise) is a design choice. It sets
how fast the controller learns about a flow change.

## 5. Motor thermal model (D-15)

Single-node lumped model:

    C_th · dT/dt = P_loss − (T − T_amb) / R_th(ω)

    P_loss = 3·I²·R_s(T) + P_fe(ω) + P_mech(ω)
    R_s(T) = R_20 · (1 + α_Cu · (T − 20)),   α_Cu ≈ 0.00393 /K
    R_th(ω) = R_0 / (k_0 + k_1 · ω/ω_rated)      (shaft-mounted fan, TEFC)

Points to discuss:

- **R_th grows at low speed.** A self-cooled motor on a VFD loses cooling at low
  speed. High torque at low speed is the classic way such motors overheat, and
  it is why VFD duty has derating curves. Our feeders often run slow, so this
  matters.
- **R_s(T) creates positive feedback.** Hotter windings have higher resistance and
  higher losses. This is physically correct, and a winding short can lead to
  thermal runaway.
- **Time constant.** For small motors, τ = R_th·C_th is typically tens of minutes.
  An overheat fault therefore develops over tens of minutes of real time. Options:
  run the simulator faster (`time_scale`, D-07), or shorten τ deliberately for
  testing and document that we did.
- **What does "motor temperature" measure?** A winding RTD/PTC (fast, τ in
  minutes, close to the insulation hot spot) or a frame thermocouple (slow,
  10–30 °C cooler)? A two-node model (winding + frame) supports either. Alarm
  thresholds depend on this choice. For reference, insulation class limits are
  130 °C for class B and 155 °C for class F, measured at the hot spot. The
  90/105 °C in config are placeholders with no justification yet.

## 6. Vibration signal (D-21, D-22)

Kinematic frequencies, all proportional to speed:

| Source | Frequency | At ω = 1750 rpm, i = 20 |
|---|---|---|
| Motor 1× (imbalance) | f_m = ω/60 | 29.2 Hz |
| Motor 2× (misalignment, looseness) | 2·f_m | 58.3 Hz |
| Screw 1× | f_m / i | 1.46 Hz |
| Gear mesh (single stage, z pinion teeth) | z·f_m | e.g. z = 17 → 496 Hz |
| Bearing outer race (BPFO) | (N_b/2)·f_r·(1 − (d/D)cos φ) | 6205 bearing: 3.585·f_m = 105 Hz |
| Bearing inner race (BPFI) | (N_b/2)·f_r·(1 + (d/D)cos φ) | 6205: 5.415·f_m = 158 Hz |
| VFD | carrier/switching sidebands | kHz range, usually outside band |

(6205 bearing: N_b = 9 balls, d/D ≈ 7.94/39.04, φ = 0.)

Signal options:

- **A. Sum of sinusoids + white noise.** Trivial, and correct for imbalance (1×)
  and misalignment (2×). For bearing faults it is **unrealistically easy to
  detect**: a clean tone at BPFO stands out in a plain FFT.
- **B. Physical bearing-fault model (recommended for bearings).** Each
  rolling-element impact excites a structural resonance (typically kHz). The
  signal is an impulse train at BPFO convolved with a decaying resonance, with
  slight randomness in impulse timing. A plain FFT shows a smeared hump at the
  resonance, not a peak at BPFO. The standard detection method is **envelope
  analysis** (band-pass around the resonance, Hilbert envelope, then FFT, where
  BPFO appears). This makes the analyzer problem realistic.
- **Process noise.** Pellets in the flights create broadband noise proportional to
  fill and flow, so a starved screw is measurably quieter. Starvation then has a
  vibration signature too.

Sampling: fs = 2560 Hz and N = 1024 give a 0.4 s block, 2.5 Hz resolution and
fmax = 1000 Hz. **The screw 1× (1.46 Hz) is below the resolution.** Screw-side
faults (bent flight, screw rubbing once per revolution) cannot be resolved with
0.4 s blocks. Longer blocks give better resolution, but blocks get smeared when
speed changes inside a block. This trade-off is D-21. Gear mesh at about 500 Hz
fits under 1000 Hz. A bearing resonance in the kHz range does **not**. If we
want envelope analysis, fs must rise (e.g. 10–20 kHz), with proportional cost in
bandwidth and storage.

Implementation note: blocks are generated analytically from the current speed, with
phase carried across blocks, so the physics can step at 100 Hz while the
accelerometer is sampled at kHz rates.

## 7. Sensor imperfection (D-14)

Proposed per-sensor models. All are optional and switched on one at a time so
that their effect on the analyzer can be seen in isolation.

| Sensor | Imperfections |
|---|---|
| Speed (VFD estimate/encoder) | quantization (e.g. 0.1 rpm), small white noise, VFD update rate |
| Temperature | first-order sensor lag, white noise, 0.1 °C quantization |
| Level switches | crossing offset, hysteresis, debounce delay |
| Accelerometer | noise floor, gain error, band-limit, optional mounting resonance |

Noise processes: white Gaussian for measurement noise. Ornstein–Uhlenbeck
(mean-reverting random walk) for slowly varying physical disturbances such as
bulk density and ambient temperature. A pure random walk is not used because it
drifts without bound.

## 8. Open questions for discussion

1. Series topology (D-01): is the second feeder a buffer stage in front of the
   process, or should it be a blend (two materials, fixed ratio)? This changes the
   control problem completely.
2. Motor current is now a tag (D-04). It only becomes informative once the motor
   model computes torque (option B above), so D-10 is now on the critical path.
3. Is mass flow measured, and where (D-03)? See mpc.md §2.
