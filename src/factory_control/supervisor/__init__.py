"""Supervisor process: OPC UA clients, historian, analyzer and controller.

Data flow inside the process::

    MachineClient(feeder_1) --\               /--> Historian      -> SQLite
                               >-- Bus --+---> StateCache     -> Controller -> client.write
    MachineClient(feeder_2) --/               \--> AnalyzerEngine -> alarms -> Historian
"""
