# Vendored verbatim from PCFBench upstream for strict-mode alignment.
# Source: /tmp/harness-consult-20261101-r23-pcfbench-gold-audit/materials/upstream/unit_normalization.py
# (watershed-climate/pcfbench scoring; commit referenced in claim_f1 UNIT_TABLE_VERSION)

"""Unit normalization for extraction-claim matching.

Returns a canonical unit string and a scale factor so that numerically
equivalent claims expressed in different units (kgCO2e/tonne vs kg CO2eq per kg,
g/kg vs kg/kg, GJ/t vs MJ/kg, m² vs m2) match correctly during scoring.
"""

from __future__ import annotations

import re

# Unicode → ASCII for super/subscripts that show up in CO2/m² spellings.
_UNICODE_REPLACEMENTS: dict[str, str] = {
    "²": "2",
    "³": "3",
    "₂": "2",
    "₃": "3",
    "⁻": "-",
    "·": "/",
}

# Each entry: lookup key (canonicalized via _canonical_key) →
# (canonical unit, scale factor to multiply value by).
UNIT_NORMALIZATION: dict[str, tuple[str, float]] = {
    # --- Percent ---
    "%": ("percent", 1.0),
    "percent": ("percent", 1.0),
    "mass%": ("percent", 1.0),
    "wt%": ("percent", 1.0),
    "weight%": ("percent", 1.0),
    "%mass": ("percent", 1.0),
    "%wt": ("percent", 1.0),
    "percentreduction": ("percent", 1.0),
    # --- Mass ratio ---
    "kg/kg": ("kg/kg", 1.0),
    "g/kg": ("kg/kg", 0.001),
    "gr/kg": ("kg/kg", 0.001),
    "grams/kilogram": ("kg/kg", 0.001),
    "grams/kg": ("kg/kg", 0.001),
    # --- Energy intensity ---
    "mj/kg": ("mj/kg", 1.0),
    "gj/t": ("mj/kg", 1.0),  # 1 GJ/tonne = 1 MJ/kg numerically
    "gj/tonne": ("mj/kg", 1.0),
    "kwh/kg": ("kwh/kg", 1.0),
    "kw.hr/kg": ("kwh/kg", 1.0),
    "kwhr/kg": ("kwh/kg", 1.0),
    "kwh/ton": ("kwh/kg", 0.001),
    "kwh/tonne": ("kwh/kg", 0.001),
    "btu/lb": ("btu/lb", 1.0),
    "btu/lbm": ("btu/lb", 1.0),
    # --- kgCO2e per kg of product (carbon intensity, mass basis) ---
    "kgco2e/kg": ("kgco2e/kg", 1.0),
    "kgco2eq/kg": ("kgco2e/kg", 1.0),
    "kgco2eqperkg": ("kgco2e/kg", 1.0),
    "kgco2eperkg": ("kgco2e/kg", 1.0),
    "kgco2eq/1kg": ("kgco2e/kg", 1.0),
    "kgco2/kg": ("kgco2e/kg", 1.0),
    # tonne basis is 1000× kg basis numerically when both sides are tonne, kg
    "kgco2e/tonne": ("kgco2e/kg", 0.001),
    "kgco2eq/tonne": ("kgco2e/kg", 0.001),
    "kgco2e/t": ("kgco2e/kg", 0.001),
    # tonnes CO2e per tonne == kgCO2e per kg numerically (ratio of equal scales)
    "tonnesco2e/tonne": ("kgco2e/kg", 1.0),
    "tco2e/tonne": ("kgco2e/kg", 1.0),
    "tco2e/t": ("kgco2e/kg", 1.0),
    # --- kgCO2e per m² (carbon intensity, area basis) ---
    "kgco2e/m2": ("kgco2e/m2", 1.0),
    "kgco2eq/m2": ("kgco2e/m2", 1.0),
    # --- kgCO2e per functional unit (semantic basis; preserved as-is) ---
    "kgco2e/fu": ("kgco2e/fu", 1.0),
    "kgco2eq/fu": ("kgco2e/fu", 1.0),
}


def _canonical_key(unit: str) -> str:
    """Reduce a free-form unit string to a punctuation-stripped lookup key.

    Handles Unicode subscript/superscript digits (²/₂), removes decorative
    characters (periods, hyphens, " eq", " per " → "/"), and lowercases.
    """
    s = unit.strip().lower()
    for old, new in _UNICODE_REPLACEMENTS.items():
        s = s.replace(old, new)
    s = s.replace(" per ", "/")
    s = s.replace("-eq.", "eq").replace("-eq", "eq")
    s = s.replace(" eq.", "eq").replace(" eq", "eq")
    s = s.replace("eq.", "eq")
    s = s.replace(".", "")
    s = s.replace("-", "")
    s = re.sub(r"\s+", "", s)
    return s


def normalize_value_and_unit(value: float, unit: str) -> tuple[float, str]:
    """Return ``(scaled_value, canonical_unit)`` for a raw extraction claim.

    Unknown units are passed through with the value unchanged and the
    canonicalized lookup key as the unit, so two predictions in the same
    unknown form still compare equal.
    """
    key = _canonical_key(unit)
    if key in UNIT_NORMALIZATION:
        canonical, scale = UNIT_NORMALIZATION[key]
        return value * scale, canonical
    return value, key


def normalize_unit(unit: str) -> str:
    """Backwards-compatible string-only normalization."""
    _, canonical = normalize_value_and_unit(1.0, unit)
    return canonical
