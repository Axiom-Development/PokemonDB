# PokémonDB

A local web app for exploring the Pokédex, building a
personal collection, planning teams, and scouting type match-ups. Built
with a Python standard-library HTTP server, SQLite, and a buildless
HTML/CSS/JS frontend -- no npm install, no build step, no external
services.

## Running it

**Windows:** double-click `Start-PokemonDB.cmd`, or from a terminal:

```
python server.py
```

Then open **http://127.0.0.1:8800/** in a browser. Stop the server with
`Ctrl+C` (or close the launcher window).

The server binds to `127.0.0.1` only -- it is not reachable from other
devices on your network. All data lives in `runtime/pokemondb.sqlite3`,
created automatically on first run and ignored by git.

## What's implemented

- **Pokédex** -- all 1,025 species from `pokemon.csv`, with local artwork,
  instant name/number search, type and generation filters, sortable
  columns, and a specimen-sheet detail panel (base stats, height/weight,
  a full weakness/resistance breakdown by multiplier, and collection/team
  actions).
- **My collection** -- add or remove any Pokémon; collection membership is
  tied to your account and drives "owned" badges everywhere else in the
  app (Pokédex cards, team slots, battle planner results).
- **Team builder** -- up to six Pokémon per team, named and saved to your
  account, with add/remove/replace, an auto-build button (restricted to
  your collection or unrestricted), and a live coverage panel (offensive
  type coverage against all 18 types, shared weaknesses, average stats).
  Switching a team to "collection only" mode is blocked while it still
  contains an unowned member.
- **Battle planner** -- pick a single opponent or build an opposing team
  of up to six, then either rank up to the top 20 counters (with
  All / Owned / Not owned filters) or auto-generate a complementary team.
  Generated owned-mode teams draw only from your collection, show fewer
  than six members with an explicit message if your collection is too
  small, and come with separate, clearly-labelled suggestions for unowned
  Pokémon that would improve the team's weakest match-ups (including what
  they'd replace and the stat trade-offs). An unrestricted mode is
  available for pure planning, and any owned saved team can be checked
  against a chosen opponent for upgrade suggestions independent of
  generation.
- **Account** -- real local accounts: registration, login, logout,
  salted+hashed passwords, server-side session cookies. No fake
  localStorage "profiles."

Every Pokémon card, team slot, and battle result that can be unowned is
visibly flagged as such -- there's no silent mixing of owned and unowned
Pokémon in an "owned" context.

## Design

Built using Claude Code's **frontend-design** skill (`.claude/skills/frontend-design`),
which asks for a distinctive, subject-grounded visual identity rather than
generic dashboard defaults.

**Concept -- a trainer's field binder.** A dark "binder case" shell holds
light "index card" content: every Pokémon is rendered as a consistent
specimen card (number, art, name, type chips) reused across every screen,
like a catalogued field guide rather than a game UI skin.

- **Color** -- `#16231F` ink (shell/chrome), `#F2EEDE` parchment (content
  surfaces), `#3C6E52` moss (primary actions), `#C97F1F` amber (secondary
  actions, badges), `#B23A26` ember (danger/weakness). The 18 Pokémon
  types get their own custom, muted palette (`--t-fire`, `--t-water`, …)
  used only as small identifying dots and chip borders -- color is a
  wayfinding system, never decoration.
- **Type** -- *Big Shoulders* (condensed, display weight) for headings and
  catalog numbers, giving them a confident specimen-label identity;
  *IBM Plex Sans* for UI copy and body text; *IBM Plex Mono* reserved for
  aligned tabular numerals (stat values, dex numbers). All three are
  self-hosted as local `.woff2` files under `web/fonts/` so the app has no
  runtime dependency on an external font CDN.
- **Layout** -- a persistent left rail (collapsing to a bottom tab bar on
  mobile) plus a sticky top search bar; Pokédex and collection use a
  responsive card grid; the detail panel is a single right-side drawer
  reused for every "inspect one Pokémon" moment. Deliberately avoided: the
  warm-cream-plus-terracotta-serif look and the near-black-plus-single-accent
  look that read as default "AI-generated" choices, a SaaS card kit with
  uniform shadows, and ALL-CAPS eyebrow labels.
- **Accessibility** -- visible focus rings throughout, `prefers-reduced-motion`
  respected, every modal (detail drawer, Pokémon picker, confirm/prompt
  dialogs) traps focus, closes on Escape, and restores focus to whatever
  opened it. Confirmations and name prompts use in-app dialogs, not
  `window.confirm`/`window.prompt`.

## Battle scoring -- deterministic and documented

All match-up math lives in `app/types.py` (the 18-type chart) and
`app/battle.py` (scoring). There are no movesets, abilities, items, or
levels in the dataset, so this is **species/type-based planning advice,
not a battle simulator** -- the UI labels it as such everywhere it appears.

1. **Type chart.** A complete modern (Gen 6+) 18-type chart. Dual typing
   multiplies the two defending types' multipliers together (so a 2x/0x
   combination is always exactly 0x, immunity always wins; a 2x/2x
   combination is 4x).
