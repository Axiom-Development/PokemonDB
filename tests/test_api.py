import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import api
from app.data import DATASET
from app.db import Store


def register(store, username, password="password123"):
    status, body, token = api.dispatch(
        "POST", "/api/register", {}, {"username": username, "password": password},
        store, DATASET, None,
    )
    assert status == 201, body
    user = store.get_session_user(token)
    return user, token


class TestAccounts(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")

    def tearDown(self):
        self.store.conn.close()

    def test_register_and_login(self):
        user, _ = register(self.store, "ash")
        self.assertEqual(user["username"], "ash")
        status, body, token = api.dispatch(
            "POST", "/api/login", {}, {"username": "ash", "password": "password123"},
            self.store, DATASET, None,
        )
        self.assertEqual(status, 200)
        self.assertIsNotNone(token)

    def test_login_wrong_password_rejected(self):
        register(self.store, "misty")
        status, body, token = api.dispatch(
            "POST", "/api/login", {}, {"username": "misty", "password": "wrong-pass"},
            self.store, DATASET, None,
        )
        self.assertEqual(status, 401)
        self.assertIsNone(token)

    def test_duplicate_username_rejected(self):
        register(self.store, "brock")
        status, body, _ = api.dispatch(
            "POST", "/api/register", {}, {"username": "brock", "password": "password123"},
            self.store, DATASET, None,
        )
        self.assertEqual(status, 400)

    def test_password_too_short_rejected(self):
        status, body, _ = api.dispatch(
            "POST", "/api/register", {}, {"username": "shorty", "password": "abc"},
            self.store, DATASET, None,
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["field"], "password")

    def test_me_requires_session(self):
        status, body, _ = api.dispatch("GET", "/api/me", {}, {}, self.store, DATASET, None)
        self.assertEqual(status, 401)

    def test_register_empty_body_rejected_cleanly(self):
        # Simulates a request with no fields at all (e.g. an empty JSON
        # object body) -- must not crash trying to .strip()/.encode() a
        # missing value.
        status, body, token = api.dispatch("POST", "/api/register", {}, {}, self.store, DATASET, None)
        self.assertEqual(status, 400)
        self.assertIsNone(token)

    def test_register_rejects_non_string_username_without_crashing(self):
        status, body, _ = api.dispatch(
            "POST", "/api/register", {}, {"username": 12345, "password": "password123"},
            self.store, DATASET, None,
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["field"], "username")

    def test_register_rejects_non_string_password_without_crashing(self):
        status, body, _ = api.dispatch(
            "POST", "/api/register", {}, {"username": "validname", "password": ["a", "list"]},
            self.store, DATASET, None,
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["field"], "password")

    def test_register_rejects_boolean_password_without_crashing(self):
        # bool is a subclass of int in Python -- make sure True/False don't
        # sneak past isinstance(password, str) checks anywhere upstream.
        status, body, _ = api.dispatch(
            "POST", "/api/register", {}, {"username": "validname2", "password": True},
            self.store, DATASET, None,
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["field"], "password")

    def test_login_rejects_non_string_username_without_crashing(self):
        status, body, token = api.dispatch(
            "POST", "/api/login", {}, {"username": {"nested": "object"}, "password": "password123"},
            self.store, DATASET, None,
        )
        self.assertEqual(status, 401)
        self.assertIsNone(token)

    def test_login_rejects_missing_password_without_crashing(self):
        register(self.store, "login_type_test")
        status, body, token = api.dispatch(
            "POST", "/api/login", {}, {"username": "login_type_test"},
            self.store, DATASET, None,
        )
        self.assertEqual(status, 401)
        self.assertIsNone(token)


class TestMalformedTeamInput(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.user, _ = register(self.store, "malformed_input_tester")

    def tearDown(self):
        self.store.conn.close()

    def test_create_team_rejects_non_string_name(self):
        status, body, _ = api.dispatch(
            "POST", "/api/teams", {}, {"name": ["not", "a", "string"], "mode": "manual", "members": [1]},
            self.store, DATASET, self.user,
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["field"], "name")

    def test_create_team_rejects_invalid_mode_string(self):
        status, body, _ = api.dispatch(
            "POST", "/api/teams", {}, {"name": "Team", "mode": "not-a-real-mode", "members": [1]},
            self.store, DATASET, self.user,
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["field"], "mode")

    def test_create_team_rejects_non_string_mode(self):
        status, body, _ = api.dispatch(
            "POST", "/api/teams", {}, {"name": "Team", "mode": 42, "members": [1]},
            self.store, DATASET, self.user,
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["field"], "mode")

    def test_update_team_rejects_non_string_name(self):
        _, created, _ = api.dispatch(
            "POST", "/api/teams", {}, {"name": "Original", "mode": "manual", "members": [1]},
            self.store, DATASET, self.user,
        )
        team_id = created["team"]["id"]
        status, body, _ = api.dispatch(
            "PUT", f"/api/teams/{team_id}", {}, {"name": 999},
            self.store, DATASET, self.user,
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["field"], "name")

    def test_generate_team_bogus_size_falls_back_gracefully(self):
        status, body, _ = api.dispatch(
            "POST", "/api/teams/generate", {}, {"mode": "unrestricted", "size": "not-a-number"},
            self.store, DATASET, self.user,
        )
        self.assertEqual(status, 200)
        self.assertLessEqual(len(body["members"]), 6)

    def test_battle_rank_bogus_limit_falls_back_gracefully(self):
        status, body, _ = api.dispatch(
            "POST", "/api/battle/rank", {},
            {"opponent": {"mode": "single", "pokedex_number": 94}, "filter": "all", "limit": "not-a-number"},
            self.store, DATASET, self.user,
        )
        self.assertEqual(status, 200)
        self.assertLessEqual(len(body["results"]), 20)

    def test_battle_rank_opponent_numbers_not_a_list_rejected(self):
        status, body, _ = api.dispatch(
            "POST", "/api/battle/rank", {},
            {"opponent": {"mode": "team", "pokedex_numbers": 94}, "filter": "all", "limit": 5},
            self.store, DATASET, self.user,
        )
        self.assertEqual(status, 400)


class TestCollectionIsolation(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.ash, _ = register(self.store, "ash2")
        self.misty, _ = register(self.store, "misty2")

    def tearDown(self):
        self.store.conn.close()

    def test_collection_is_per_user(self):
        api.dispatch("POST", "/api/collection", {}, {"pokedex_number": 1}, self.store, DATASET, self.ash)
        api.dispatch("POST", "/api/collection", {}, {"pokedex_number": 7}, self.store, DATASET, self.misty)

        _, ash_body, _ = api.dispatch("GET", "/api/collection", {}, {}, self.store, DATASET, self.ash)
        _, misty_body, _ = api.dispatch("GET", "/api/collection", {}, {}, self.store, DATASET, self.misty)

        self.assertEqual([p["pokedex_number"] for p in ash_body["pokemon"]], [1])
        self.assertEqual([p["pokedex_number"] for p in misty_body["pokemon"]], [7])

    def test_collection_requires_login(self):
        status, _, _ = api.dispatch("GET", "/api/collection", {}, {}, self.store, DATASET, None)
        self.assertEqual(status, 401)

    def test_remove_from_collection(self):
        api.dispatch("POST", "/api/collection", {}, {"pokedex_number": 1}, self.store, DATASET, self.ash)
        api.dispatch("DELETE", "/api/collection/1", {}, {}, self.store, DATASET, self.ash)
        _, body, _ = api.dispatch("GET", "/api/collection", {}, {}, self.store, DATASET, self.ash)
        self.assertEqual(body["pokemon"], [])


class TestTeamsIsolationAndOwnership(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.ash, _ = register(self.store, "ash3")
        self.misty, _ = register(self.store, "misty3")
        for n in (1, 4, 7):
            api.dispatch("POST", "/api/collection", {}, {"pokedex_number": n}, self.store, DATASET, self.ash)

    def tearDown(self):
        self.store.conn.close()

    def test_owned_mode_rejects_unowned_members(self):
        status, body, _ = api.dispatch(
            "POST", "/api/teams", {}, {"name": "Starters", "mode": "owned", "members": [1, 4, 25]},
            self.store, DATASET, self.ash,
        )
        self.assertEqual(status, 400)

    def test_owned_mode_accepts_owned_members(self):
        status, body, _ = api.dispatch(
            "POST", "/api/teams", {}, {"name": "Starters", "mode": "owned", "members": [1, 4, 7]},
            self.store, DATASET, self.ash,
        )
        self.assertEqual(status, 201)

    def test_manual_mode_allows_unowned(self):
        status, body, _ = api.dispatch(
            "POST", "/api/teams", {}, {"name": "Dream team", "mode": "manual", "members": [1, 150]},
            self.store, DATASET, self.ash,
        )
        self.assertEqual(status, 201)

    def test_team_rejects_duplicate_members(self):
        status, body, _ = api.dispatch(
            "POST", "/api/teams", {}, {"name": "Clones", "mode": "manual", "members": [1, 1]},
            self.store, DATASET, self.ash,
        )
        self.assertEqual(status, 400)

    def test_team_rejects_more_than_six(self):
        status, body, _ = api.dispatch(
            "POST", "/api/teams", {}, {"name": "Too many", "mode": "manual", "members": [1, 2, 3, 4, 5, 6, 7]},
            self.store, DATASET, self.ash,
        )
        self.assertEqual(status, 400)

    def test_teams_are_per_user(self):
        api.dispatch("POST", "/api/teams", {}, {"name": "Ash's team", "mode": "manual", "members": [1]}, self.store, DATASET, self.ash)
        _, ash_teams, _ = api.dispatch("GET", "/api/teams", {}, {}, self.store, DATASET, self.ash)
        _, misty_teams, _ = api.dispatch("GET", "/api/teams", {}, {}, self.store, DATASET, self.misty)
        self.assertEqual(len(ash_teams["teams"]), 1)
        self.assertEqual(len(misty_teams["teams"]), 0)

    def test_cannot_delete_another_users_team(self):
        _, body, _ = api.dispatch("POST", "/api/teams", {}, {"name": "Secret", "mode": "manual", "members": [1]}, self.store, DATASET, self.ash)
        team_id = body["team"]["id"]
        status, _, _ = api.dispatch("DELETE", f"/api/teams/{team_id}", {}, {}, self.store, DATASET, self.misty)
        self.assertEqual(status, 404)


class TestBattleApi(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.user, _ = register(self.store, "trainer")
        for n in (1, 4, 7, 25):
            api.dispatch("POST", "/api/collection", {}, {"pokedex_number": n}, self.store, DATASET, self.user)

    def tearDown(self):
        self.store.conn.close()

    def test_rank_respects_limit_of_20(self):
        status, body, _ = api.dispatch(
            "POST", "/api/battle/rank", {}, {"opponent": {"mode": "single", "pokedex_number": 94}, "filter": "all", "limit": 20},
            self.store, DATASET, self.user,
        )
        self.assertEqual(status, 200)
        self.assertLessEqual(len(body["results"]), 20)

    def test_rank_owned_filter_matches_collection(self):
        status, body, _ = api.dispatch(
            "POST", "/api/battle/rank", {}, {"opponent": {"mode": "single", "pokedex_number": 94}, "filter": "owned", "limit": 20},
            self.store, DATASET, self.user,
        )
        numbers = {r["pokedex_number"] for r in body["results"]}
        self.assertEqual(numbers, {1, 4, 7, 25})
        for r in body["results"]:
            self.assertTrue(r["owned"])

    def test_rank_not_owned_filter_excludes_collection(self):
        status, body, _ = api.dispatch(
            "POST", "/api/battle/rank", {}, {"opponent": {"mode": "single", "pokedex_number": 94}, "filter": "not_owned", "limit": 20},
            self.store, DATASET, self.user,
        )
        numbers = {r["pokedex_number"] for r in body["results"]}
        self.assertTrue(numbers.isdisjoint({1, 4, 7, 25}))

    def test_generate_owned_team_uses_only_owned(self):
        status, body, _ = api.dispatch(
            "POST", "/api/battle/generate", {}, {"opponent": {"mode": "single", "pokedex_number": 94}, "mode": "owned", "size": 6},
            self.store, DATASET, self.user,
        )
        self.assertEqual(status, 200)
        numbers = [m["pokedex_number"] for m in body["members"]]
        self.assertTrue(set(numbers).issubset({1, 4, 7, 25}))
        self.assertTrue(body["shortfall"])  # only 4 eligible, asked for 6
        self.assertIn("message", body)
        self.assertIsNotNone(body["message"])

    def test_generate_unrestricted_can_use_unowned(self):
        status, body, _ = api.dispatch(
            "POST", "/api/battle/generate", {}, {"opponent": {"mode": "single", "pokedex_number": 94}, "mode": "unrestricted", "size": 6},
            self.store, DATASET, self.user,
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(body["members"]), 6)
        numbers = [m["pokedex_number"] for m in body["members"]]
        self.assertEqual(len(numbers), len(set(numbers)))

    def test_opponent_team_up_to_six(self):
        status, body, _ = api.dispatch(
            "POST", "/api/battle/rank", {},
            {"opponent": {"mode": "team", "pokedex_numbers": [94, 6, 9, 3, 65, 130]}, "filter": "all", "limit": 10},
            self.store, DATASET, self.user,
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(body["opponent_names"]), 6)

    def test_opponent_team_rejects_more_than_six(self):
        status, body, _ = api.dispatch(
            "POST", "/api/battle/rank", {},
            {"opponent": {"mode": "team", "pokedex_numbers": [1, 2, 3, 4, 5, 6, 7]}, "filter": "all", "limit": 10},
            self.store, DATASET, self.user,
        )
        self.assertEqual(status, 400)

    def test_replacements_require_fully_owned_team(self):
        status, body, _ = api.dispatch(
            "POST", "/api/battle/replacements", {},
            {"opponent": {"mode": "single", "pokedex_number": 94}, "team": [1, 150]},
            self.store, DATASET, self.user,
        )
        self.assertEqual(status, 400)

    def test_replacements_on_owned_team(self):
        status, body, _ = api.dispatch(
            "POST", "/api/battle/replacements", {},
            {"opponent": {"mode": "single", "pokedex_number": 94}, "team": [1, 4, 7, 25]},
            self.store, DATASET, self.user,
        )
        self.assertEqual(status, 200)
        for s in body["suggestions"]:
            self.assertNotIn(s["suggestion"]["pokedex_number"], {1, 4, 7, 25})


if __name__ == "__main__":
    unittest.main()
