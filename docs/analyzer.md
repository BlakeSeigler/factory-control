# Analyzer: real-time rules

## 0. Framework (implemented)

- One instance of each rule **per machine**. Each instance owns its state.
- Rules receive only the tags they declare in `inputs`. Sim ground truth is never
  an input.
- Rules run on **sample time** (OPC UA SourceTimestamp), not wall time (D-19).
  The same code then behaves identically live, accelerated (`time_scale > 1`) and
  when replaying the historian offline. Replay is also how we will test rules
  against recorded fault scenarios.
- `on_tick(now)` handles timeout-style conditions. `now` is the newest sample
  time seen for that machine.
- Output is `AlarmEvent` transitions (`raised` / `cleared`), stored in
  `alarm_event`.

**Gap (D-19):** if a machine stops sending samples, its sample time freezes, and
timeout rules stop advancing with it. Stale-data detection must therefore use
connection state or wall time. It is a separate "communication lost" condition and
should not be inferred from missing samples inside the rules.

## 1. Rule 1: setpoint changed but speed is not following (D-20)

Trigger: a `SpeedSetpoint` change of at least `min_step_rpm`. Clear: |sp − pv| ≤
deadband. A new setpoint while the rule is armed re-arms it.

**Option A: fixed timeout (as in config).** Simple, but it is wrong for large
steps. With the drive's ramp limit `a` and time constant `τ`, the drive cannot
reach the deadband faster than:

    t_ramp     = max(0, |Δ| − a·τ) / a        (on the acceleration limit)
    t_settle   = τ · ln( min(|Δ|, a·τ) / δ )  (exponential tail into deadband δ)
    T_expected = t_ramp + t_settle

With the placeholder drive (a = 600 rpm/s, τ = 0.8 s, δ = 20 rpm), a 0 → 1800 rpm
step needs 2.2 s + 2.5 s ≈ 4.7 s. The original 5 s timeout left 0.3 s of margin,
which is less than a few 100 ms publish periods, so it would have raised false
alarms on healthy full-range steps. **The timeout is now 15 s** (about 3× the
worst healthy case). That removes the false alarms, but a small step (e.g. 100 rpm,
T_expected ≈ 1.3 s) now gets more than 10× its expected time before anyone is told. Any
fixed timeout trades false alarms on large steps against slow detection on small
ones. Options B and C remove that trade-off.

**Option B: timeout scaled from the drive's configured dynamics (recommended
first).** `T_allow = k · T_expected(|Δ|) + margin`. It needs only the drive's ramp
setting and an estimate of τ, which are configuration data for a real drive.

**Option C: model residual.** Run the drive model inside the analyzer, predict
ω(t) from the setpoint history, and alarm when |ω_meas − ω_pred| exceeds a
threshold for a minimum duration. This catches *sluggish* response (partial jam,
drive in current limit), not just *absent* response. It requires a reasonably
accurate drive model, which we will have from the simulator, but on a real
machine the model would need identifying from data.

Message wording: "speed not following setpoint". Do not call it a "drive fault",
because a stuck speed sensor produces the same signature (fault-injection.md §3).

## 2. Rule 2: motor too hot (D-23)

**Baseline:** two levels, each with hysteresis, plus an on-delay:

    RAISE warning when T ≥ warn_c   for t_on;   CLEAR when T < warn_c − h
    RAISE alarm   when T ≥ alarm_c  for t_on;   CLEAR when T < alarm_c − h

Hysteresis stops chatter around the limit. The on-delay rejects single-sample
spikes, such as a sensor glitch.

**Extensions to discuss:**

- **Rate of rise.** `dT/dt` estimated over a window (a derivative of a noisy signal
  needs filtering). A winding short or blocked fan shows an abnormal slope long
  before the absolute limit is reached. It also gives a physical plausibility
  check: a slope larger than `P_max / C_th` is physically impossible, so a sensor
  fault can be told apart from a real temperature rise.
- **Expected temperature for current load.** Using the thermal model with measured
  speed (and current, if added), predict T and alarm on the residual. This is the
  most sensitive option, and the most model-dependent.

Thresholds depend on what the sensor measures (winding or frame, plant-model.md §5).

## 3. Rule 3: anomalous vibration (D-21, D-22)

Pipeline per block (`amplitude_spectrum` in `analyzer/vibration.py` is implemented and tested):