2. **Per-match-up score.** For a candidate against one opponent, find the
   candidate's best possible STAB type advantage (its best type times the
   opponent's typing) and the worst hit it would take back (the
   opponent's best type times the candidate's typing). Each multiplier
   maps to points on a symmetric scale:
   - Offense: `4x→+2, 2x→+1, 1x→0, 0.5x→-1, 0.25x→-2, 0x→-3`
   - Defense: `0x→+3, 0.25x→+2, 0.5x→+1, 1x→0, 2x→-1, 4x→-2`

   (0x offense is scored *worse* than being resisted, since the
   candidate's own typing can never land an advantage; 0x defense is
   scored *best*, since the candidate is immune outright.)
3. **Team averaging.** Against an opposing team, the type_score is
   averaged across all members.
4. **Stat tiebreaker.** A small stat-based bonus (`battle_readiness`:
   speed, bulk, and peak offense, each normalized against the full
   dataset) is scaled by `STAT_BONUS_WEIGHT` (0.15) before being added.
   Because every per-opponent type_score is an integer, two candidates'
   average type_scores against an up-to-six-member team can differ by as
   little as 1/6 ≈ 0.167 -- and 0.15 is kept strictly below that, by
   construction. That guarantees the stat tiebreaker can only ever decide
   between two candidates with an *equal* average type score, and can
   never outrank a genuine type-effectiveness difference, no matter the
   opponent team size. This invariant has a direct regression test
   (`tests/test_battle.py::test_stat_bonus_weight_cannot_outrank_type_score`)
   plus a concrete worked example
   (`test_better_type_score_beats_much_higher_stat_bonus_against_a_team`).
5. **Team generation.** A deterministic greedy pass repeatedly adds the
   remaining candidate with the best marginal value (match-up score, plus
   a bonus for covering opposing types the team doesn't hit yet, minus a
   penalty for stacking a weakness the team already shares), breaking ties
   by ascending Pokédex number. Owned-mode generation draws strictly from
   the candidate pool it's given -- it can never silently include a
   Pokémon outside that pool, and reports a shortfall message instead of
   padding the team if the collection is too small.
6. **Replacement suggestions** are generated separately from the
   generated/saved team: for each of a team's weakest match-ups, the best
   *unowned* Pokémon that would improve on it by a full point or more is
   surfaced, along with the owned member it would replace, the resulting
   score improvement, and factual stat-only trade-offs (bulk, speed, peak
   offense) -- never invented moves or abilities.

## Dataset limitations

`pokemon.csv` has species-level base stats, types, and generation/flavor
metadata -- not movesets, abilities, individual levels, held items, or
competitive-format legality. Every battle/team recommendation in the app
is therefore type- and stat-based planning advice, explicitly labelled as
such, not a guarantee of winning a real battle or a competitive simulator.

## Local deployment limits

This is a single-machine local tool, not a deployable multi-user service:

- Binds to `127.0.0.1` only, plain HTTP (no TLS) -- fine for localhost,
  not safe to expose on a network as-is.
- SQLite access is serialized behind one process-wide lock; adequate for
  one person using the app from one browser, not a concurrent multi-user
  workload.
- Session cookies are `HttpOnly` + `SameSite=Strict`, which is the main
  CSRF defense for a same-origin local app; there is no additional CSRF
  token.
- No password reset flow -- a forgotten password means registering a new
  account.
- No rate limiting, email verification, or audit logging.

## Tests

```
python -m unittest discover -s tests
```

85 tests across five files:

- `tests/test_types.py` -- the type chart itself: immunities, dual-type
  multiplication (including 0x/0.25x/4x), quad weaknesses/resistances,
  and that every chart entry is a real multiplier.
- `tests/test_battle.py` -- scoring and team generation: top-20 ranking
  and sort order, ownership filtering, distinct/deterministic generated
  teams, strict ownership pools, shared-weakness detection, and the
  stat-bonus-cannot-outrank-type-score guarantee (with a regression test
  built from a deliberately adversarial fixture).
- `tests/test_auth.py` -- password salting/hashing, verification, session
  token uniqueness, username/password validation.
- `tests/test_api.py` -- the full HTTP-independent API layer: account
  registration/login, per-user isolation of collections and teams, strict
  ownership enforcement on team creation/updates, battle-planner
  filtering and team generation, and malformed-input handling (wrong
  JSON types for usernames/passwords/team names/modes, bogus
  size/limit values, non-list opponent arrays).
- `tests/test_bodyparse.py` -- the HTTP body-parsing helpers in isolation:
  missing/negative/non-numeric/oversized `Content-Length`, and JSON
  bodies that parse but aren't an object (bare array/string/number/null).

## Project layout

```
server.py              stdlib HTTP server: routing, cookies, static files
app/
  types.py             the 18-type chart + dual-type math
  battle.py             scoring, ranking, team generation
  data.py               loads pokemon.csv into memory
  db.py                  SQLite schema + queries (users/sessions/collection/teams)
  auth.py                 password hashing, session tokens, validation
  bodyparse.py            pure HTTP body-parsing helpers (unit-testable)
  api.py                   JSON API handlers + routing table
web/
  index.html, styles/, scripts/   buildless frontend (ES modules, no bundler)
  fonts/                self-hosted .woff2 files
tests/                  unittest suite (see above)
runtime/                SQLite database (gitignored, created on first run)
```
