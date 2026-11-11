r"""Supervisor process: OPC UA clients, historian, analyzer and controller.

Data flow inside the process (one DeviceClient = one OPC UA session per PLC)::

    DeviceClient(shredder)   --\                /--> Historian      -> SQLite
    DeviceClient(extruder)   ---+-> Bus fan-out +--> StateCache     -> Controller -> client.write
    DeviceClient(water_bath) ---+               \--> AnalyzerEngine -> alarms -> Historian
    DeviceClient(pelletizer) --/
"""
