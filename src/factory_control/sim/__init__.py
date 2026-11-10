"""Plant model of the pellet line. Pure Python/numpy, no OPC UA dependency.

Layering (see docs/plant-model.md):

    true physical state  --(sensors.py)-->  measured values  --(machine/)-->  OPC UA

Process faults (jam, bridging, winding short) act on the physics; sensor faults
(stuck, drift, noise) act only in the measurement layer. Keeping the two layers
separate is what lets us ask "did the analyzer see what really happened".
"""
