"""The learning layer: simulated fields, nodes, producers and seasons, and the three models (A, B, C) trained on them.

Everything here that is not NASA data is simulated and says so (`simulated: True`, source `simulated_panel`): the panel measures whether
the method recovers a structure planted on purpose, never how accurate it would be on real fields. Real data replaces the panel by
adding rows to the tables in `data/learning/`; the models and the registry do not change.
"""
