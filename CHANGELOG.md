# CivGame AI Development Changelog

## Session: 2026-04-20 | Enemy borders visible through fog of war

**Bug:** Enemy territory drew no border if the owning city was hidden by fog
of war. Frontend derived territory from `state.cities` (radius-around-city),
but enemy cities in fog aren't sent to the client — so the territory
surrounding them was invisible, yet moving into it still triggered a war
declaration. Player could walk into "neutral-looking" tiles and accidentally
start wars.

**Fix:** Backend `to_dict()` now sends `tile_owners` — a `{"q,r": player_id}`
map for every tile the player has seen (visible or explored), computed via
`get_tile_owner`. Frontend uses this as the authoritative source for
territory rendering (colored fill + outer border), falling back to
city-radius derivation only if the server didn't send it.

## Session: 2026-04-20 | Package refactor: civgame/

Monolithic `game_engine.py` (4127 lines, one `GameState` class with ~60 methods)
split into a proper package `civgame/`:

```
civgame/
├── __init__.py              re-exports
├── constants.py             Terrain, TERRAIN_*, GAME_CONFIG, CITY_NAMES
├── hex.py                   hex_neighbors, hex_distance, offset_to_cube
├── data/                    static game data
│   ├── technologies.py
│   ├── units.py
│   ├── buildings.py
│   ├── civilizations.py
│   └── improvements.py
├── mapgen/                  map generators
│   ├── earth.py             real continent outlines
│   └── random_map.py        random continents
├── mixins/                  GameState responsibility split
│   ├── visibility.py        (fog of war, tile ownership)
│   ├── city.py              (founding, yields, defense)
│   ├── movement.py          (move_unit, A* pathfinding)
│   ├── combat.py            (melee + ranged)
│   ├── actions.py           (worker, fortify, sentry, explore)
│   ├── diplomacy.py         (war/peace/alliance)
│   ├── research.py          (set_research)
│   ├── turn.py              (end_turn, score)
│   ├── serialization.py     (to_dict, save/load)
│   └── simulation.py        (classmethod simulate)
├── ai/                      AI domain-split
│   ├── core.py              (_run_ai, _log_ai, home_city redist)
│   ├── production.py        (what to build)
│   ├── worker.py            (tile improvements)
│   ├── settler.py           (city placement)
│   ├── military.py          (move/attack/defend)
│   └── civilian.py          (spy, caravan)
└── state.py                 GameState(mixins...) + __init__
```

**Backward compat:** `game_engine.py` is now a 34-line shim that re-exports
everything — `server.py`, `config_loader.py`, `run_sim.py`, `sim_report.py`
work unchanged.

**Fixes found during refactor:**
- `config_loader.py`: changed `game_engine.GAME_CONFIG = new_dict` to
  `GAME_CONFIG.clear(); GAME_CONFIG.update(new)` so mutations are visible
  through all modules referring to the same dict object (identity-preserving).
- A stray `@classmethod` was incorrectly attached to `save_full` after
  extraction — removed; `simulate` retains its correct `@classmethod`.
- Missing `import random` / `import GAME_CONFIG` / `CITY_NAMES` / `TERRAIN_MOVE_COST`
  imports detected in mixin files via static analysis and added.
- **Pre-existing recursion bug** found and fixed in `_advance_turn`: when
  the sole human player died, the mutual `end_turn ↔ _advance_turn`
  recursion kept cycling through alive AIs with no stopping condition,
  blowing the stack after ~500 turns. Fix: detect "no living human" and
  set `game_over = True` (winner = highest-scoring alive AI).

**Verification:**
- All objects identical between `game_engine.X` and `civgame.X` (tested via `is`).
- MRO order verified (GameState → 10 mixins → object).
- 100-turn full AI simulation runs, save/load roundtrip succeeds, classmethod
  `GameState.simulate()` works, `sim_report.py` and `run_sim.py` import fine.
- `config_loader` hot-reload continues to work (dicts mutated in place).
- Server starts and `/api/version` returns correct data.

Largest file now: 423 lines (simulation.py). Most mixin files 150-350 lines.

## Session: 2026-04-20 | Goto preview + road cost fix

