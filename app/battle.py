"""Deterministic, type-based battle scoring.

Everything here is derived only from species types and base stats (see
app.types for the 18-type chart). There are no movesets, abilities or
levels in the dataset, so this models match-up *potential*, not a
battle simulator -- the API and UI both label results as planning advice.

Scoring formula (documented so results are explainable, not a black box):

1. For a candidate vs. one opponent, find the candidate's best possible
   STAB type advantage (`best_offensive_multiplier`) and the worst hit it
   would take from the opponent's own types (`worst_defensive_multiplier`).
2. Each multiplier is converted to points on a symmetric scale:
     OFFENSE_POINTS: 4x->+2  2x->+1  1x->0  0.5x->-1  0.25x->-2  0x->-3
     DEFENSE_POINTS: 0x->+3  0.25x->+2  0.5x->+1  1x->0  2x->-1  4x->-2
   (0x offense is scored worse than being resisted, since the candidate's
   own typing can never land a type advantage; 0x defense is scored best,
   since the candidate is immune outright.)
3. type_score = offense_points + defense_points, in range [-5, +5].
4. Against an opposing team, type_score is averaged across all members.
   Because every per-opponent type_score is an integer, two candidates'
   average type_scores against the same N-member team (N up to
   MAX_TEAM_SIZE) can differ by as little as 1/N -- as low as 1/6.
5. A small stat-based tiebreaker (`battle_readiness`, raw range [0, 1)) is
   scaled by STAT_BONUS_WEIGHT before being added, so its maximum possible
   contribution stays strictly below 1/MAX_TEAM_SIZE. That guarantees
   stats can only ever decide between otherwise type-equal candidates
   (equal average type_score) and can never outrank a genuine type
   difference, no matter how many opponents are being scored against.

Team generation uses a deterministic greedy pass: repeatedly add the
remaining candidate with the best marginal value (match-up score, plus a
bonus for covering opposing/attacking types the team doesn't hit yet,
minus a penalty for stacking a weakness the team already shares), with
ties broken by ascending Pokedex number so results are reproducible.
"""

from . import types as type_engine

OFFENSE_POINTS = {4: 2, 2: 1, 1: 0, 0.5: -1, 0.25: -2, 0: -3}
DEFENSE_POINTS = {0: 3, 0.25: 2, 0.5: 1, 1: 0, 2: -1, 4: -2}

MAX_TEAM_SIZE = 6

# Scales battle_readiness (raw range [0, 1)) down so its full range (max
# STAT_BONUS_WEIGHT) stays strictly below 1/MAX_TEAM_SIZE (~0.167) -- the
# smallest possible gap between two distinct average type_scores against an
# up-to-6-member team. This is what makes the stat tiebreaker provably
# unable to outrank a real type-effectiveness difference (see module
# docstring, point 5).
STAT_BONUS_WEIGHT = 0.15

COVERAGE_BONUS = 0.5
SHARED_WEAKNESS_PENALTY = 0.75
IMPROVEMENT_MARGIN = 1.0
NOTABLE_STAT_GAP = 10


def fmt_mult(mult):
    if mult == int(mult):
        return f"{int(mult)}x"
    return f"{mult}x"


def _offense_points(mult):
    return OFFENSE_POINTS.get(mult, 0)


def _defense_points(mult):
    return DEFENSE_POINTS.get(mult, 0)


def best_offensive_type(candidate_types, defending_types):
    best_type, best_mult = None, -1
    for t in candidate_types:
        if not t:
            continue
        mult = type_engine.dual_multiplier(t, defending_types)
        if mult > best_mult:
            best_type, best_mult = t, mult
    return best_type, (best_mult if best_type else 1.0)


def worst_defensive_type(candidate_types, attacking_types):
    worst_type, worst_mult = None, -1
    for t in attacking_types:
        if not t:
            continue
        mult = type_engine.dual_multiplier(t, candidate_types)
        if mult > worst_mult:
            worst_type, worst_mult = t, mult
    return worst_type, (worst_mult if worst_type else 1.0)


def type_score(candidate_types, opponent_types):
    """Single-opponent type_score for one candidate; see module docstring."""
    _, off_mult = best_offensive_type(candidate_types, opponent_types)
    _, def_mult = worst_defensive_type(candidate_types, opponent_types)
    return _offense_points(off_mult) + _defense_points(def_mult)


