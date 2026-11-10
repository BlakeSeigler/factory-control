-- Historian schema. Timestamps are unix seconds (REAL) taken from the OPC UA
-- SourceTimestamp, i.e. sim time. See docs/data.md for the narrow-vs-wide and
-- waveform-retention decisions (D-16, D-17).

PRAGMA journal_mode = WAL;   -- dashboard reads while the supervisor writes

CREATE TABLE IF NOT EXISTS machine (
    id        TEXT PRIMARY KEY,
    endpoint  TEXT NOT NULL
);

-- Narrow (entity-attribute-value) time series for every scalar tag.
-- Booleans are stored as 0.0 / 1.0.
CREATE TABLE IF NOT EXISTS sample (
    ts          REAL    NOT NULL,
    machine_id  TEXT    NOT NULL REFERENCES machine(id),
    tag         TEXT    NOT NULL,
    value       REAL    NOT NULL,
    status      INTEGER NOT NULL DEFAULT 0   -- OPC UA StatusCode, 0 = Good
);
CREATE INDEX IF NOT EXISTS sample_machine_tag_ts ON sample (machine_id, tag, ts);

-- Raw vibration blocks (float32 little-endian). Retention policy is D-17.
CREATE TABLE IF NOT EXISTS vibration_block (
    ts              REAL    NOT NULL,
    machine_id      TEXT    NOT NULL REFERENCES machine(id),
    sample_rate_hz  REAL    NOT NULL,
    n               INTEGER NOT NULL,
    data            BLOB    NOT NULL
);
CREATE INDEX IF NOT EXISTS vibration_block_machine_ts ON vibration_block (machine_id, ts);

-- Setpoints the supervisor itself issued, with attribution. (Every setpoint value,
-- whoever wrote it, is also in `sample` via the subscribed SpeedSetpoint tag.)
CREATE TABLE IF NOT EXISTS setpoint_command (
    ts          REAL NOT NULL,
    machine_id  TEXT NOT NULL REFERENCES machine(id),
    rpm         REAL NOT NULL,
    source      TEXT NOT NULL
);

-- Alarm transitions (raised / cleared). Current state = last transition per (machine, rule).
CREATE TABLE IF NOT EXISTS alarm_event (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL NOT NULL,
    machine_id  TEXT NOT NULL REFERENCES machine(id),
    rule        TEXT NOT NULL,
    severity    TEXT NOT NULL,
    transition  TEXT NOT NULL,
    message     TEXT NOT NULL,
    details     TEXT NOT NULL DEFAULT '{}'   -- JSON
);
CREATE INDEX IF NOT EXISTS alarm_event_machine_ts ON alarm_event (machine_id, ts);

-- Simulator ground truth (injected faults). Never read by the analyzer; used only to
-- score it offline (D-12).
CREATE TABLE IF NOT EXISTS sim_ground_truth (
    ts             REAL NOT NULL,
    machine_id     TEXT NOT NULL REFERENCES machine(id),
    active_faults  TEXT NOT NULL             -- JSON
);