### Road/railroad movement bug fix
- **Bug:** Road/railroad cost multipliers used `max(1, int(cost * 0.4))` — on cost-1 terrain (grass/plains/desert) roads gave **zero** speed-up because `int(0.4) = 0 → max(1, 0) = 1`. Only forest/hills benefited, and even there railroad was no faster than road.
- **Fix:** Switched move costs to **float**. Road halves cost (× 0.5), railroad quarters it (× 0.25), floor at 0.25.
  - Grass/plains/desert (base 1) → road 0.5, railroad 0.25
  - Forest/hills (base 2) → road 1.0, railroad 0.5
  - A warrior (mov=2) now covers **4 grass road tiles** or **8 railroad tiles** per turn (was 2).
- Affected: `move_unit()` (line 1050), `_compute_path()` (A* for preview/render), `_find_path_next()` (A* for actual movement). A* now genuinely prefers roads.
- Frontend: `Moves` display trims trailing zeros for fractional MP (`1.5/2`, `0.25/2`).

## Session: 2026-04-20 | Goto preview + confirm

### Goto preview mechanic
- Holding left mouse button 400ms on a target hex now shows a **cyan dashed preview path** (instead of immediately setting goto)
- Click again on the same target hex to **confirm** — goto is set and unit starts moving
- Click anywhere else to **cancel** the preview
- `Esc` also clears the preview
- Preview shows pulsing cyan target ring with `Nt ?` distance indicator (distinct from confirmed golden goto)
- New backend endpoint `POST /api/game/{id}/path_preview {unit_id, q, r}` — read-only A* path, no state mutation

## Session: 2026-04-10/11 | v0.9.5 — Unit food, city management, Earth maps, full manual

### Latest Fixes (v0.9.5)
- Worker only shows improvements valid for current tile (no farm where farmed, no road where roaded)
- Goto immediately moves unit (uses all movement points this turn)
- Production complete dialog shows what was built before opening new production popup
- Auto-produce immediately starts production when activated on idle city
- Comprehensive How to Play manual (units, buildings, terrain, combat, economy, tech tree, tips)
- Custom styled dialogs replace all browser confirm/alert/prompt
- Profile menu (renamed from My Account) with language selector
- __init__ fix: wrap_q method was accidentally breaking game initialization
- Version bumped to 0.9.5

### Unit Food System (NEW)
- Every military unit has a **home city** (city where it was produced)
- **Scaling food cost**: first 2 units FREE, units 3-4 cost 1 food each, units 5+ cost 2 food each
- Example: city with 6 military units pays 0+0+1+1+2+2 = 6 food/turn
- This naturally limits army size — too many units = city starves
- **AI redistributes home_city** each turn to balance food load across cities (no more Roma pop=1)
- Civilians (settler, worker, spy, caravan) don't eat food
- City panel shows food breakdown: produced - pop eats - army eats = surplus

### City Capture Rework
- Enemy units inside captured city borders are **pushed out** to nearest tile outside borders (BFS)
- If no valid exit tile exists (surrounded), unit is disbanded
- Units do NOT desert or switch sides
- Orphaned units (home_city was captured) reassign to nearest remaining city

### Worker AI Rework
- Workers prioritize **farms/improvements first** when any city has low food surplus
- Only switch to **road building** when food surplus is healthy (>1)
- Road building uses **A* pathfinding** to find optimal path to capital
- Roads to capital get priority boost (d-5) to ensure trade route connection
- Result: 77 farms built, cities connected to capital for trade income

### City Management Screen (NEW)
- New "Manage City" button in city panel
- Shows **all workable tiles** with terrain, food/prod/gold, improvements, worked status
- **Food breakdown**: production vs consumption (population + army)
- **Growth timer**: "Grows in ~X turns" or "Shrinks in ~X turns"
- **Happiness indicator**: smiley/frown with value
- **Warnings**: starvation (red), unhappy (orange), growth (green), no road connection
- **Home units list**: which military units are eating from this city
- API: `GET /api/game/{id}/city/{cid}/manage` for AI bots

### Custom In-Game Dialogs
- ALL browser native dialogs (confirm/alert/prompt) replaced with styled in-game modals
- War confirmation, end turn warning, disband, delete save, token creation — all custom UI
- Consistent dark theme with gold accents, keyboard support (Enter/Escape)

### Menu Overhaul
- "My Account" renamed to **Profile** — shows username, language selector (EN/CS)
- Saves removed from profile (available via Load Game)
- **How to Play** button — comprehensive game manual with all mechanics, shortcuts, tips
- API tokens and admin tools remain in Profile

