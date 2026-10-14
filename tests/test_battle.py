import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import battle
from app.data import DATASET


class TestScoring(unittest.TestCase):
    def test_type_score_range(self):
        # Charizard (Fire/Flying) vs Venusaur (Grass/Poison): Fire is 2x vs Grass,
        # neutral vs Poison -> best offense 2x (+1). Grass/Poison vs Fire/Flying:
        # Grass->Fire 0.5, Grass->Flying 1 => 0.5; Poison->Fire 1, Poison->Flying 1 => 1.
        # worst defensive multiplier an opponent lands is max(0.5, 1) = 1 (neutral, 0 pts).
        charizard = DATASET.get(6)
        venusaur = DATASET.get(3)
        score = battle.type_score(charizard["types"], venusaur["types"])
        self.assertEqual(score, 1)  # +1 offense, 0 defense

    def test_immunity_offense_worse_than_resisted(self):
        self.assertLess(battle.OFFENSE_POINTS[0], battle.OFFENSE_POINTS[0.25])

    def test_immunity_defense_best(self):
        self.assertGreater(battle.DEFENSE_POINTS[0], battle.DEFENSE_POINTS[0.25])

    def test_rank_counters_top20_and_sorted(self):
        # Gengar (Ghost/Poison, #94) as opponent.
        gengar = DATASET.get(94)
        pool = DATASET.order
        ranked = battle.rank_counters(DATASET, [gengar["types"]], ["Gengar"], pool, limit=20)
        self.assertLessEqual(len(ranked), 20)
        scores = [r["score"] for r in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_rank_counters_ownership_filter(self):
        gengar = DATASET.get(94)
        owned_pool = [1, 4, 7, 25]  # Bulbasaur, Charmander, Squirtle, Pikachu
        ranked = battle.rank_counters(DATASET, [gengar["types"]], ["Gengar"], owned_pool, limit=20)
        self.assertEqual({r["pokedex_number"] for r in ranked}, set(owned_pool))

    def test_generate_team_distinct_members(self):
        gengar = DATASET.get(94)
        result = battle.generate_team(DATASET, DATASET.order, opponent_type_lists=[gengar["types"]], size=6)
        self.assertEqual(len(result["members"]), len(set(result["members"])))
        self.assertEqual(len(result["members"]), 6)
        self.assertFalse(result["shortfall"])

    def test_generate_team_strict_ownership_pool(self):
        owned_pool = [1, 4, 7]  # only 3 eligible Pokemon
        result = battle.generate_team(DATASET, owned_pool, opponent_type_lists=None, size=6)
        self.assertEqual(set(result["members"]), set(owned_pool))
        self.assertTrue(result["shortfall"])
        self.assertEqual(len(result["members"]), 3)

    def test_generate_team_never_exceeds_pool_even_unrestricted(self):
        result = battle.generate_team(DATASET, DATASET.order, opponent_type_lists=None, size=6)
        self.assertEqual(len(result["members"]), 6)
        for n in result["members"]:
            self.assertIn(n, DATASET.order)

    def test_generate_team_deterministic(self):
        gengar = DATASET.get(94)
        r1 = battle.generate_team(DATASET, DATASET.order, opponent_type_lists=[gengar["types"]], size=6)
        r2 = battle.generate_team(DATASET, DATASET.order, opponent_type_lists=[gengar["types"]], size=6)
        self.assertEqual(r1["members"], r2["members"])

    def test_analyze_team_shared_weakness_detected(self):
        # Two Grass/Poison-ish types both weak to Flying/Psychic/Fire/Ice would share weaknesses;
        # use Bulbasaur(1) and Oddish-line Bellsprout(69, Grass/Poison) as a concrete dual-grass-poison pair.
        bulbasaur = DATASET.get(1)
        bellsprout = DATASET.get(69)
        self.assertEqual(bulbasaur["types"], ["Grass", "Poison"])
        self.assertEqual(bellsprout["types"], ["Grass", "Poison"])
        analysis = battle.analyze_team(DATASET, [1, 69])
        self.assertIn("Fire", analysis["shared_weaknesses"])
        self.assertEqual(analysis["shared_weaknesses"]["Fire"], 2)

    def test_analyze_team_offense_coverage_complete(self):
        analysis = battle.analyze_team(DATASET, [1])
        self.assertEqual(len(analysis["offense_coverage"]), 18)

    def test_suggest_replacements_excludes_owned(self):
        gengar = DATASET.get(94)
        owned_set = {1, 4, 7}
        suggestions = battle.suggest_replacements(
            DATASET, [1, 4, 7], [gengar["types"]], ["Gengar"], owned_set
        )
        for s in suggestions:
            self.assertNotIn(s["suggestion"]["pokedex_number"], owned_set)

    def test_fmt_mult(self):
        self.assertEqual(battle.fmt_mult(4), "4x")
        self.assertEqual(battle.fmt_mult(0.5), "0.5x")
        self.assertEqual(battle.fmt_mult(0), "0x")

    def test_stat_bonus_weight_cannot_outrank_type_score(self):
        # By construction, the scaled stat bonus's full range must stay
        # strictly below 1/MAX_TEAM_SIZE -- the smallest possible gap
        # between two distinct average type_scores against an up-to-6-
        # member opposing team. If this ever regresses, stats could flip
        # a ranking that type effectiveness alone would have decided.
        max_possible_stat_contribution = battle.STAT_BONUS_WEIGHT * 1.0
        smallest_possible_type_score_gap = 1 / battle.MAX_TEAM_SIZE
        self.assertLess(max_possible_stat_contribution, smallest_possible_type_score_gap)

    def test_better_type_score_beats_much_higher_stat_bonus_against_a_team(self):
        # Regression test for a real bug: final_score used to be
        # avg_type_score + raw stat_bonus (stat_bonus up to ~1.0), which
        # could swamp an avg_type_score gap as small as 1/6 against a
        # 6-member team and let a far worse type matchup outrank a better
        # one purely on stats. Build two fake candidates where that would
        # have happened under the old unscaled formula, and confirm the
        # better type matchup still wins now.
        class FakeDataset:
            def __init__(self, pokes, readiness):
                self._pokes = pokes
                self._readiness = readiness

            def get(self, n):
                return self._pokes[n]

            def battle_readiness(self, n):
                return self._readiness[n]

        # Candidate 1 is pure Fire, candidate 2 is pure Normal. Against a
        # 6-member opposing team of five Rock-types and one Grass-type,
        # Normal's average type_score comes out higher than Fire's.
        pokes = {
            1: {"pokedex_number": 1, "name": "WorseTypeMaxStat", "types": ["Fire"]},
            2: {"pokedex_number": 2, "name": "BetterTypeZeroStat", "types": ["Normal"]},
        }
        # Candidate 1 has the maximum possible raw stat bonus; candidate 2
        # has none at all -- under the old formula this was enough to flip
        # the ranking despite candidate 2's better type matchup.
        readiness = {1: 1.0, 2: 0.0}
        fake_dataset = FakeDataset(pokes, readiness)

        opponent_type_lists = [["Rock"]] * 5 + [["Grass"]]
        opponent_names = [f"Opponent{i}" for i in range(6)]

        result1 = battle.score_candidate(fake_dataset, 1, opponent_type_lists)
        result2 = battle.score_candidate(fake_dataset, 2, opponent_type_lists)
        self.assertLess(result1["type_score"], result2["type_score"])  # sanity check on the fixture

        ranked = battle.rank_counters(fake_dataset, opponent_type_lists, opponent_names, [1, 2], limit=2)
        self.assertEqual(ranked[0]["pokedex_number"], 2)
        self.assertEqual(ranked[1]["pokedex_number"], 1)


if __name__ == "__main__":
    unittest.main()
