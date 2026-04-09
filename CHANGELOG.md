# CivGame AI Development Changelog

## Session: 2026-04-09 | 400+ simulations total

### Latest Changes

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