### Pre-Game Setup Screen (NEW)
- **New Game** opens full setup modal instead of inline selects
- **29 civilizations** displayed with leader, trait, bonus, strategy, color
- Click to select — shows detail card with all civ info
- **Map type**: Random / Earth (Small/Medium/Large)
- **Globe map**: checkbox for wrap-around (left edge connects to right)
- **Earth map generator**: real continent outlines (NA, SA, Europe, Africa, Asia, Australia)
  - Latitude-based terrain: polar→tundra, temperate→forest/plains, tropical→grass/jungle
  - Mountain ranges: Rockies, Andes, Alps, Himalayas, Urals
  - Sahara desert band, coastal tiles auto-generated
  - ~38% land coverage (realistic)
- **Opponent count**: 1-7 opponents selectable
- Map size selector disabled for Earth maps (fixed sizes)

### Unit Movement Animation
- Smooth 250ms easeInOutQuad animation when units move between hexes
- Unit glides from old hex to new hex instead of teleporting

### Production Queue & Auto-Produce
- **Production queue**: up to 5 items queued per city (Shift+click to add to queue)
- **Auto-produce modes**: Smart (AI decides), Units only, Buildings only, Off
- Queue displayed in production modal with numbered items
- After production completes: queue item → auto-mode → idle (popup for human)

### UI/UX Improvements
- **Save & Quit dialog**: nice popup with save name input, Save & Quit / Quit Without Saving / Cancel
- **Production popup**: opens automatically after founding city and after production completes
- **Gold income change**: top bar shows gold delta (+5, -3) each turn, red when negative
- **Last produced**: top bar shows what was last built/produced
- **Worker tech filter**: only shows improvements that are researched (Farm needs agriculture, etc.)
- **Worker keyboard shortcuts**: 1=Farm, 2=Mine, 3=Mill, 4=Road, 5=Rail, 6=Trade
- **Workers skip during building**: workers building improvements are not selected as active units
- **Move pause**: 0.6s delay after unit finishes moving before selecting next unit
- **Simulation removed from menu**: only available via command line (sim_report.py)

### Tech Tree Descriptions
- Each technology shows what it unlocks and WHY it's useful
- Shows prerequisite technologies
- 31 techs with human-readable descriptions

### Explore Fix
- Explore avoids foreign territory (prevents accidental war declarations)
- Uses A* for movement instead of raw BFS step
- If move fails, marks direction as explored (prevents infinite retry)

### Shared Tiles Between Cities
- If two cities of same player have overlapping borders, each tile is worked by only the NEAREST city
- Prevents double-harvesting of shared tiles

### Settler Population Cost
- Settler costs **1 population** from producing city (like Civilization)
- City must have **pop >= 2** to build settler
- Food store resets to 0 after settler produced
- AI won't queue settler in size-1 cities

### Goto Path Visualization
- Selected unit with goto shows **golden dashed line** along A* path to target
- **Pulsing diamond marker** on target hex
- **Distance counter** (number of hexes) shown below target
- Path computed via A* on server (same algorithm as unit movement)

### AI Intelligence Fixes
- **Settler pre-check**: AI verifies real settle spot exists before producing settler (no more blind production)
- **Settler wander reduced**: avg 5.2t→4.0t, max 33t→8t
- **Territory entry dedup**: "entered territory — WAR!" logged only once (not per unit)
- **Spy cap**: reduced to 1 per player (was 2)
- **Culturalist expansion**: culturalists get +2 max cities to support culture victory (needs more cities)
- **Culturalist settler bonus**: +10 settler score for culture strategy

### Simulation & Balance Fixes
- **Scaling food replaces hard cap**: army size limited by food, not arbitrary cap
- **T1 false combat fix**: settler consumption no longer counted as "destroyed in combat"
- **Gang-up rebalanced**: ratio 1.2→1.5, min score 500→1000, chance 25%→10%
- **Settler timeout**: after 10 turns, force-settle at current location
- **Results**: max 5.0 units/city (was 21.5), avg settler wander 3.2t (was 22t), 133 growth events

### Versioning System (NEW)
- Game version v0.9.0 displayed in menu and game top bar
- `GET /api/version` returns version, build date, and latest changelog
- My Account panel shows version + changelog sections
- Changelog parsed from CHANGELOG.md automatically

