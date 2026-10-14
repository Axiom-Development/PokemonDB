"""The modern (Gen 6+) 18-type effectiveness chart and dual-type math.

This is the single source of truth for every type calculation in the app
(Pokedex weakness panels, battle rankings, team coverage). Only exceptions to
a neutral 1x multiplier are listed below; any attacker/defender pair not
present here is neutral.
"""

ALL_TYPES = [
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting",
    "Poison", "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost",
    "Dragon", "Dark", "Steel", "Fairy",
]

_TYPE_SET = set(ALL_TYPES)

# chart[attacking_type][defending_type] = multiplier
CHART = {
    "Normal":   {"Rock": 0.5, "Ghost": 0, "Steel": 0.5},
    "Fire":     {"Fire": 0.5, "Water": 0.5, "Grass": 2, "Ice": 2, "Bug": 2,
                 "Rock": 0.5, "Dragon": 0.5, "Steel": 2},
    "Water":    {"Fire": 2, "Water": 0.5, "Grass": 0.5, "Ground": 2,
                 "Rock": 2, "Dragon": 0.5},
    "Electric": {"Water": 2, "Electric": 0.5, "Grass": 0.5, "Ground": 0,
                 "Flying": 2, "Dragon": 0.5},
    "Grass":    {"Fire": 0.5, "Water": 2, "Grass": 0.5, "Poison": 0.5,
                 "Ground": 2, "Flying": 0.5, "Bug": 0.5, "Rock": 2,
                 "Dragon": 0.5, "Steel": 0.5},
    "Ice":      {"Fire": 0.5, "Water": 0.5, "Grass": 2, "Ice": 0.5,
                 "Ground": 2, "Flying": 2, "Dragon": 2, "Steel": 0.5},
    "Fighting": {"Normal": 2, "Ice": 2, "Poison": 0.5, "Flying": 0.5,
                 "Psychic": 0.5, "Bug": 0.5, "Rock": 2, "Ghost": 0,
                 "Dark": 2, "Steel": 2, "Fairy": 0.5},
    "Poison":   {"Grass": 2, "Poison": 0.5, "Ground": 0.5, "Rock": 0.5,
                 "Ghost": 0.5, "Steel": 0, "Fairy": 2},
    "Ground":   {"Fire": 2, "Electric": 2, "Grass": 0.5, "Poison": 2,
                 "Flying": 0, "Bug": 0.5, "Rock": 2, "Steel": 2},
    "Flying":   {"Electric": 0.5, "Grass": 2, "Fighting": 2, "Bug": 2,
                 "Rock": 0.5, "Steel": 0.5},
    "Psychic":  {"Fighting": 2, "Poison": 2, "Psychic": 0.5, "Dark": 0,
                 "Steel": 0.5},
    "Bug":      {"Fire": 0.5, "Grass": 2, "Fighting": 0.5, "Poison": 0.5,
                 "Flying": 0.5, "Psychic": 2, "Ghost": 0.5, "Dark": 2,
                 "Steel": 0.5, "Fairy": 0.5},
    "Rock":     {"Fire": 2, "Ice": 2, "Fighting": 0.5, "Ground": 0.5,
                 "Flying": 2, "Bug": 2, "Steel": 0.5},
    "Ghost":    {"Normal": 0, "Psychic": 2, "Ghost": 2, "Dark": 0.5},
    "Dragon":   {"Dragon": 2, "Steel": 0.5, "Fairy": 0},
    "Dark":     {"Fighting": 0.5, "Psychic": 2, "Ghost": 2, "Dark": 0.5,
                 "Fairy": 0.5},
    "Steel":    {"Fire": 0.5, "Water": 0.5, "Electric": 0.5, "Ice": 2,
                 "Rock": 2, "Steel": 0.5, "Fairy": 2},
    "Fairy":    {"Fighting": 2, "Poison": 0.5, "Bug": 0.5, "Dragon": 2,
                 "Dark": 2, "Steel": 0.5},
}


def _validate():
    for atk, row in CHART.items():
        assert atk in _TYPE_SET, f"unknown attacking type {atk}"
        for d, mult in row.items():
            assert d in _TYPE_SET, f"unknown defending type {d}"
            assert mult in (0, 0.25, 0.5, 2, 4), f"unexpected multiplier {mult}"


_validate()


def single_multiplier(attacking_type, defending_type):
    """Multiplier of one attacking type against one defending type."""
    return CHART.get(attacking_type, {}).get(defending_type, 1)


def dual_multiplier(attacking_type, defending_types):
    """Multiplier of one attacking type against a defender's 1-2 types.

    Multiplies across both defending types, which is how the games combine
    dual typing (e.g. a Ground move vs. a Water/Flying defender is
    1 x 0 = 0 -- Ground is neutral against Water, but Flying is immune to
    Ground, so the immunity carries through; a quad weakness is 2 x 2 = 4).
    """
    result = 1.0
    for t in defending_types:
        if t:
            result *= single_multiplier(attacking_type, t)
    return result


def defensive_profile(defending_types):
    """Map of every attacking type -> multiplier against this defender."""
    return {t: dual_multiplier(t, defending_types) for t in ALL_TYPES}


def best_offensive_multiplier(attacking_types, defending_types):
    """Best multiplier the attacker can land using either of its own types
    as STAB (same-type attack bonus) against the defender's typing."""
    options = [dual_multiplier(t, defending_types) for t in attacking_types if t]
    return max(options) if options else 1.0


def worst_defensive_multiplier(defending_types, attacking_types):
    """Worst (highest) incoming multiplier the defender faces from any one
    of the attacker's own types."""
    options = [dual_multiplier(t, defending_types) for t in attacking_types if t]
    return max(options) if options else 1.0
