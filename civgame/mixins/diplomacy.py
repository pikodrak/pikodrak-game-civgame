"""Diplomacy: war, peace, alliances."""
import random
from civgame.constants import GAME_CONFIG

class DiplomacyMixin:
    def declare_war(self, player_a, player_b):
        # Check cooldown
        cd_a = self.players[player_a].get("diplo_cooldown", {}).get(player_b, 0)
        if cd_a > 0:
            return  # can't change diplomacy yet
        # Track how many wars player_a has started (for peaceful-bloc bonus).
        self.players[player_a]["wars_started"] = self.players[player_a].get("wars_started", 0) + 1
        # Check for betrayal: breaking DoF/alliance to attack?
        rel_before = self.players[player_a]["diplomacy"].get(player_b, "peace")
        was_dof = any(ag["type"] == "declaration_of_friendship"
                      and player_a in ag["players"] and player_b in ag["players"]
                      for ag in getattr(self, "agreements", []))
        if rel_before == "alliance" or was_dof:
            # Record betrayal in both sides' memory
            if hasattr(self, "_bump_memory"):
                self._bump_memory(player_b, player_a, "betrayals")
        # Memory: the victim remembers who declared on them
        if hasattr(self, "_bump_memory"):
            self._bump_memory(player_b, player_a, "wars_declared_on_me")
            # Warmonger stigma is trait-dependent:
            #   peaceful observers (aggression ≤ 0.5): +1 warmonger_count (−8 opinion)
            #   aggressive observers (aggression ≥ 0.7): +1 axis_approval (+5 opinion)
            #   → "axis of evil" naturally forms because aggressive civs respect
            #     each other's conquests while pacifists band together in disgust.
            for p in self.players:
                if p["id"] == player_a or p["id"] == player_b or not p["alive"]:
                    continue
                obs_agg = p.get("aggression", 0.5)
                if obs_agg >= 0.7:
                    self._bump_memory(p["id"], player_a, "axis_approval")
                elif obs_agg <= 0.5:
                    self._bump_memory(p["id"], player_a, "warmonger_count")
        self.players[player_a]["diplomacy"][player_b] = "war"
        self.players[player_b]["diplomacy"][player_a] = "war"
        cd = GAME_CONFIG.get("diplo_war_cooldown", 10)
        self.players[player_a].setdefault("diplo_cooldown", {})[player_b] = cd
        self.players[player_b].setdefault("diplo_cooldown", {})[player_a] = cd
        # Relations drop
        self.players[player_a].setdefault("relations", {})[player_b] = \
            min(-50, self.players[player_a].get("relations", {}).get(player_b, 0) - 50)
        self.players[player_b].setdefault("relations", {})[player_a] = \
            min(-50, self.players[player_b].get("relations", {}).get(player_a, 0) - 50)
        # Alliance auto-war: allies of player_b may join (loyalty-based)
        for p in self.players:
            if p["id"] == player_a or p["id"] == player_b or not p["alive"]:
                continue
            if p["diplomacy"].get(player_b) == "alliance" and p["diplomacy"].get(player_a) != "war":
                # Higher loyalty = more likely to honor alliance (min 50%, max 90%)
                join_chance = min(0.9, 0.5 + p.get("loyalty", 0.5) * 0.4)
                if random.random() < join_chance:
                    p["diplomacy"][player_a] = "war"
                    self.players[player_a]["diplomacy"][p["id"]] = "war"
                    p.setdefault("diplo_cooldown", {})[player_a] = cd
                    self.players[player_a].setdefault("diplo_cooldown", {})[p["id"]] = cd
                    self._log_ai(p["id"], f"ALLIANCE WAR: joined war against {self.players[player_a]['name']} (ally {self.players[player_b]['name']} attacked)")

    def make_peace(self, player_a, player_b):
        # Check cooldown
        cd_a = self.players[player_a].get("diplo_cooldown", {}).get(player_b, 0)
        cd_b = self.players[player_b].get("diplo_cooldown", {}).get(player_a, 0)
        if cd_a > 0 or cd_b > 0:
            return  # can't make peace yet
        self.players[player_a]["diplomacy"][player_b] = "peace"
        self.players[player_b]["diplomacy"][player_a] = "peace"
        cd = GAME_CONFIG.get("diplo_peace_cooldown", 15)
        self.players[player_a].setdefault("diplo_cooldown", {})[player_b] = cd
        self.players[player_b].setdefault("diplo_cooldown", {})[player_a] = cd

    def form_alliance(self, player_a, player_b):
        """Form alliance — mutual free passage + shared vision."""
        # Must be at peace first
        rel_a = self.players[player_a]["diplomacy"].get(player_b, "peace")
        if rel_a == "war":
            return
        self.players[player_a]["diplomacy"][player_b] = "alliance"
        self.players[player_b]["diplomacy"][player_a] = "alliance"

    def break_alliance(self, player_a, player_b):
        """Break alliance — reverts to peace."""
        self.players[player_a]["diplomacy"][player_b] = "peace"
        self.players[player_b]["diplomacy"][player_a] = "peace"
        cd = GAME_CONFIG.get("diplo_peace_cooldown", 15)
        self.players[player_a].setdefault("diplo_cooldown", {})[player_b] = cd
        self.players[player_b].setdefault("diplo_cooldown", {})[player_a] = cd

    # --------------------------------------------------------
    # END TURN
    # --------------------------------------------------------