### DALL-E Graphics (via OpenAI API)
- 21 unit sprites generated via DALL-E 3 (detailed pixel art style)
- 29 building icons generated via DALL-E 3 (isometric style)
- Terrain kept as PIL-generated (DALL-E can't make seamless flat textures for hex tiles)
- PIL units enhanced with 3px dark outline for map readability
- Unit size on hex increased from 85% to 95%

## Session: 2026-04-10b | Ranged combat, game length, border visibility

### Ranged Combat Mechanic (NEW)
- **Ranged units** (archer, catapult, artillery, bomber) can now attack from distance without moving
- Archer/catapult: range 2, Artillery/bomber: range 3
- Attacker stays on their hex, takes only 25% return fire
- Ranged attacks **cannot capture cities** — city HP floors at 1, melee unit needed for final capture
- New API endpoint: `POST /api/game/{id}/ranged_attack {unit_id, q, r}`
- AI uses ranged attacks: fires at enemies in range before closing distance
- Frontend: Ranged button (R key), orange range overlay when targeting, range stat in unit panel
- Keyboard shortcuts help updated

### Rules Updated for AI Bot Accuracy
- Diplomacy: clarified API action names (war/peace, NOT declare_war/make_peace)
- Fortify: clarified it only uses current turn moves, not permanent block
- Explore: clarified civilians CANNOT explore
- Settler: added note about manual movement requirement
- Gold/bankruptcy: clarified negative gold IS a problem with maintenance
- Walls defense: documented exact values (Palace=10, Walls=50, Castle=80, Bunker=60)
- City capture: clarified melee required, ranged cannot capture

### Game Length & Visuals
- Added `max_turns = 300` turn limit (score victory at limit)
- Increased space victory threshold: 5000 → 12000 production
- Increased culture victory threshold: 8000 → 20000 culture
- Territory border lines: thicker (2.5 → 4.5px) and more opaque (.7 → .85) for better visibility
- Score calculation refactored to `_calc_score()` method

## Session: 2026-04-10 | 14 new buildings, 3 new techs, 15+ simulations

### Simulation-Driven Balance (this session)

**New Buildings (14 total)**
- barracks (bronze_working): +10 defense, units get +10 XP
- harbor (sailing): +1 food, +3 gold (coastal cities)
- colosseum (construction): +1 culture, +3 happiness
- forge (iron_working): +2 production
- stable (horseback): +1 prod, +1 gold
- workshop (engineering): +3 production
- school (education): +2 science, +1 happiness
- museum (aesthetics): +5 culture, +2 happiness
- theater (aesthetics): +3 culture, +2 happiness
- military_academy (military_science): +20 defense, units get +15 XP (stacks with barracks)
- hospital (industrialization): +4 food, +1 happiness
- airport (flight): +2 gold, +10 defense
- stadium (electricity): +2 culture, +4 happiness (counters factory/power_plant unhappiness)
- bunker (nuclear_fission): +60 defense

**New Technologies (3)**
- aesthetics (theology + printing_press): unlocks museum, theater
- military_science (gunpowder + education): unlocks military_academy
- Updated existing techs: bronze_working→barracks, sailing→harbor, construction→colosseum, iron_working→forge, horseback→stable, engineering→workshop, education→school, industrialization→hospital, electricity→stadium, flight→airport, nuclear_fission→bunker

**Trade Routes & Economy**
- Cities connected to capital by road earn +1 gold per 2 population (min 1)
- BFS road connection check from city to palace
- Bankruptcy cascade: disband military → sell cheapest building (except palace)
- Military economy guard: AI won't build military when maintenance > income
- Spy cap reduced to max 2 per player

**Diplomacy Balance**
- Alliance join war: loyalty-based chance (50-90%) instead of automatic
- Max 2 alliances per player (prevents web of obligations)
- Alliance formation rate halved (loyalty * 0.1)
- Result: war declarations dropped from 55 → 5-24 per game

**AI Improvements**
- AI building scoring for all 14 new buildings with strategy-aware bonuses
- Captured cities immediately get production assignment
- Tech priorities updated for all strategies (aesthetics, military_science)
- Duplicate tech prevention (spy steal + research completion race condition)
- Config loading fixed for simulation mode

**Simulation Logging**
- Map terrain counts at game start
- Player start positions, traits, strategies
- Per-city: building list, trade connection status, HP
- Diplomacy state per turn
- Victory type detection (space/culture/domination/score)
- Final map state: improvement/road positions, per-player building totals

**Victory Thresholds (from config)**
- Space: 5000 production (was defaulting to 2000)
- Culture: 8000 (was defaulting to 3000)
- Domination: 75% of cities

**Happiness System**
- Cities have happiness score: building bonuses minus population penalty (1 per pop above 4)
- Unhappy cities (happiness < 0): -25% production, -25% science, food surplus capped at 1
- Key happiness buildings: colosseum(+3), stadium(+4), temple(+2), theater(+2), museum(+2)
- Industrial buildings cause unhappiness: factory(-1), power_plant(-1), nuclear_plant(-2)
- Strategy: build happiness buildings before growing cities past population 4

**Simulation Results (20+ sims)**
- 25/28 building types consistently built in larger games
- All 4 victory types active: space, culture (close), domination (early rush), score
- Disbands: 1-10 per game (down from 47)
- Wars: 3-24 per game (down from 55)
- Correct historical city names: Praha, Seoul, Mecca, Roma, Aachen, Karakorum, etc.
- 29 buildings, 31 technologies, 21 unit types all active
- Happiness system prevents infinite growth without investment

## Session: 2026-04-09 | 400+ simulations total

### Latest Changes

**Buildings & Tech Expansion + Economy Overhaul**
- 12 new buildings: barracks, harbor, colosseum, forge, stable, workshop, school, museum, theater, military_academy, airport, bunker
- 3 new technologies: aesthetics (museum/theater), military_science (military_academy), updated prereqs
- Barracks/military_academy XP bonus: military units produced in cities with barracks get +10 XP, military_academy adds +15 XP
- AI building scoring: all new buildings properly scored with strategy bonuses
- AI tech priorities: updated for all strategies to include new techs (aesthetics, military_science)
- Trade route bonus: cities connected to capital by road earn +1 gold per 2 population (min 1)
- BFS connection check: traces road/railroad path from city to palace city
- Building selling: when bankrupt with no military units, cheapest building sold for half cost (except palace)
- Bankruptcy cascade: disband units → sell buildings, proportional to debt depth
- Military economy check: AI won't build military when maintenance exceeds income
- Alliance war join is now loyalty-based (50-90% chance) instead of automatic
- Max 2 alliances per player to prevent cascade wars
- Alliance formation rate halved (loyalty * 0.1 instead of 0.2)
- Config loading fixed: simulations now load game_config.ini properly
- Victory threshold defaults aligned: space=5000 prod, culture=8000, domination=75%
- Enhanced simulation logging: map data, terrain counts, trade connections, diplomacy state, building lists, per-city details
- Settler founding fix: pre-check unified with found_city checks, log only after success
- /api/rules: full tech tree, all civilizations, barracks system, complete building/unit data

**Advanced Diplomacy Complete**
- War mobilization: during war ALL military units march toward nearest enemy city
- Culture pressure: contested tiles won by city with higher culture/distance ratio
- Relations system: -100 to +100 opinion, city near border = -30 provocation
- Alliance auto-war: attack ally → all alliance members join defense
- Declare war respects cooldown (10 turns)
- Explore cancelled for military during war
- Menu panel z-index fix for New Game button

**Game Logging + Spectator Mode**
- All game actions logged to SQLite: move, end_turn, production, research, diplomacy
- Active games registered in DB with user, size, turn, timestamp
- Spectator mode (admin pikodrak only):
  - "View Active Games" in My Account panel
  - Lists all active games with player, size, turn, age
  - "Watch" button loads game state without fog of war
  - Auto-refreshes every 3 seconds to see live gameplay
- Admin API: GET /api/spectate/games, /api/spectate/game/{id}, /api/spectate/log/{id}

**My Account Panel**
- "My Account" button in main menu (only for logged-in users)
- Saved Games list: load any save with one click
- API Tokens: create, view (click to copy), revoke tokens
- API Reference: inline documentation of all AI endpoints
- Logout button
- Token creation shows full token in alert (copy once)

**AI API: Full Game Control via REST**
- API tokens: persistent tokens per user (civ_xxx...), stored in DB
- Endpoints: POST /api/auth/token (create), GET /api/auth/tokens (list), DELETE /api/auth/token/{id} (revoke)
- GET /api/game/{id}/ai/state — complete game state (no fog, all info)
- GET /api/game/{id}/ai/actions/{player} — all possible actions per unit/city:
  - Per unit: movable hexes, buildable improvements, available actions (move/fortify/explore/found_city/etc)
  - Per city: yields, available productions, buildings
  - Available techs, diplomacy options with cooldowns
- GET /api/game/{id}/ai/map — full terrain/improvement/road/territory data
- All existing action endpoints work with API token auth

**User Authentication System**
- SQLite database (civgame.db) with users and saves tables
- bcrypt password hashing, JWT tokens (30-day expiry)
- Login/Register screen before main menu
- "Play as Guest" option (no account needed)
- Per-user game saves (API: /api/user/save, /api/user/saves, /api/user/load/{id})
- Auth token in all API calls, Logout button in game
- Enter key submits login form

**Critical fixes from screenshot analysis**
- FIXED: Terrain rendering was catastrophically broken (rotation/offset/scale removed)
- 4 variants per terrain type — position-based selection, no two adjacent hexes identical
- Subtle brightness-only variation (no geometric transforms)
- FIXED: Explore BFS — finds nearest REACHABLE unexplored tile via pathfinding
  - Old: random sampling got stuck behind mountains
  - New: BFS from unit, first unexplored passable tile = target
- JS syntax validation added after every change (node --check)

**Major visual overhaul (based on screenshot analysis)**
- Terrain variation: each hex rotated, offset, scaled differently — no two identical tiles
- Brightness variation per tile (warm/cool tint)
- Units 85% of hex size (was 70%) + player color dot at bottom-right
- Player identification: colored circle on every unit shows owner at a glance
- Improvements visible on map: farms (green rows), mines (triangle), lumber mills (circle), trading posts (gold coin)
- Roads visible: brown lines connecting adjacent road tiles, railroads dashed with darker color
- Territory borders fixed: uses territory ownership map, draws border only where neighbor is different player
- Border drawn at 98% hex radius for clean alignment

**BFS pathfinding, worker manual build, unit panel redesign**
- BFS pathfinding replaces greedy step — units navigate around mountains/water
- Goto/explore now finds real paths instead of getting stuck
- Worker manual build: Farm, Mine, Mill, Road, Rail, Trade buttons
- Unit panel redesign: icon (48x48), position & terrain, building status
- Next Unit button (Tab) to cycle through active units
- Shows active unit count, terrain type, building progress

**Bug fixes: naval, disband, borders**
- Naval units only buildable in coastal cities (adjacent water required)
- Disband button (Del key) — delete unit with confirmation
- Territory border edges fixed — correct hex edge mapping for border segments

**Production modal (center screen)**
- Build menu opens as centered modal instead of tiny right panel
- Two-column layout: Units | Buildings with icons (36x36 / 32x32)
- Shows estimated turns for each item
- Opens automatically for idle cities at start of turn
- Escape closes modal

**Active unit highlight & end-turn idle selection**
- Active unit: pulsing golden hex highlight + thick gold ring + inner white ring + glow shadow
- End turn with idle units: selects and centers on first idle unit before confirm dialog
- Camera pans to idle unit so player can see what needs orders

**Territory border rendering**
- Thick colored border (lineWidth=3, alpha 55%) only on edges facing outside territory
- No more full hex outlines — just clean border segments where territory ends
- Light fill inside territory preserved

**Gameplay Fixes (user-reported bugs)**
- Goto: hold left mouse button 400ms to set (was single click distant hex)
- Goto units skipped in unit cycling (like fortify/sentry)
- Worker auto-build button (A key) — sets worker to auto-improve nearby tiles
- End turn confirmation: warns if units without orders remain
- Civilian protection: AI won't attack settlers/workers unless at war
- Settler coordination: won't target spots where another settler is heading
- Controls panel updated with Auto-Build (A) shortcut

**AI Iteration 4: Infrastructure & Military Balance**
- Core buildings (granary+25, library+20, marketplace+18) scored much higher
- Walls get +20 bonus when at war or enemies nearby
- Military diminishing returns: harsh penalty above 5 units/city
- Aztec buildings: 2-3 → 7-15 per game
- Greece military: 62 → 9 (capped by diminishing returns)
- All civs now build infrastructure alongside military

**High-Quality Graphics Upgrade**
- All sprites upgraded to 128x128 resolution (from 64x64)
- Units: detailed body proportions, armor, weapons, shadows, layered shading
- Buildings: architectural detail, columns, arches, proper roofing, gold accents (96x96)
- Terrain: natural variation patches, grass blades, wheat heads, tree canopy layers, snow-capped peaks
- Drop shadows on all unit sprites
- Proper material colors: skin tones, metal shading, wood grain, leather

**PNG Sprite Graphics System**
- 21 unit sprites (64x64 pixel art PNGs) — warrior through ironclad
- 15 building icons (48x48 PNGs) — palace through nuclear_plant
- 8 terrain tiles (64x64 PNGs) — grass, plains, forest, hills, mountain, desert, water, coast
- All generated via Python PIL in Civ II modern pixel-art style
- Frontend loads PNGs with canvas fallback if image not ready
- Production panel shows unit/building icons next to names
- Building list in city panel shows icons
- Terrain tiles rendered as hex-clipped PNGs with per-tile variation
- All icon paths in game_config.ini (icon = static/img/...)

**Strategy-Victory Alignment & Conqueror Buff**
- Strategy-victory alignment improved: 60% → 67%
- Conqueror strategy: +15% war chance (vs 8%), earlier domination urgency at 30%+ cities
- Conqueror tech priorities expanded: added industrialization, flight
- All 4 victory types active: space 6, domination 3, culture 3, score 3

**Combat & AI Iteration 3 (based on battle analysis)**
- Combat damage increased: 30+10/30+5 → 50+15/40+10 (battles 60% more decisive)
- Draw ratio dropped: 867→354 (29% win rate → 46%)
- Obsolete units seek nearest city for upgrade when not at war
- Old units at end: 10+ → 0 (all upgraded)
- City defense smarter: only rush when outnumbered by nearby enemies
- Defend spam fixed: 174→0 (was over-defending)

**Unit Upgrades & City Defense**
- Unit upgrade system: warrior→swordsman→musketman→rifleman→infantry (and mounted/naval chains)
- Upgrades happen in own cities, cost half of unit price
- AI upgrades obsolete units when gold allows (~57 upgrades per game)
- City defense: units rush to defend cities when enemies within 3 hexes (~63 defends per game)

**Continued AI Tuning (2nd analysis round)**
- Score victory: highest score wins if no other victory by turn limit
- Space tech rush: if 1+ space techs done, remaining get 70% cost discount
- Domination urgency: +25 military score when controlling 40%+ cities
- 15/15 games won, 3 victory types all active, 5 strategies winning

**AI Fixes Based on Log Analysis (7 problems fixed)**
1. **Economy disaster** (gold -1206): aggressive bankruptcy — disband multiple units at once based on debt depth
2. **Settler stuck** (109 events → 0): settlers now try settling at current location when stuck, or random move to get unstuck
3. **Buildings never built**: building scores increased with game phase multiplier (1.0→1.5x), gold buildings extra bonus when bankrupt
4. **Income flat**: workers build trading_posts (+2g) when gold negative, gold buildings scored higher
5. **Peace spam** (294→36): AI respects diplomacy cooldowns in decision loop
6. **Worker imbalance**: increased worker target to 1 per city (max 4), was 1 per 2 cities
7. **Military when bankrupt**: -30 score penalty for military production when gold < -30

**Enhanced Simulation Logging**
- Per-turn economy: income, maintenance, net profit
- Per-turn yields: food, prod, science, culture totals
- Victory progress: space (X/3 techs, X/2000 prod, X%), culture (X/3000, X%), domination (X/Y cities, X%)
- Territory tile count (every 10 turns)
- Improvement & road count per player
- Battle results: who won, HP remaining, damage dealt/taken
- City capture: who captured what from whom, attacker HP
- Siege failures: unit lost, city HP remaining
- Settler wander time: how many turns between creation and founding
- Settler stuck detection: logged when can't move toward target
- Elimination: player name, remaining units, turn number
- Worker improvement yields: shows +food/+prod/+gold for each build

**Czech Kingdom Civilization**
- Leader: Jan Zizka (Hussite Wars)
- Trait: industrious (+20% production)
- Bonus: science
- Strategy: turtle (defense + science → space victory)
- Aggression 0.35 (peaceful), Loyalty 0.85 (reliable ally)
- Inspired by: Charles University, Hussite war wagons, Czech industry (Skoda)

**GUI Improvements**
- Top bar: resource labels (Gold, Science, Culture, Army) under values
- Buttons grouped compactly, better spacing
- Panel: better contrast, larger fonts for values
- Production items: clearer hover, better readability
- Action buttons: better hover effect with gold accent
- After setting production → auto-jumps to next idle city or next unit

**War Confirmation Popup**
- Human player entering foreign territory → confirm dialog "This means WAR!"
- Attacking non-war unit/city → same confirm dialog
- Only after player confirms, war is declared and move executed
- AI auto-declares war (no popup)

**Alliance & Territory System**
- 4 diplomatic states: **war** / **peace** / **alliance** / neutral
- Alliance = mutual free passage through territory + formed against common enemies
- Loyal civs (loyalty > 0.5) form alliances when sharing enemy
- Disloyal civs may break alliances
- UI: Alliance/Break buttons in Diplomacy panel
- AI forms ~3 alliances per game, territory violations trigger ~8 wars

**Territory System**
- `get_tile_owner(q,r)` returns which player controls a tile via city borders
- Entering foreign territory (neutral) auto-declares war
- Peace treaty allows passage through allied territory
- Founding a city pushes foreign units outside new borders
- Territory = city border_radius (grows with culture: 1→2→3→4→5)

**Goto System**
- Click distant hex with selected unit → auto-move each turn
- Golden dashed line shows path, dot shows target
- Cancelled when: enemy adjacent (non-peace), arrived, stuck
- Panel shows "Moving to (x,y)" status

**Default Diplomacy**
- All civilizations start at peace (was neutral)
- Entering neutral territory triggers war

**INI Configuration (game_config.ini)**
- All game parameters externalized to INI file
- Hot-reload every 2 seconds — edit while game runs
- Sections: [game], [terrain_*], [civ.*], [unit.*], [building.*], [improvement.*]
- config_loader.py with background watcher thread

**Workers Two-Layer System**
- Improvements (farm/mine/lumber_mill) and roads (road/railroad) are separate layers
- Both coexist on same tile — farm + road on same hex
- Worker priority: improvement first → road → railroad upgrade
- Worker seeks unimproved tiles near cities, then connects cities with roads

---

### Phase 1-3: Core Features ✅
- Workers + 7 tile improvements
- Spy (tech theft/sabotage) + Caravan (trade gold)
- 6 leader traits with combat/yield bonuses
- Personality-driven diplomacy (aggression/loyalty)

### Phase 4: Score-Based Production ✅
- Contextual scoring replaces rigid priority list
- Every option scored by: military ratio, war status, game phase, trait, strategy
- Diminishing military returns above 3x cities

### Phase 5: Unique Leader Strategies ✅

| Civ | Strategy | Trait | Aggr | Loyal | Typical Victory |
|-----|----------|-------|------|-------|-----------------|
| Rome | builder | industrious | 0.5 | 0.7 | Space/Domination |
| Egypt | culturalist | creative | 0.3 | 0.8 | Culture |
| Greece | conqueror | aggressive | 0.8 | 0.5 | Domination |
| China | expansionist | expansive | 0.3 | 0.7 | Space/Domination |
| Persia | builder | financial | 0.5 | 0.5 | Space |
| Aztec | conqueror | aggressive | 0.85 | 0.35 | Domination |
| Japan | turtle | protective | 0.4 | 0.9 | Space |
| Mongol | conqueror | aggressive | 1.0 | 0.2 | Domination |

Strategy affects: research priorities, production scoring, building preferences

### Phase 6: 3 Victory Conditions ✅
- **Space**: 3 end-game techs + accumulate 2000 production
- **Culture**: accumulate 3000 culture points
- **Domination**: control 60%+ of all cities

### Phase 7: Diplomacy & Economy Fixes ✅
- **Diplomacy cooldown**: 10 turns minimum war, 15 turns peace treaty
  - Eliminated war/peace spam (570→213 diplo events/game)
- **Bankruptcy system**: AI disbands weakest unit when gold < -50
  - Average 100 disbanded/game, prevents -1000 gold spirals
- **Strategy-weighted research**: conqueror→military techs, turtle→space techs, culturalist→culture techs
- **Gang-up on leader**: AI declares war when someone has 1.3x their score

### Final Balance (20-sim batch, latest code):

**Victory distribution:**
- Domination: 56% (conquest is king)
- Space: 22% (tech race)
- Culture: 22% (peaceful path)

**Strategy wins:**
- Expansionist (China): 8 — many cities, flexible victory
- Culturalist (Egypt): 5 — culture victory specialist
- Conqueror (Greece/Aztec/Mongol): 3 — military conquest
- Builder (Rome/Persia): 2 — production/space race

**Key metrics:**
- Avg game length: 110 turns
- Avg city captures: 9/game
- Avg player eliminations: 1.4/game
- Avg unit disbands (bankruptcy): 100/game
- 18/20 games produced winner

---

### All AI Fixes Applied:
1. Settler spam → capped by map size + free spot check
2. IDLE cities → immediate re-queue after production
3. City capture → _ai_step_toward d==0 fix
4. Worker AI → auto-improve near cities
5. Diplomacy cooldown → 10t war / 15t peace minimum
6. Bankruptcy → disband weakest unit at gold < -50
7. Gang-up mechanic → AI targets 1.3x score leader
8. Combat bonuses → aggressive +15% atk, protective +15% def
9. Research priorities → strategy-weighted tech path
10. Score-based production → contextual with diminishing returns
