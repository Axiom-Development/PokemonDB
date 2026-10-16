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

**Concept -- the site is the Pokédex.** Every part of the interface is a
part of a red handheld device: the page header is the device top (blue lens
plus three indicator lights), data screens are green LCD panels sitting in
cream bezels, lists and tables are readouts, numbers are pixel LCD digits
and buttons are chunky keys that press down. It is a visual skin only --
routes, data and behaviour are unchanged.

- **Tokens** -- all colours, fonts, shadows and patterns live in
  `web/styles/tokens.css`: `--dex-red` `#E3350D` (device body, primary
  action), `--lcd` `#C7E6B8` / `--lcd-dark` `#1D3B17` / `--lcd-line`
  `#A9CF98` (screens), `--bezel` `#E9E4D4` (surrounds, cards, panels),
  `--cream-deep` `#F6EBC8` (page, with a speaker-grille dot grid) and `--ink`
  `#222224` for every outline and text. Yellow and blue are tiny accents
  only (focus ring, lens). The 18 official type colours are used as badge
  fills with ink or white label text chosen for contrast.
- **Type** -- *Bowlby One SC* for titles and Pokémon names (white on red with
  a hard ink shadow, or ink on bezel); *Rubik* (variable) for UI text;
  *Silkscreen* only for numbers (dex numbers, counts, stats, totals). All
  three are OFL fonts, self-hosted as `.woff2` under `web/fonts/` -- there is
  no CDN.
- **Depth and shape** -- 3px ink outlines, flat offset shadows (never
  blurred), and bevelled corners via `corner-shape: bevel` inside
  `@supports`, with 4--8px rounded corners as the fallback. No gradients
  other than hard-edged patterns (grille, LCD scanlines, segmented bars).
- **Files** -- `tokens.css` (tokens, fonts, primitives), `main.css` (device
  shell and shared components), `database.css` (Pokédex, detail sheet, team,
  battle and account screens).
- **Layout** -- content is capped at about 1100px. Only the content area
  scrolls, so the red device scrollbar starts below the header. On phones
  (720px and below) the navigation becomes a red bottom button row and the
  browse grid stays at three columns.
- **Motion** -- only where it means something: keys press down, cards lift
  2px, and the detail sheet, dialogs and menus use a 240ms stepped
  "power-on" reveal. All of it is disabled under `prefers-reduced-motion`.
- **Accessibility** -- visible focus ring (ink outline plus yellow halo),
  labelled controls, AA contrast (`--lcd-dark` on `--lcd` is 9.1:1; white on
  `--dex-red` is only used at large-text sizes), state never conveyed by
  colour alone, and every modal (detail sheet, Pokémon picker, confirm and
  prompt dialogs) traps focus, closes on Escape, and restores focus.

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
