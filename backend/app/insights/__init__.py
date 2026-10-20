"""Customer insight tools built on top of a finished, user-verified analysis.

Every module here reads stored data (analysis, findings, verified plan, catalogue) and returns plain
dicts. None of them changes the official analysis or score. Where a tool needs a "what if" number
(North sensitivity, as-built room types, a family-weighted view) it re-runs the same pure engines
in memory and labels the result as a simulation.
"""
