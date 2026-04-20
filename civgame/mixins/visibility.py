"""Tile ownership and fog of war."""
from civgame.hex import hex_neighbors, hex_distance
from civgame.constants import Terrain

class VisibilityMixin:
    def get_tile_owner(self, q, r):
        """Return player_id who owns this tile. City hex always belongs to city owner.
        Contested tiles: higher culture/distance wins."""
        # City hex always belongs to city owner
        for c in self.cities.values():
            if c["q"] == q and c["r"] == r:
                return c["player"]
        # Other tiles: culture pressure
        best_owner = None
        best_score = -1
        for c in self.cities.values():
            br = c.get("border_radius", 1)
            dist = hex_distance(c["q"], c["r"], q, r)
            if dist <= br:
                culture = c.get("culture", 0) + 1
                score = culture / max(1, dist)
                if score > best_score:
                    best_score = score
                    best_owner = c["player"]
        return best_owner

    # --------------------------------------------------------
    # VISIBILITY / FOG OF WAR
    # --------------------------------------------------------

    def get_visible_tiles(self, player_id):
        """Return set of (q,r) currently visible to player."""
        visible = set()
        sight = 2

        for u in self.units.values():
            if u["player"] == player_id:
                for dq in range(-sight-1, sight+2):
                    for dr in range(-sight-1, sight+2):
                        tq, tr = u["q"] + dq, u["r"] + dr
                        if hex_distance(u["q"], u["r"], tq, tr) <= sight:
                            if 0 <= tq < self.width and 0 <= tr < self.height:
                                visible.add((tq, tr))

        for c in self.cities.values():
            if c["player"] == player_id:
                br = c.get("border_radius", 1) + 1  # see 1 beyond borders
                for dq in range(-br - 1, br + 2):
                    for dr in range(-br - 1, br + 2):
                        tq, tr = c["q"] + dq, c["r"] + dr
                        if hex_distance(c["q"], c["r"], tq, tr) <= br:
                            if 0 <= tq < self.width and 0 <= tr < self.height:
                                visible.add((tq, tr))

        # Update explored memory
        if player_id in self.explored:
            self.explored[player_id].update(visible)

        return visible

    # --------------------------------------------------------
    # ACTIONS
    # --------------------------------------------------------

