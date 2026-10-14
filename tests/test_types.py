import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import types as t


class TestTypeChart(unittest.TestCase):
    def test_all_types_present(self):
        self.assertEqual(len(t.ALL_TYPES), 18)

    def test_immunities(self):
        self.assertEqual(t.single_multiplier("Normal", "Ghost"), 0)
        self.assertEqual(t.single_multiplier("Ghost", "Normal"), 0)
        self.assertEqual(t.single_multiplier("Electric", "Ground"), 0)
        self.assertEqual(t.single_multiplier("Dragon", "Fairy"), 0)
        self.assertEqual(t.single_multiplier("Psychic", "Dark"), 0)
        self.assertEqual(t.single_multiplier("Poison", "Steel"), 0)
        self.assertEqual(t.single_multiplier("Ground", "Flying"), 0)
        self.assertEqual(t.single_multiplier("Fighting", "Ghost"), 0)

    def test_neutral_default(self):
        self.assertEqual(t.single_multiplier("Normal", "Grass"), 1)
        self.assertEqual(t.single_multiplier("Water", "Steel"), 1)

    def test_super_effective(self):
        self.assertEqual(t.single_multiplier("Water", "Fire"), 2)
        self.assertEqual(t.single_multiplier("Grass", "Water"), 2)
        self.assertEqual(t.single_multiplier("Fire", "Grass"), 2)

    def test_not_very_effective(self):
        self.assertEqual(t.single_multiplier("Fire", "Water"), 0.5)
        self.assertEqual(t.single_multiplier("Water", "Grass"), 0.5)

    def test_dual_type_quad_weakness(self):
        # A concrete quad-weakness case: Ice attacking Dragon/Flying
        # (e.g. Salamence-like) = 2 * 2 = 4x.
        self.assertEqual(t.dual_multiplier("Ice", ["Dragon", "Flying"]), 4)

    def test_dual_type_quad_resist(self):
        # Fighting attacking Ghost/Psychic: 0 (Ghost immune) * 0.5 (Psychic resists) = 0
        self.assertEqual(t.dual_multiplier("Fighting", ["Ghost", "Psychic"]), 0)

    def test_dual_type_immunity_dominates(self):
        # Ground attacking Water/Flying (e.g. Gyarados-like): Ground is neutral (1x)
        # against Water alone, but 0x vs Flying -> combined must be exactly 0.
        self.assertEqual(t.dual_multiplier("Ground", ["Water", "Flying"]), 0)

    def test_single_type_defender(self):
        # No second type should behave as pure neutral multiplier, not 1 extra factor.
        self.assertEqual(t.dual_multiplier("Water", ["Fire", None]), 2)
        self.assertEqual(t.dual_multiplier("Water", ["Fire", ""]), 2)

    def test_defensive_profile_complete(self):
        profile = t.defensive_profile(["Grass", "Poison"])
        self.assertEqual(len(profile), 18)
        # Bulbasaur-like typing: 4x weak to Psychic? Actually Grass/Poison -> Psychic 2x (poison weak) * 1 (grass neutral) = 2
        self.assertEqual(profile["Psychic"], 2)
        self.assertEqual(profile["Fire"], 2)  # fire 2x grass * neutral poison = 2... fire vs poison is neutral
        self.assertEqual(profile["Water"], 0.5)  # water resisted by grass(0.5)*neutral poison(1)

    def test_best_offensive_multiplier_picks_better_type(self):
        # A Water/Flying attacker vs a pure Ground defender: Water is 2x, Flying is neutral (1x)
        # -> the attacker's best available STAB option is 2x.
        self.assertEqual(t.best_offensive_multiplier(["Water", "Flying"], ["Ground"]), 2)

    def test_chart_values_are_only_known_multipliers(self):
        allowed = {0, 0.25, 0.5, 1, 2, 4}
        for atk, row in t.CHART.items():
            for defend, mult in row.items():
                self.assertIn(mult, allowed)


if __name__ == "__main__":
    unittest.main()