def score_candidate(dataset, pokedex_number, opponent_type_lists):
    """Full scoring + explanation for one candidate against one or more
    opponents (each entry in opponent_type_lists is an opponent's type
    list)."""
    p = dataset.get(pokedex_number)
    c_types = p["types"]

    per_opponent = []
    for o_types in opponent_type_lists:
        off_type, off_mult = best_offensive_type(c_types, o_types)
        def_type, def_mult = worst_defensive_type(c_types, o_types)
        per_opponent.append({
            "offense_type": off_type,
            "offense_multiplier": off_mult,
            "defense_type": def_type,
            "defense_multiplier": def_mult,
            "type_score": _offense_points(off_mult) + _defense_points(def_mult),
        })

    avg_type_score = sum(o["type_score"] for o in per_opponent) / len(per_opponent)
    stat_bonus = dataset.battle_readiness(pokedex_number)
    final_score = avg_type_score + stat_bonus * STAT_BONUS_WEIGHT

    best = max(per_opponent, key=lambda o: o["type_score"])
    worst = min(per_opponent, key=lambda o: o["type_score"])

    return {
        "pokedex_number": pokedex_number,
        "name": p["name"],
        "types": c_types,
        "score": round(final_score, 3),
        "type_score": round(avg_type_score, 3),
        "stat_bonus": round(stat_bonus, 3),
        "best_matchup": best,
        "worst_matchup": worst,
        "per_opponent": per_opponent,
    }


def explain(result, opponent_names):
    """Builds a plain-language explanation sentence from a scored result."""
    name = result["name"]
    best = result["best_matchup"]
    single = len(opponent_names) == 1
    if single:
        opp = opponent_names[0]
        off = best["offense_type"]
        off_m = fmt_mult(best["offense_multiplier"])
        def_t = best["defense_type"]
        def_m = fmt_mult(best["defense_multiplier"])
        parts = []
        if best["offense_multiplier"] > 1:
            parts.append(f"{name}'s {off} typing hits {opp} for {off_m}")
        elif best["offense_multiplier"] < 1:
            parts.append(f"{name}'s best type advantage against {opp} is only {off_m} ({off})")
        else:
            parts.append(f"{name} trades neutral {off_m} damage with {opp}")
        if best["defense_multiplier"] < 1:
            parts.append(f"and takes just {def_m} back from {opp}'s {def_t}-type attacks")
        elif best["defense_multiplier"] > 1:
            parts.append(f"but takes {def_m} from {opp}'s {def_t}-type attacks")
        else:
            parts.append(f"and takes neutral damage in return")
        return " ".join(parts) + "."
    else:
        avg = result["type_score"]
        best_opp = opponent_names[result["per_opponent"].index(best)] if best in result["per_opponent"] else None
        tone = "a strong" if avg > 1.5 else "a solid" if avg > 0 else "a risky"
        sentence = f"{name} is {tone} pick against this team (average type score {avg:+.1f})."
        if best_opp:
            sentence += f" Best matchup: {best_opp} at {fmt_mult(best['offense_multiplier'])} offense / {fmt_mult(best['defense_multiplier'])} defense."
        return sentence


def rank_counters(dataset, opponent_type_lists, opponent_names, pool, limit=20):
    """Ranks `pool` (an iterable of pokedex numbers) against the given
    opponent(s), best match-up first. Ties broken by ascending Pokedex
    number for determinism."""
    scored = [score_candidate(dataset, n, opponent_type_lists) for n in pool]
    scored.sort(key=lambda r: (-r["score"], r["pokedex_number"]))
    top = scored[:limit]
    for r in top:
        r["explanation"] = explain(r, opponent_names)
    return top


def stat_gap_notes(current, suggestion):
    """Factual, stat-only tradeoff notes (never invented moves/abilities)."""
    notes = []
    c_stats, s_stats = current["stats"], suggestion["stats"]
    c_bulk = c_stats["hp"] + c_stats["defense"] + c_stats["special_defense"]
    s_bulk = s_stats["hp"] + s_stats["defense"] + s_stats["special_defense"]
    c_off = max(c_stats["attack"], c_stats["special_attack"])
    s_off = max(s_stats["attack"], s_stats["special_attack"])
    if s_bulk < c_bulk - NOTABLE_STAT_GAP:
        notes.append(f"{suggestion['name']} has {c_bulk - s_bulk} less combined bulk (HP+Def+Sp.Def)")
    if s_stats["speed"] < c_stats["speed"] - NOTABLE_STAT_GAP:
        notes.append(f"{c_stats['speed'] - s_stats['speed']} less Speed")
    if s_off < c_off - NOTABLE_STAT_GAP:
        notes.append(f"{c_off - s_off} less peak offense (Attack/Sp. Atk)")
    if not notes:
        notes.append("no notable stat downside versus the member it would replace")
    return notes


def suggest_replacements(dataset, team_members, opponent_type_lists, opponent_names, owned_set, max_suggestions=3):
    """For an owned team, looks for unowned Pokemon that would meaningfully
    improve the weakest slot(s) against the given opponent(s). Returned
    separately from the generated team -- never auto-applied."""
    scored_team = [score_candidate(dataset, n, opponent_type_lists) for n in team_members]
    scored_team.sort(key=lambda r: r["score"])  # weakest first

    unowned_pool = [n for n in dataset.order if n not in owned_set and n not in team_members]
    scored_unowned = [score_candidate(dataset, n, opponent_type_lists) for n in unowned_pool]
    scored_unowned.sort(key=lambda r: (-r["score"], r["pokedex_number"]))

    suggestions = []
    used_suggestions = set()
    for weak in scored_team[:max_suggestions]:
        better = [
            r for r in scored_unowned
            if r["score"] >= weak["score"] + IMPROVEMENT_MARGIN
            and r["pokedex_number"] not in used_suggestions
        ]
        if not better:
            continue
        pick = better[0]
        used_suggestions.add(pick["pokedex_number"])
        current_p = dataset.get(weak["pokedex_number"])
        suggestion_p = dataset.get(pick["pokedex_number"])
        suggestions.append({
            "replaces": {"pokedex_number": weak["pokedex_number"], "name": weak["name"], "score": weak["score"]},
            "suggestion": {"pokedex_number": pick["pokedex_number"], "name": pick["name"], "score": pick["score"]},
            "improvement": round(pick["score"] - weak["score"], 3),
            "reason": explain(pick, opponent_names),
            "tradeoffs": stat_gap_notes(current_p, suggestion_p),
        })
    return suggestions


