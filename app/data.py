"""Loads the static Pokemon reference dataset (pokemon.csv) into memory.

The dataset is read-only species data (stats, types, generation) so it is
kept in plain Python structures rather than a SQLite table; mutable,
per-user data (accounts, collections, teams) lives in SQLite via app.db.
"""

import csv
import os

from . import types as type_engine

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "pokemon.csv")

_BOOL_TRUE = {"TRUE", "true", "1"}


def _to_bool(value):
    return value.strip() in _BOOL_TRUE


def _row_to_pokemon(row):
    types = [row["type_1"]]
    if row["type_2"]:
        types.append(row["type_2"])
    stats = {
        "hp": int(row["hp"]),
        "attack": int(row["attack"]),
        "defense": int(row["defense"]),
        "special_attack": int(row["special_attack"]),
        "special_defense": int(row["special_defense"]),
        "speed": int(row["speed"]),
    }
    return {
        "pokedex_number": int(row["pokedex_number"]),
        "name": row["name"],
        "slug": row["slug"],
        "genus": row["genus"],
        "generation": int(row["generation"]),
        "types": types,
        "stats": stats,
        "total_stats": sum(stats.values()),
        "height_m": float(row["height_m"]),
        "weight_kg": float(row["weight_kg"]),
        "base_experience": int(row["base_experience"]) if row["base_experience"] else None,
        "capture_rate": int(row["capture_rate"]) if row["capture_rate"] else None,
        "base_happiness": int(row["base_happiness"]) if row["base_happiness"] else None,
        "is_baby": _to_bool(row["is_baby"]),
        "is_legendary": _to_bool(row["is_legendary"]),
        "is_mythical": _to_bool(row["is_mythical"]),
        "image_path": row["image_path"],
        "image_url": row.get("image_url") or "",
    }


def load_pokemon(csv_path=CSV_PATH):
    with open(csv_path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    pokemon = [_row_to_pokemon(r) for r in rows]
    pokemon.sort(key=lambda p: p["pokedex_number"])
    return pokemon


class PokemonDataset:
    """In-memory index over the full Pokemon roster plus derived stats
    used for stat-based tiebreaking in battle scoring."""

    def __init__(self, csv_path=CSV_PATH):
        self.by_number = {}
        self.order = []
        roster = load_pokemon(csv_path)
        for p in roster:
            self.by_number[p["pokedex_number"]] = p
            self.order.append(p["pokedex_number"])

        totals = [p["total_stats"] for p in roster]
        speeds = [p["stats"]["speed"] for p in roster]
        offenses = [max(p["stats"]["attack"], p["stats"]["special_attack"]) for p in roster]
        self._total_range = (min(totals), max(totals))
        self._speed_range = (min(speeds), max(speeds))
        self._offense_range = (min(offenses), max(offenses))

        self.generations = sorted({p["generation"] for p in roster})

    def all(self):
        return [self.by_number[n] for n in self.order]

    def get(self, pokedex_number):
        return self.by_number.get(pokedex_number)

    def exists(self, pokedex_number):
        return pokedex_number in self.by_number

    def matchup(self, pokedex_number):
        p = self.get(pokedex_number)
        if p is None:
            return None
        return type_engine.defensive_profile(p["types"])

    def _normalize(self, value, value_range):
        lo, hi = value_range
        if hi == lo:
            return 0.5
        return (value - lo) / (hi - lo)

    def battle_readiness(self, pokedex_number):
        """A 0..1 composite of speed, bulk and raw offense, used only as a
        secondary tiebreaker in battle scoring -- never to override type
        effectiveness. See app.battle for how this is weighted."""
        p = self.get(pokedex_number)
        if p is None:
            return 0.0
        stats = p["stats"]
        bulk = stats["hp"] + stats["defense"] + stats["special_defense"]
        offense = max(stats["attack"], stats["special_attack"])
        speed = stats["speed"]
        bulk_n = self._normalize(bulk, (self._total_range[0] * 0.5, self._total_range[1] * 0.5))
        offense_n = self._normalize(offense, self._offense_range)
        speed_n = self._normalize(speed, self._speed_range)
        return 0.35 * offense_n + 0.35 * bulk_n + 0.3 * speed_n


DATASET = PokemonDataset()
