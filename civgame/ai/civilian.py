"""AI control of spies and caravans."""
from civgame.hex import hex_neighbors, hex_distance
from civgame.data import TECHNOLOGIES

class AICivilianMixin:
    def _ai_spy_move(self, unit, pid):
        """Move spy toward nearest enemy city."""
        if unit["moves_left"] <= 0:
            return
        # Already in enemy city? Stay put
        for c in self.cities.values():
            if c["player"] != pid and c["q"] == unit["q"] and c["r"] == unit["r"]:
                unit["moves_left"] = 0
                return
        # Move toward nearest enemy city
        enemy_cities = [c for c in self.cities.values() if c["player"] != pid]
        if enemy_cities:
            target = min(enemy_cities, key=lambda c: hex_distance(unit["q"], unit["r"], c["q"], c["r"]))
            for _ in range(unit["mov"]):
                if unit["moves_left"] <= 0 or unit["id"] not in self.units:
                    break
                old_q, old_r = unit["q"], unit["r"]
                self._ai_step_toward(unit, target["q"], target["r"])
                if unit["q"] == old_q and unit["r"] == old_r:
                    break

    def _ai_caravan_move(self, unit, pid):
        """Move caravan toward nearest foreign non-enemy city for trade."""
        if unit["moves_left"] <= 0:
            return
        trade_cities = [c for c in self.cities.values()
                        if c["player"] != pid
                        and self.players[pid]["diplomacy"].get(c["player"], "neutral") != "war"]
        if trade_cities:
            target = min(trade_cities, key=lambda c: hex_distance(unit["q"], unit["r"], c["q"], c["r"]))
            for _ in range(unit["mov"]):
                if unit["moves_left"] <= 0 or unit["id"] not in self.units:
                    break
                old_q, old_r = unit["q"], unit["r"]
                self._ai_step_toward(unit, target["q"], target["r"])
                if unit["q"] == old_q and unit["r"] == old_r:
                    break