def _marginal_value(dataset, candidate, opponent_type_lists, offense_covered, weakness_counts):
    p = dataset.get(candidate)
    c_types = p["types"]

    if opponent_type_lists:
        base = sum(type_score(c_types, o) for o in opponent_type_lists) / len(opponent_type_lists)
    else:
        # No opponent given (Team Builder's generic auto-build): reward
        # broad offensive coverage and bulk against the whole type chart.
        hits = sum(1 for t in type_engine.ALL_TYPES if type_engine.dual_multiplier(t, c_types) == 0)
        strong = sum(1 for t in type_engine.ALL_TYPES
                     if type_engine.best_offensive_multiplier(c_types, [t]) >= 2)
        weak = sum(1 for t in type_engine.ALL_TYPES
                    if type_engine.dual_multiplier(t, c_types) >= 2)
        base = 0.1 * strong - 0.15 * weak + 0.2 * hits

    coverage_gain = 0.0
    for t in type_engine.ALL_TYPES:
        if t in offense_covered:
            continue
        if type_engine.best_offensive_multiplier(c_types, [t]) >= 2:
            coverage_gain += COVERAGE_BONUS

    redundancy = 0.0
    for t in type_engine.ALL_TYPES:
        if type_engine.dual_multiplier(t, c_types) >= 2 and weakness_counts.get(t, 0) >= 1:
            redundancy += SHARED_WEAKNESS_PENALTY

    stat_bonus = dataset.battle_readiness(candidate)
    return base + coverage_gain - redundancy + stat_bonus * STAT_BONUS_WEIGHT


def generate_team(dataset, pool, opponent_type_lists=None, size=6):
    """Greedy, deterministic coverage-maximizing team builder.

    `pool` is the candidate universe (owned-only or the full roster,
    decided by the caller). Returns fewer than `size` members, with
    `shortfall=True`, if the pool itself has fewer eligible Pokemon.
    """
    remaining = list(dict.fromkeys(pool))  # dedupe, preserve order
    team = []
    offense_covered = set()
    weakness_counts = {t: 0 for t in type_engine.ALL_TYPES}

    while remaining and len(team) < size:
        best_candidate, best_value = None, None
        for candidate in remaining:
            value = _marginal_value(dataset, candidate, opponent_type_lists, offense_covered, weakness_counts)
            key = (value, -candidate)
            if best_value is None or key > best_value:
                best_candidate, best_value = candidate, key
        team.append(best_candidate)
        remaining.remove(best_candidate)

        c_types = dataset.get(best_candidate)["types"]
        for t in type_engine.ALL_TYPES:
            if type_engine.best_offensive_multiplier(c_types, [t]) >= 2:
                offense_covered.add(t)
            if type_engine.dual_multiplier(t, c_types) >= 2:
                weakness_counts[t] = weakness_counts.get(t, 0) + 1

    return {
        "members": team,
        "requested_size": size,
        "shortfall": len(team) < size,
    }


def analyze_team(dataset, members):
    """Type coverage + shared weaknesses + stat overview for a team of
    pokedex numbers (1-6)."""
    pokes = [dataset.get(n) for n in members]
    offense_coverage = {}
    for t in type_engine.ALL_TYPES:
        best = max((type_engine.best_offensive_multiplier(p["types"], [t]) for p in pokes), default=1.0)
        offense_coverage[t] = best

    shared_weaknesses = {}
    for t in type_engine.ALL_TYPES:
        count = sum(1 for p in pokes if type_engine.dual_multiplier(t, p["types"]) >= 2)
        if count >= 2:
            shared_weaknesses[t] = count

    immunity_gaps = [t for t in type_engine.ALL_TYPES if offense_coverage[t] <= 0.5]

    totals = {"hp": 0, "attack": 0, "defense": 0, "special_attack": 0, "special_defense": 0, "speed": 0}
    for p in pokes:
        for k in totals:
            totals[k] += p["stats"][k]
    averages = {k: round(v / len(pokes), 1) for k, v in totals.items()} if pokes else {}

    return {
        "offense_coverage": offense_coverage,
        "shared_weaknesses": shared_weaknesses,
        "weak_offense_types": immunity_gaps,
        "stat_totals": totals,
        "stat_averages": averages,
        "size": len(pokes),
    }
