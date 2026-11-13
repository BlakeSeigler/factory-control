# OPC UA: what it is, and how this project uses it

## 1. Is it really client/server?

Yes. The roles are asymmetric, even though data moves in both directions.

- A **server** owns an *address space*: a graph of nodes (objects, variables,
  methods, types) that describes the device. It never initiates a request.
- A **client** opens a *session* to a server and calls *services* on it: `Browse`,
  `Read`, `Write`, `Call` (methods), `CreateSubscription` /
  `CreateMonitoredItems`, `Publish`.

Data flows server → client (reads, change notifications) and client → server
(writes, method calls). **Every exchange starts with a client request.** That
includes "push" notifications. The client keeps `Publish` requests outstanding.
The server holds them and answers one when it has notifications, or when the
keep-alive interval expires with nothing to report. It works like long polling.
So the server only pushes by answering requests the client already made, and a
server cannot contact a client that never connected.

A program can be both. A SCADA or edge gateway is typically a client to many
devices and a server to an MES above it (an *aggregating server*).

**In this project:** each device's PLC is a **server** (real PLCs host OPC UA
servers themselves). The supervisor is a single **client** process holding one
session per PLC, so four independent connections. "Each device has its own
connection" is satisfied by sessions. Separate client processes would add nothing.

### And PubSub?

OPC UA Part 14 (PubSub) is a second, different model. Publishers emit
`DataSetMessages` over UDP multicast or through a broker (MQTT/AMQP). There are no
sessions, and subscribers are anonymous and decoupled. It is designed for
one-to-many distribution: cloud ingestion, and controller-to-controller traffic
over TSN. It does not provide what we need for supervisory control:
an acknowledged, per-request write ("did the drive accept my setpoint?"). We use
client/server.

## 2. Concepts you will see in the code

| Concept | Meaning | Where |
|---|---|---|
| Namespace URI / index | Nodes live in namespaces. The URI is stable. The index is just the URI's position in the server's namespace array and **may differ between servers**. Clients must resolve the index from the URI on every connect. | `client.get_namespace_index(FEEDER_NS_URI)` |
| NodeId | (namespace index, identifier). Server-assigned here. We never hard-code NodeIds; we resolve by browse path. | `client.py::_subscribe` |
| BrowseName / browse path | Human-meaningful path such as `Extruder/Barrel/Temperature`. This is our contract. | `common/tags.py` |
| DataValue | A variable's value plus **StatusCode** (Good/Uncertain/Bad), **SourceTimestamp** (when the source sampled it) and **ServerTimestamp** (when the server stored it). | `server.py::_write` |
| Subscription | A container on the server with a *publishing interval*: how often it may send batched notifications. | `subscription_period_ms` |
| MonitoredItem | One watched attribute in a subscription. It has a *sampling interval* (how often the server checks the value), a *queue size*, and a *filter*. | defaults today (D-11) |
| DataChangeFilter | Trigger (Status / StatusValue / StatusValueTimestamp) and deadband (none / absolute / percent). This decides what counts as a change. | defaults today (D-11) |

### Report-by-exception and what it means for our data

With the default trigger (StatusValue), the server only notifies when the value or
status **changes**. A motor holding exactly 1200.0 rpm generates no traffic.
Consequences:

1. A historian row means "the value became *v* at *t* and **held** until the next
   row". The dashboard therefore draws step lines. Linear interpolation would draw
   ramps that never happened. We hit exactly this bug while building the dashboard.
2. Averages over time must be **time-weighted**. A plain `AVG(value)` over
   rows is wrong.
3. Silence is ambiguous: a constant value and a dead source both produce no
   samples. Subscription keep-alives and status changes distinguish them at the
   session level, and the analyzer needs an explicit stale-data check (D-32).
4. Once sensor noise exists, every published value differs, so traffic and
   storage rise to the full publish rate unless we configure a deadband (D-11).

## 3. Writes vs. methods for commands

| | Writable variable (`SpeedSetpoint`) | Method (`SetSpeed(rpm)`) |
|---|---|---|
| Semantics | "Desired state is X" | "Do this action" |
| Readback | The value is the current setpoint; any client can read or subscribe to it | Needs a separate variable to expose the state |
| Validation | Server returns per-node StatusCode (e.g. `BadOutOfRange`) | Arbitrary validation, multiple args, multiple outputs |
| Atomic multi-parameter | No | Yes |
| Typical use | Setpoints | Start/Stop/Reset, recipes, fault injection |

