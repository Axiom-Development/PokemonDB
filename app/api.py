"""JSON API: routing + handlers, decoupled from the HTTP server transport
so the handlers can be unit tested directly (see tests/test_api.py)."""

import re
import time

from . import auth
from . import battle
from . import types as type_engine

SESSION_COOKIE = "pdb_session"
MAX_TEAM_SIZE = 6


class ApiError(Exception):
    def __init__(self, status, message, field=None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.field = field


class Context:
    def __init__(self, store, dataset, json_body, query, user):
        self.store = store
        self.dataset = dataset
        self.json = json_body or {}
        self.query = query or {}
        self.user = user
        self.params = {}


def require_user(ctx):
    if ctx.user is None:
        raise ApiError(401, "You need to sign in first.")
    return ctx.user


def public_pokemon(p, owned_set=None):
    out = dict(p)
    if owned_set is not None:
        out["owned"] = p["pokedex_number"] in owned_set
    return out


def _int_or(value, default):
    """Coerces a JSON field to int, falling back to `default` for anything
    that isn't cleanly convertible (missing, null, wrong type, non-numeric
    string) instead of letting int() raise."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


TEAM_MODES = ("manual", "owned")


def _clean_team_name(raw, default=None):
    """Validates an incoming team name. Returns `default` for an absent
    field; raises ApiError for a present-but-wrong-typed value so a bad
    request fails loudly instead of corrupting data or crashing on the
    SQLite bind."""
    if raw is None:
        return default
    if not isinstance(raw, str):
        raise ApiError(400, "name must be text.", field="name")
    cleaned = raw.strip()
    return cleaned or default


def _clean_team_mode(raw, default=None):
    if raw is None:
        return default
    if not isinstance(raw, str) or raw not in TEAM_MODES:
        raise ApiError(400, "mode must be 'manual' or 'owned'.", field="mode")
    return raw


# ---------------------------------------------------------------- pokemon --

def h_list_pokemon(ctx):
    owned = set(ctx.store.get_collection(ctx.user["id"])) if ctx.user else None
    return 200, {"pokemon": [public_pokemon(p, owned) for p in ctx.dataset.all()]}


def h_meta(ctx):
    return 200, {
        "types": type_engine.ALL_TYPES,
        "generations": ctx.dataset.generations,
        "total": len(ctx.dataset.order),
    }


def h_get_pokemon(ctx):
    num = int(ctx.params["num"])
    p = ctx.dataset.get(num)
    if p is None:
        raise ApiError(404, "No Pokemon with that number.")
    owned = set(ctx.store.get_collection(ctx.user["id"])) if ctx.user else None
    return 200, {"pokemon": public_pokemon(p, owned)}


def h_matchup(ctx):
    num = int(ctx.params["num"])
    profile = ctx.dataset.matchup(num)
    if profile is None:
        raise ApiError(404, "No Pokemon with that number.")
    buckets = {}
    for t, mult in profile.items():
        key = battle.fmt_mult(mult)[:-1]  # drop the trailing "x" -> canonical string key
        buckets.setdefault(key, []).append(t)
    return 200, {"pokedex_number": num, "profile": profile, "buckets": buckets}


# ------------------------------------------------------------------- auth --

def h_register(ctx):
    username = ctx.json.get("username")
    if isinstance(username, str):
        username = username.strip()
    password = ctx.json.get("password")
    err = auth.validate_username(username)
    if err:
        raise ApiError(400, err, field="username")
    err = auth.validate_password(password)
    if err:
        raise ApiError(400, err, field="password")
    if ctx.store.get_user_by_username(username):
        raise ApiError(400, "That username is already taken.", field="username")

    salt_hex, hash_hex = auth.hash_password(password)
    user_id = ctx.store.create_user(username, salt_hex, hash_hex)
    token = _start_session(ctx, user_id)
    return 201, {"user": {"id": user_id, "username": username}}, token


def h_login(ctx):
    username = ctx.json.get("username")
    if isinstance(username, str):
        username = username.strip()
    password = ctx.json.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        raise ApiError(401, "Incorrect username or password.")
    user = ctx.store.get_user_by_username(username)
    if user is None or not auth.verify_password(password, user["salt"], user["password_hash"]):
        raise ApiError(401, "Incorrect username or password.")
    token = _start_session(ctx, user["id"])
    return 200, {"user": {"id": user["id"], "username": user["username"]}}, token


def _start_session(ctx, user_id):
    token = auth.new_session_token()
    expires_at = time.time() + auth.SESSION_LIFETIME_SECONDS
    ctx.store.create_session(token, user_id, expires_at)
    return token


def h_logout(ctx, session_token=None):
    if session_token:
        ctx.store.delete_session(session_token)
    return 200, {"ok": True}, ""


def h_me(ctx):
    if ctx.user is None:
        raise ApiError(401, "Not signed in.")
    return 200, {"user": {"id": ctx.user["id"], "username": ctx.user["username"]}}


# ------------------------------------------------------------ collection --

def h_get_collection(ctx):
    require_user(ctx)
    numbers = ctx.store.get_collection(ctx.user["id"])
    pokes = [ctx.dataset.get(n) for n in numbers if ctx.dataset.exists(n)]
    return 200, {"pokemon": [public_pokemon(p, set(numbers)) for p in pokes]}


def h_add_collection(ctx):
    require_user(ctx)
    num = ctx.json.get("pokedex_number")
    if not isinstance(num, int) or not ctx.dataset.exists(num):
        raise ApiError(400, "Unknown Pokemon number.")
    ctx.store.add_to_collection(ctx.user["id"], num)
    return 200, {"ok": True}


def h_remove_collection(ctx):
    require_user(ctx)
    num = int(ctx.params["num"])
    ctx.store.remove_from_collection(ctx.user["id"], num)
    return 200, {"ok": True}


# ------------------------------------------------------------------ teams --

def _validate_members(ctx, members):
    if not isinstance(members, list) or len(members) > MAX_TEAM_SIZE:
        raise ApiError(400, f"A team can have at most {MAX_TEAM_SIZE} Pokemon.")
    seen = set()
    for n in members:
        if not isinstance(n, int) or not ctx.dataset.exists(n):
            raise ApiError(400, f"Unknown Pokemon number: {n!r}")
        if n in seen:
            raise ApiError(400, "A team can't include the same Pokemon twice.")
        seen.add(n)
    return members


def _team_view(ctx, team):
    owned = set(ctx.store.get_collection(ctx.user["id"]))
    members = [public_pokemon(ctx.dataset.get(n), owned) for n in team["members"]]
    analysis = battle.analyze_team(ctx.dataset, team["members"]) if team["members"] else None
    return {
        "id": team["id"],
        "name": team["name"],
        "mode": team["mode"],
        "members": members,
        "analysis": analysis,
    }


def h_list_teams(ctx):
    require_user(ctx)
    teams = ctx.store.list_teams(ctx.user["id"])
    return 200, {"teams": [_team_view(ctx, t) for t in teams]}


def h_create_team(ctx):
    require_user(ctx)
    name = _clean_team_name(ctx.json.get("name"), default="Untitled team")
    mode = _clean_team_mode(ctx.json.get("mode"), default="manual")
    members = _validate_members(ctx, ctx.json.get("members") or [])
    if mode == "owned":
        owned = set(ctx.store.get_collection(ctx.user["id"]))
        not_owned = [n for n in members if n not in owned]
        if not_owned:
            raise ApiError(400, "An owned-mode team can only contain Pokemon in your collection.")
    team_id = ctx.store.create_team(ctx.user["id"], name, mode, members)
    team = ctx.store.get_team(ctx.user["id"], team_id)
    return 201, {"team": _team_view(ctx, team)}


def h_update_team(ctx):
    require_user(ctx)
    team_id = int(ctx.params["id"])
    existing = ctx.store.get_team(ctx.user["id"], team_id)
    if existing is None:
        raise ApiError(404, "Team not found.")
    name = _clean_team_name(ctx.json.get("name"), default=existing["name"])
    mode = _clean_team_mode(ctx.json.get("mode"), default=None)
    members = ctx.json.get("members")
    if members is not None:
        members = _validate_members(ctx, members)
        effective_mode = mode if mode is not None else existing["mode"]
        if effective_mode == "owned":
            owned = set(ctx.store.get_collection(ctx.user["id"]))
            not_owned = [n for n in members if n not in owned]
            if not_owned:
                raise ApiError(400, "An owned-mode team can only contain Pokemon in your collection.")
    team = ctx.store.update_team(ctx.user["id"], team_id, name=name, mode=mode, members=members)
    return 200, {"team": _team_view(ctx, team)}


def h_delete_team(ctx):
    require_user(ctx)
    team_id = int(ctx.params["id"])
    ok = ctx.store.delete_team(ctx.user["id"], team_id)
    if not ok:
        raise ApiError(404, "Team not found.")
    return 200, {"ok": True}


def h_analyze_team(ctx):
    members = _validate_members(ctx, ctx.json.get("members") or [])
    analysis = battle.analyze_team(ctx.dataset, members) if members else None
    return 200, {"analysis": analysis}


def h_generate_team(ctx):
    require_user(ctx)
    mode = ctx.json.get("mode")
    size = max(1, min(_int_or(ctx.json.get("size"), MAX_TEAM_SIZE), MAX_TEAM_SIZE))
    if mode not in ("owned", "unrestricted"):
        raise ApiError(400, "mode must be 'owned' or 'unrestricted'.")

    owned = ctx.store.get_collection(ctx.user["id"])
    if mode == "owned":
        pool = owned
    else:
        pool = ctx.dataset.order

    if mode == "owned" and not pool:
        return 200, {
            "members": [],
            "shortfall": True,
            "message": "Your collection is empty, so there's nothing to build an owned team from yet. Add Pokemon from the Pokedex first.",
        }

    result = battle.generate_team(ctx.dataset, pool, opponent_type_lists=None, size=size)
    owned_set = set(owned)
    members = [public_pokemon(ctx.dataset.get(n), owned_set) for n in result["members"]]
    message = None
    if result["shortfall"]:
        message = (
            f"Your collection only has {len(pool)} eligible Pokemon, so this team has "
            f"{len(result['members'])} member(s) instead of {size}."
        )
    return 200, {
        "members": members,
        "shortfall": result["shortfall"],
        "message": message,
        "analysis": battle.analyze_team(ctx.dataset, result["members"]) if result["members"] else None,
    }


# ----------------------------------------------------------- battle planner --

def _resolve_opponent(ctx, opponent):
    if not isinstance(opponent, dict):
        raise ApiError(400, "opponent is required.")
    kind = opponent.get("mode")
    if kind == "single":
        num = opponent.get("pokedex_number")
        if not isinstance(num, int) or not ctx.dataset.exists(num):
            raise ApiError(400, "Pick a valid opposing Pokemon.")
        p = ctx.dataset.get(num)
        return [p["types"]], [p["name"]]
    elif kind == "team":
        numbers = opponent.get("pokedex_numbers")
        if not isinstance(numbers, list) or not numbers or len(numbers) > MAX_TEAM_SIZE:
            raise ApiError(400, f"An opposing team needs 1-{MAX_TEAM_SIZE} Pokemon.")
        type_lists, names = [], []
        for n in numbers:
            if not isinstance(n, int) or not ctx.dataset.exists(n):
                raise ApiError(400, f"Unknown opposing Pokemon number: {n!r}")
            p = ctx.dataset.get(n)
            type_lists.append(p["types"])
            names.append(p["name"])
        return type_lists, names
    raise ApiError(400, "opponent.mode must be 'single' or 'team'.")


def h_battle_rank(ctx):
    opponent_types, opponent_names = _resolve_opponent(ctx, ctx.json.get("opponent"))
    filt = ctx.json.get("filter", "all")
    limit = max(1, min(_int_or(ctx.json.get("limit"), 20), 20))

    owned_set = set(ctx.store.get_collection(ctx.user["id"])) if ctx.user else set()
    if filt == "owned":
        if ctx.user is None:
            raise ApiError(401, "Sign in to filter by your collection.")
        pool = [n for n in ctx.dataset.order if n in owned_set]
    elif filt == "not_owned":
        pool = [n for n in ctx.dataset.order if n not in owned_set] if ctx.user else list(ctx.dataset.order)
    else:
        pool = list(ctx.dataset.order)

    # exclude the opponent(s) themselves from the ranked field when single
    opponent_numbers = set()
    opp_json = ctx.json.get("opponent") or {}
    if opp_json.get("mode") == "single":
        opponent_numbers.add(opp_json.get("pokedex_number"))
    else:
        opponent_numbers.update(opp_json.get("pokedex_numbers") or [])
    pool = [n for n in pool if n not in opponent_numbers]

    ranked = battle.rank_counters(ctx.dataset, opponent_types, opponent_names, pool, limit=limit)
    for r in ranked:
        r["owned"] = r["pokedex_number"] in owned_set
    return 200, {"opponent_names": opponent_names, "results": ranked}


def h_battle_generate(ctx):
    require_user(ctx)
    opponent_types, opponent_names = _resolve_opponent(ctx, ctx.json.get("opponent"))
    mode = ctx.json.get("mode")
    if mode not in ("owned", "unrestricted"):
        raise ApiError(400, "mode must be 'owned' or 'unrestricted'.")
    size = max(1, min(_int_or(ctx.json.get("size"), MAX_TEAM_SIZE), MAX_TEAM_SIZE))

    owned = ctx.store.get_collection(ctx.user["id"])
    opponent_numbers = set()
    opp_json = ctx.json.get("opponent") or {}
    if opp_json.get("mode") == "single":
        opponent_numbers.add(opp_json.get("pokedex_number"))
    else:
        opponent_numbers.update(opp_json.get("pokedex_numbers") or [])

    if mode == "owned":
        pool = [n for n in owned if n not in opponent_numbers]
        if not pool:
            return 200, {
                "members": [], "shortfall": True,
                "message": "Your collection is empty, so there's nothing to build an owned team from yet.",
                "opponent_names": opponent_names,
            }
    else:
        pool = [n for n in ctx.dataset.order if n not in opponent_numbers]

    result = battle.generate_team(ctx.dataset, pool, opponent_type_lists=opponent_types, size=size)
    owned_set = set(owned)
    members = [public_pokemon(ctx.dataset.get(n), owned_set) for n in result["members"]]
    message = None
    if result["shortfall"]:
        message = (
            f"Your collection only has {len(pool)} eligible Pokemon (excluding the opponent), "
            f"so this team has {len(result['members'])} member(s) instead of {size}."
        )
    scored = [battle.score_candidate(ctx.dataset, n, opponent_types) for n in result["members"]]
    explanations = {s["pokedex_number"]: battle.explain(s, opponent_names) for s in scored}
    replacements = []
    if mode == "owned" and result["members"]:
        replacements = battle.suggest_replacements(
            ctx.dataset, result["members"], opponent_types, opponent_names, owned_set
        )
    return 200, {
        "members": members,
        "shortfall": result["shortfall"],
        "message": message,
        "opponent_names": opponent_names,
        "explanations": explanations,
        "analysis": battle.analyze_team(ctx.dataset, result["members"]) if result["members"] else None,
        "replacement_suggestions": replacements,
    }


def h_battle_replacements(ctx):
    require_user(ctx)
    opponent_types, opponent_names = _resolve_opponent(ctx, ctx.json.get("opponent"))
    members = ctx.json.get("team") or []
    members = _validate_members(ctx, members)
    owned_set = set(ctx.store.get_collection(ctx.user["id"]))
    not_owned = [n for n in members if n not in owned_set]
    if not_owned:
        raise ApiError(400, "Replacement suggestions need an owned team -- these Pokemon aren't in your collection.")
    if not members:
        raise ApiError(400, "Add at least one team member first.")
    suggestions = battle.suggest_replacements(ctx.dataset, members, opponent_types, opponent_names, owned_set)
    return 200, {"opponent_names": opponent_names, "suggestions": suggestions}


# --------------------------------------------------------------- routing --

ROUTE_TABLE = [
    ("GET", r"^/api/meta$", h_meta),
    ("GET", r"^/api/pokemon$", h_list_pokemon),
    ("GET", r"^/api/pokemon/(?P<num>\d+)$", h_get_pokemon),
    ("GET", r"^/api/pokemon/(?P<num>\d+)/matchup$", h_matchup),

    ("POST", r"^/api/register$", h_register),
    ("POST", r"^/api/login$", h_login),
    ("POST", r"^/api/logout$", h_logout),
    ("GET", r"^/api/me$", h_me),

    ("GET", r"^/api/collection$", h_get_collection),
    ("POST", r"^/api/collection$", h_add_collection),
    ("DELETE", r"^/api/collection/(?P<num>\d+)$", h_remove_collection),

    ("GET", r"^/api/teams$", h_list_teams),
    ("POST", r"^/api/teams$", h_create_team),
    ("PUT", r"^/api/teams/(?P<id>\d+)$", h_update_team),
    ("DELETE", r"^/api/teams/(?P<id>\d+)$", h_delete_team),
    ("POST", r"^/api/teams/analyze$", h_analyze_team),
    ("POST", r"^/api/teams/generate$", h_generate_team),

    ("POST", r"^/api/battle/rank$", h_battle_rank),
    ("POST", r"^/api/battle/generate$", h_battle_generate),
    ("POST", r"^/api/battle/replacements$", h_battle_replacements),
]

_COMPILED = [(method, re.compile(pattern), handler) for method, pattern, handler in ROUTE_TABLE]


def resolve_route(method, path):
    for m, pattern, handler in _COMPILED:
        if m != method:
            continue
        match = pattern.match(path)
        if match:
            return handler, match.groupdict()
    return None, None


def dispatch(method, path, query, json_body, store, dataset, user, session_token=None):
    """Returns (status, response_dict, new_session_token_or_None)."""
    handler, params = resolve_route(method, path)
    if handler is None:
        return 404, {"error": "Not found."}, None

    ctx = Context(store, dataset, json_body, query, user)
    ctx.params = params or {}
    try:
        if handler is h_logout:
            result = handler(ctx, session_token=session_token)
        else:
            result = handler(ctx)
    except ApiError as e:
        return e.status, {"error": e.message, "field": e.field}, None

    if len(result) == 3:
        status, body, token = result
    else:
        status, body = result
        token = None
    return status, body, token
