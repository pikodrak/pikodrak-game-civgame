# CivGame AI Development Changelog

## Session: 2026-04-09 | 400+ simulations total

### Latest Changes

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
