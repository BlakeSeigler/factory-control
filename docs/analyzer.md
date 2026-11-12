# Analyzer: real-time rules

## 0. Framework (infrastructure in place; no rule logic yet)

- One instance of each rule **per device**, created only if the device exposes the
  tags the rule requires. Each instance owns its state. Current assignment:

  | Device | Rule 1 setpoint tracking | Rule 2 motor overtemp | Rule 3 vibration |
  |---|---|---|---|
  | shredder | yes | yes | yes |
  | extruder | yes | yes | yes |
  | water bath | no | no | no |
  | pelletizer | yes | yes | no |

- Rules receive only the tags they declare in `inputs`. Sim ground truth is never
  an input.
- Rules run on **sample time** (OPC UA SourceTimestamp), not wall time (D-32).
  The same code then behaves identically live, accelerated (`time_scale > 1`) and
  when replaying the historian offline. Replay is also how we will test rules
  against recorded fault scenarios.
- `on_tick(now)` handles timeout-style conditions. `now` is the newest sample
  time seen for that device.
- Output is `AlarmEvent` transitions (`raised` / `cleared`), stored in
  `alarm_event`.

**Gap (D-32):** if a device stops sending samples, its sample time freezes, and
timeout rules stop advancing with it. Stale-data detection must therefore use
connection state or wall time. It is a separate "communication lost" condition and
should not be inferred from missing samples inside the rules.

## 1. Rule 1: setpoint changed but speed is not following (D-33, D-34)

Trigger: a `SpeedSetpoint` change of at least `min_step_rpm`. Clear: |sp − pv| ≤
deadband. A new setpoint while the rule is armed re-arms it.

**Option A: fixed timeout (as in config).** Simple, but it is wrong for large
steps. With the drive's ramp limit `a` and time constant `τ`, the drive cannot
reach the deadband faster than:

    t_ramp     = max(0, |Δ| − a·τ) / a        (on the acceleration limit)
    t_settle   = τ · ln( min(|Δ|, a·τ) / δ )  (exponential tail into deadband δ)
    T_expected = t_ramp + t_settle

With the placeholder shredder/extruder drives (a = 300 rpm/s, τ = 1.0 s,
δ = 20 rpm), a 0 → 1800 rpm step needs 5.0 s + 2.7 s ≈ 7.7 s. **The timeout is
15 s** (about 2× that worst case). A small step (e.g. 100 rpm, T_expected ≈ 1.6 s)
then gets almost 10× its expected time before anyone is told. Any fixed timeout
trades false alarms on large steps against slow detection on small ones, and the
devices have different drives (the pelletizer is faster). Options B and C remove
that trade-off.

**Option B: timeout scaled from the drive's configured dynamics (recommended
first).** `T_allow = k · T_expected(|Δ|) + margin`. It needs only the drive's ramp
setting and an estimate of τ, which are configuration data for a real drive.

**Option C: model residual.** Run the drive model inside the analyzer, predict
ω(t) from the setpoint history, and alarm when |ω_meas − ω_pred| exceeds a
threshold for a minimum duration. This catches *sluggish* response (partial jam,
drive in current limit), not just *absent* response. It requires a reasonably
accurate drive model, which we will have from the simulator, but on a real
device the model would need identifying from data.

Message wording: "speed not following setpoint". Do not call it a "drive fault",
because a stuck speed sensor produces the same signature (fault-injection.md §3).

**Interaction with PLC logic (D-34).** Two PLC behaviors make "speed ≠ setpoint"
*correct*:
- the shredder's overload **auto-reverse** (stop, reverse, retry);
- the extruder's **cold-start interlock** (screw held at 0 until the barrel is hot).

Unless the PLC publishes its state (D-07), Rule 1 will flag both as faults.
Options: a state tag, which Rule 1 uses to suppress itself while the PLC is
deliberately overriding the setpoint (recommended); or the analyzer re-deriving
the PLC's logic, which is fragile and duplicates the PLC.

## 2. Rule 2: motor too hot (D-35)

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

Thresholds depend on what the sensor measures (winding or frame, plant-model.md
§2.2). Applies to the shredder and extruder motors. **Barrel** temperature is a
separate concern: too hot degrades the polymer. A barrel-deviation rule (|T_b −
setpoint| too large for too long, or heater pinned at 0 % / 100 %) is a natural
fourth rule using tags we already have.

## 3. Rule 3: anomalous vibration (D-24, D-36)

Pipeline per block (not implemented):

1. **Gate.** Skip blocks during speed transients, i.e. when |Δω| within the block
   is more than a few percent. A spectrum of a changing speed is smeared and
   compares badly with a steady-state baseline.
   **Shredder caveat:** cutting is impulsive and random, so healthy shredder
   vibration is non-stationary. Its baseline needs throughput-dependent bins and
   robust statistics (median and percentiles, not mean ± σ), or the rule will
   alarm on every hard chunk.
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
  bearings realistically (plant-model.md §2.3), plain FFT bands will miss early
  bearing faults. Envelope analysis needs a higher sample rate.
- **Absolute limits as a backstop.** ISO 20816 velocity-RMS zones flag a device
  that was already rough when the baseline was learned. The baseline method
  cannot catch that case.
- **Learned models** (isolation forest, autoencoder on spectra). Possible later,
  but the interpretable band features should come first, so that we can see
  what the learned model adds.

## 4. Motor current: logged, no rule (D-38)

`Motor/Current` is historized. Current-based detection was dropped. Note for
later: a current **spike** while the motor accelerates is normal, as you said. A
**sustained** rise at constant speed is not normal: it means a jam or increasing
friction. The earlier draft only tested the second case, because it ignored the
period after setpoint changes. If jams turn out to be hard to catch with Rule 1,
that is the check to bring back.

## 5. Alarm lifecycle (D-37)

Current: raise/clear transitions only. Industrial practice (ISA-18.2 / IEC 62682)
adds **acknowledgement** (active-unacked, active-acked, cleared-unacked),
**shelving** (temporarily suppress a known nuisance alarm), and alarm-flood
metrics. We should at least add ack before the dashboard shows alarms. An alarm
nobody has to acknowledge is easy to miss.