A setpoint is state, so we use a writable variable. Fault injection is an action
with parameters, so we use methods.

**Known gap (D-13):** the PLC currently *clamps* an out-of-range setpoint (motor
speed above max, barrel setpoint above `max_setpoint_c`) and logs it, but the node
still shows the requested value (e.g. 2500 rpm while 1800 is applied). That is misleading. Options:
(a) reject with `BadOutOfRange` via a write setter, so the client gets an
explicit error (recommended);
(b) write the clamped value back to the node;
(c) add a separate read-only `AppliedSetpoint` tag. Real drives commonly do (c)
in addition to (a).

## 4. Security (D-12)

OPC UA security has three layers:

- **Secure channel**: SecurityMode `None` / `Sign` / `SignAndEncrypt`, with a
  SecurityPolicy such as `Basic256Sha256` or `Aes256_Sha256_RsaPss`. Both
  applications authenticate each other with **application instance certificates**
  checked against trust lists.
- **User authentication** inside the session: anonymous, username/password, or
  X.509 user certificate.
- **Authorization**: per-node access levels and roles.

We run `None` on 127.0.0.1 for development. Before these processes run on a real
network, use `SignAndEncrypt` with certificates. Without it, anyone on the network
can change motor speeds.

## 5. Our address space

Generated per device type from `common/tags.py` (single source of truth). Each PLC
exposes one root object named after its type, in namespace
`urn:factory-control:device`:

```
Objects/Shredder/                         Objects/Extruder/
  Identification/DeviceId   String          Identification/DeviceId     String
  Hopper/LevelLow           Boolean         Hopper/LevelLow             Boolean
  Hopper/LevelHigh          Boolean         Hopper/LevelHigh            Boolean
  Hopper/Weight             Double kg       Motor/SpeedSetpoint         Double rpm  RW
  Motor/SpeedSetpoint       Double rpm RW   Motor/Speed                 Double rpm
  Motor/Speed               Double rpm      Motor/Current               Double A
  Motor/Current             Double A        Motor/Temperature           Double degC
  Motor/Temperature         Double degC     Vibration/SampleRate        Double Hz
  Vibration/SampleRate      Double Hz       Vibration/Waveform          Double[]
  Vibration/Waveform        Double[]        Barrel/TemperatureSetpoint  Double degC RW
                                            Barrel/Temperature          Double degC
Objects/WaterBath/                          Barrel/HeaterOutput         Double %
  Identification/DeviceId   String
  Bath/WaterTemperature     Double degC   Objects/Pelletizer/
                                            Identification/DeviceId     String
                                            Motor/SpeedSetpoint         Double rpm  RW
                                            Motor/Speed                 Double rpm
                                            Motor/Current               Double A
                                            Motor/Temperature           Double degC
                                            Strands/Present             Boolean[] one per strand
                                            Strands/Count               Double (PLC-computed)

Every server also has, in namespace urn:factory-control:simulation (sim only, D-14):
  Objects/Simulation/ActiveFaults (String JSON), InjectFault(name, params_json), ClearFaults()
```

Level switches: `True` means material is present at the switch. `Hopper/Weight`
exists only where a load cell is fitted (the shredder). `Barrel/HeaterOutput` is
the PLC's PID output, not a sensor. A PLC publishes its own internal values like
this routinely, and they are diagnostically valuable: a heater at 100 % that
cannot reach its setpoint means a failed heater band.

**Why a custom model and not a companion specification?** Industry information
models exist: OPC UA for Machinery (OPC 40001) and the plastics and rubber
machinery specifications from EUROMAP (the 77/83/84 family; 84 covers extrusion).
Conforming to one adds many mandatory nodes and type definitions that do not help
us learn or test the control problem. The tag contract is isolated in one module,
so mapping it onto a companion spec later is a contained change.

## 6. Connection lifecycle in our client

`DeviceClient.run` connects, resolves namespace indices and nodes, creates one
subscription, and then calls `check_connection()` once per second. On any failure
it tears the session down and reconnects with exponential backoff (1 s → 30 s).
Session timeout is 30 s, so the server reclaims a dead supervisor's session
quickly. Each device has its own client, session and task, so an outage on one
device does not affect the others.
