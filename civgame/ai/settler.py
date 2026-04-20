"""AI settler placement: find good city spots and travel to them."""
import random
from civgame.hex import hex_neighbors, hex_distance
from civgame.constants import Terrain, TERRAIN_YIELDS, CITY_NAMES

class AISettlerMixin:
    def _ai_settler_move(self, unit, pid):
        """Settler AI: find good spot and settle. Flee from enemies."""
        if unit["id"] not in self.units:
            return

        # Flee from adjacent enemies — settlers don't fight
        for nq, nr in hex_neighbors(unit["q"], unit["r"]):
            for eu in self.units.values():
                if eu["player"] != pid and eu["cat"] != "civilian" and eu["q"] == nq and eu["r"] == nr:
                    # Run away from enemy
                    flee = [(fq, fr) for fq, fr in hex_neighbors(unit["q"], unit["r"])
                            if self.tiles.get((fq, fr)) not in (None, Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN)
                            and hex_distance(fq, fr, nq, nr) > 1]
                    if flee:
                        self.current_player = pid
                        self.move_unit(unit["id"], flee[0][0], flee[0][1])
                        self._log_ai(pid, f"SETTLER: fleeing from enemy at ({nq},{nr})")
                    return

        # Find target spot once
        target = self._ai_find_settle_spot(unit, pid)

        # Use all movement to get there or settle
        for _ in range(unit["mov"]):
            if unit["id"] not in self.units or unit["moves_left"] <= 0:
                break
            # Can we settle here? Use same checks as found_city
            terrain = self.tiles.get((unit["q"], unit["r"]))
            too_close = any(hex_distance(c["q"], c["r"], unit["q"], unit["r"]) < 4 for c in self.cities.values())
            # Check foreign city proximity
            near_foreign = any(c["player"] != pid and hex_distance(c["q"], c["r"], unit["q"], unit["r"]) <= max(c.get("border_radius", 1) + 1, 3)
                               for c in self.cities.values())
            in_foreign = self.get_tile_owner(unit["q"], unit["r"]) not in (None, pid)
            if not too_close and not near_foreign and not in_foreign and terrain and terrain not in (Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                player_civ = self.players[pid]["civ"]
                city_names = CITY_NAMES.get(player_civ, [])
                if not city_names:
                    city_names = ["Nova Roma", "Alexandria", "Persepolis", "Kyoto", "Tenochtitlan",
                                  "Constantinople", "Carthage", "Babylon", "Memphis", "Sparta",
                                  "Athens", "Thebes", "Troy", "Corinth", "Delhi",
                                  "Luxor", "Olympia", "Syracuse", "Antioch", "Samarkand"]
                used = {c["name"] for c in self.cities.values()}
                name = next((n for n in city_names if n not in used), f"City {self.next_city_id}")
                self.current_player = pid
                result = self.found_city(unit["id"], name)
                if result.get("ok"):
                    wander_turns = self.turn - unit.get("born_turn", self.turn)
                    self._log_ai(pid, f"SETTLE: founded {name} at ({unit['q']},{unit['r']}) terrain={terrain.value} wandered={wander_turns}t")
                return

            # Timeout: settler wandering too long — force settle
            wander_turns = self.turn - unit.get("born_turn", self.turn)
            if wander_turns >= 10:
                terrain_here = self.tiles.get((unit["q"], unit["r"]))
                too_close = any(hex_distance(c["q"], c["r"], unit["q"], unit["r"]) < 3 for c in self.cities.values())
                in_foreign = self.get_tile_owner(unit["q"], unit["r"]) not in (None, pid)
                if not too_close and not in_foreign and terrain_here and terrain_here not in (Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                    player_civ = self.players[pid]["civ"]
                    city_names = CITY_NAMES.get(player_civ, [])
                    if not city_names:
                        city_names = CITY_NAMES.get("default", [f"City {i}" for i in range(50)])
                    used = {c["name"] for c in self.cities.values()}
                    name = next((n for n in city_names if n not in used), f"City {self.next_city_id}")
                    self.current_player = pid
                    result = self.found_city(unit["id"], name)
                    if result.get("ok"):
                        self._log_ai(pid, f"SETTLE: founded {name} at ({unit['q']},{unit['r']}) terrain={terrain_here.value} wandered={wander_turns}t (TIMEOUT)")
                    return

            if target:
                old_q, old_r = unit["q"], unit["r"]
                self._ai_step_toward(unit, target[0], target[1])
                if unit["q"] == old_q and unit["r"] == old_r:
                    # Stuck — try settling here if possible
                    terrain_here = self.tiles.get((unit["q"], unit["r"]))
                    too_close = any(hex_distance(c["q"], c["r"], unit["q"], unit["r"]) < 3 for c in self.cities.values())
                    in_foreign = self.get_tile_owner(unit["q"], unit["r"]) not in (None, pid)
                    if not too_close and not in_foreign and terrain_here and terrain_here not in (Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                        self._log_ai(pid, f"SETTLER: stuck, settling here instead at ({unit['q']},{unit['r']})")
                    else:
                        neighbors = hex_neighbors(unit["q"], unit["r"])
                        valid = [(nq, nr) for nq, nr in neighbors
                                 if self.tiles.get((nq, nr)) not in (None, Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN)]
                        if valid:
                            nq, nr = random.choice(valid)
                            self.current_player = pid
                            self.move_unit(unit["id"], nq, nr)
                    break
            else:
                break

    def _ai_find_settle_spot(self, origin, pid, exclude_uid=None):
        """Find best settlement location. origin can be unit dict or (q,r) tuple."""
        if isinstance(origin, dict):
            oq, oR = origin["q"], origin["r"]
            exclude_uid = origin.get("id")
        else:
            oq, oR = origin[0], origin[1]
        player = self.players[pid]
        strategy = player.get("strategy", "balanced")
        best = None
        best_score = -999
        for q in range(0, self.width, 2):
            for r in range(0, self.height, 2):
                t = self.tiles.get((q, r))
                if t in (None, Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                    continue
                if any(hex_distance(c["q"], c["r"], q, r) < 5 for c in self.cities.values()):
                    continue
                owner = self.get_tile_owner(q, r)
                if owner is not None and owner != pid:
                    continue
                # Avoid spots where another settler is already heading
                if any(u["player"] == pid and u["type"] == "settler"
                       and (exclude_uid is None or u["id"] != exclude_uid)
                       and hex_distance(u["q"], u["r"], q, r) < 4 for u in self.units.values()):
                    continue
                d = hex_distance(oq, oR, q, r)
                if d > 20:
                    continue
                # Score all tiles in 2-ring radius
                score = 0
                food_total = 0
                for dq in range(-2, 3):
                    for dr in range(-2, 3):
                        if hex_distance(q, r, q + dq, r + dr) > 2:
                            continue
                        nt = self.tiles.get((q + dq, r + dr))
                        if nt and nt not in (Terrain.WATER, Terrain.COAST, Terrain.MOUNTAIN):
                            y = TERRAIN_YIELDS[nt]
                            food_total += y["food"]
                            # Weight: food most important for city growth
                            score += y["food"] * 3 + y["prod"] * 2 + y["gold"]
                # City tile itself
                cy = TERRAIN_YIELDS.get(t, {})
                score += cy.get("food", 0) * 2

                # Strategy preferences
                if strategy == "expansionist" and food_total >= 6:
                    score += 5  # China loves food-rich spots
                # Coastal bonus (for future naval)
                has_coast = any(self.tiles.get((q + dq, r + dr)) in (Terrain.COAST, Terrain.WATER)
                                for dq in range(-1, 2) for dr in range(-1, 2)
                                if hex_distance(q, r, q + dq, r + dr) <= 1)
                if has_coast:
                    score += 3

                score -= d  # Prefer closer
                if score > best_score:
                    best_score = score
                    best = (q, r)
        if best:
            self._log_ai(pid, f"SETTLER: target ({best[0]},{best[1]}) score={best_score} dist={hex_distance(oq,oR,best[0],best[1])}")
        else:
            self._log_ai(pid, f"SETTLER: no good spot from ({oq},{oR})")
        return best

