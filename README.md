# CivGame — Civilization-like Turn-Based Strategy

Browser-based strategy game inspired by Sid Meier's Civilization. Python backend + HTML5 Canvas frontend.

## Quick Start

```bash
pip install fastapi uvicorn
python server.py
# Open http://localhost:8000
```

## Features

### 8 Civilizations with Unique AI Personalities

| Civ | Leader | Trait | Strategy | Style |
|-----|--------|-------|----------|-------|
| Rome | Caesar | Industrious (+20% prod) | Builder | Production → space victory |
| Egypt | Cleopatra | Creative (+4 culture) | Culturalist | Culture victory |
| Greece | Alexander | Aggressive (+15% attack) | Conqueror | Military rush |
| China | Qin Shi Huang | Expansive (+1 food) | Expansionist | Many cities |
| Persia | Cyrus | Financial (+33% gold) | Builder | Gold economy |
| Aztec | Montezuma | Aggressive (+15% attack) | Conqueror | Conquest |
| Japan | Tokugawa | Protective (+15% def, +20% science) | Turtle | Defense + tech |
| Mongol | Genghis Khan | Aggressive (+15% attack) | Conqueror | Fast conquest |

### 3 Victory Conditions
- **Space** — Research 3 end-game techs + accumulate 2000 production
- **Culture** — Accumulate 3000 culture points
- **Domination** — Control 60% of all cities

### Game Systems
- **27 technologies** across 6 eras (Ancient → Modern)
- **22 unit types** — military, settler, worker, spy, caravan
- **15 buildings** — granary, library, walls, temple, factory...
- **7 tile improvements** — farm, mine, lumber mill, road, railroad, trading post, quarry
- **Roads & railroads** as separate layer (coexist with farms/mines)
- **Fog of war** with explored tile memory
- **Spy** — infiltrate enemy cities, steal tech or sabotage production
- **Caravan** — trade with foreign cities for gold
- **Worker auto-build** — improves tiles near cities, connects cities with roads

### AI Features
- **Score-based production** — every option scored by context (war, economy, game phase, trait)
- **Strategy-weighted research** — each civ prioritizes different tech paths
- **Personality diplomacy** — aggression/loyalty drive war, peace, betrayal
- **Gang-up mechanic** — AI targets the leading player
- **Diplomacy cooldowns** — 10-turn war minimum, 15-turn peace treaty
- **Bankruptcy handling** — AI disbands units when gold goes negative
- **Worker AI** — auto-improves tiles, builds roads between cities, upgrades to railroads

### Controls
| Key | Action |
|-----|--------|
| Click adjacent | Move unit |
| Click distant | Set goto (auto-move) |
| B | Found city (settler) |
| F | Fortify (+25% defense) |
| S | Sentry (wake on enemy) |
| X | Auto-explore |
| Space | Skip unit / End turn |
| Enter | End turn |
| Ctrl+S | Save game |

## Configuration

All game parameters are in `game_config.ini` — hot-reloaded every 2 seconds:

- Civilization traits, aggression, loyalty, strategy
- Unit stats (attack, defense, movement, cost)
- Building yields and costs
- Terrain yields and movement costs
- Victory thresholds
- Diplomacy cooldowns
- Economy settings

Edit the INI file while the game runs — changes apply immediately to new games.

## Debug Simulation

Run AI-only games from the menu to test balance:
- Configurable map size, player count, turns, seed
- Full AI decision logging (research, production, diplomacy, combat, movement)
- Results saved to `saves/sim_log.json`

API endpoint: `POST /api/simulate`

## Tech Stack
- **Backend:** Python 3, FastAPI, uvicorn
- **Frontend:** Vanilla JS, HTML5 Canvas
- **Config:** INI with hot-reload
- **No database** — in-memory state, JSON save files

## Development

Built with 400+ AI simulations for balance tuning. See `CHANGELOG.md` for full development history.

---

*Co-authored by Claude AI (Opus 4.6)*