1. **Gate.** Skip blocks during speed transients, i.e. when |Δω| within the block
   is more than a few percent. A spectrum of a changing speed is smeared and
   compares badly with a steady-state baseline.
2. **Spectrum.** Remove the mean, apply a Hann window and take the rFFT. Welch
   averaging over several blocks reduces variance at the cost of latency.
3. **Order normalization.** Divide frequency by shaft frequency f_m. Kinematic
   features then sit at fixed orders (1×, 2×, mesh, BPFO, ...) regardless of speed.
4. **Features.** Energy in narrow order bands around each kinematic order, plus
   overall RMS. Optionally overall **velocity** RMS in 10–1000 Hz (integrate in
   the frequency domain by dividing by 2πf), which is the quantity ISO 20816 uses
   for absolute severity zones.
5. **Baseline.** Mean and standard deviation per feature from `baseline_blocks`
   healthy blocks, **binned by speed range**. Amplitudes are speed-dependent, so a
   baseline learned at 1750 rpm is wrong at 600 rpm.
6. **Score.** Max per-feature z-score (interpretable: "2× order is 6σ above
   baseline", which points to misalignment), or Mahalanobis distance over all
   features (more sensitive, harder to explain).
7. **Decide.** Raise after k consecutive blocks above the threshold; clear after
   m consecutive blocks below it.

**Questions to decide together:**

- **Who certifies "healthy"?** A baseline learned while a fault is present
  treats the fault as normal. Options: learn at commissioning on operator
  command; learn continuously with slow adaptation (which tolerates slow fault
  growth: bad); or keep a fixed reference.
- **Plain FFT or envelope analysis for bearings?** If the simulator models
  bearings realistically (plant-model.md §6 B), plain FFT bands will miss early
  bearing faults. Envelope analysis needs a higher sample rate.
- **Absolute limits as a backstop.** ISO 20816 velocity-RMS zones flag a machine
  that was already rough when the baseline was learned. The baseline method
  cannot catch that case.
- **Learned models** (isolation forest, autoencoder on spectra). Possible later,
  but the interpretable band features should come first, so that we can see
  what the learned model adds.

## 4. Rule 4: motor current too high or rising abnormally (D-04, D-25)

Tag: `Motor/Current` (A, RMS drive output current, as every VFD reports it).
In the simulator it stays 0 until the torque model exists (plant-model.md §2 B).
**The rule is disabled until its limits are configured**: all four values in
`supervisor.analyzer.overcurrent` are `null`.

Why current is worth more than its one rule: current ≈ torque, and torque is
the mechanical load on the screw. It makes faults visible that the other tags
miss (fault-injection.md §3):

| Fault | Current signature |
|---|---|
| Jam / foreign object | sharp rise at constant speed, up to the drive's current limit |
| Bridging / starving | **drop** at constant speed (screw runs empty) |
| Bearing degradation | slow upward drift (friction) |
| Speed sensor stuck | current keeps changing while "speed" is frozen |

Two conditions, to decide together:

- **Absolute limit.** `I ≥ limit_a` for `on_delay_s`. The natural reference is
  the motor nameplate full-load current (FLA). Continuous operation above FLA
  overheats the motor. The drive itself trips at its own overload limit, so
  our limit should be lower, to warn before the drive trips.
- **Relative rise ("a crazy increase").** `I ≥ rise_ratio × baseline`, where the
  baseline is the median current over the last `baseline_window_s` of **steady**
  operation. This catches a jam on a lightly loaded feeder long before the
  absolute limit.

Required gating: accelerating the screw takes extra torque, so every speed step
produces a healthy current surge. The baseline and the relative test must ignore
the period right after a setpoint change, otherwise every setpoint change raises
a false alarm. A **low**-current condition (`I < fall_ratio × baseline`, for
starving) is the natural companion rule. I left it out until we agree on it.

## 5. Alarm lifecycle (D-24)

Current: raise/clear transitions only. Industrial practice (ISA-18.2 / IEC 62682)
adds **acknowledgement** (active-unacked, active-acked, cleared-unacked),
**shelving** (temporarily suppress a known nuisance alarm), and alarm-flood
metrics. We should at least add ack before the dashboard shows alarms. An alarm
nobody has to acknowledge is easy to miss.
