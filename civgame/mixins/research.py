"""Research selection."""
from civgame.data import TECHNOLOGIES

class ResearchMixin:
    def set_research(self, player_id, tech_name):
        """Set current research for a player."""
        if player_id != self.current_player:
            return {"ok": False, "msg": "Not your turn"}

        player = self.players[player_id]

        if tech_name not in TECHNOLOGIES:
            return {"ok": False, "msg": "Unknown technology"}

        tech = TECHNOLOGIES[tech_name]
        if tech_name in player["techs"]:
            return {"ok": False, "msg": "Already researched"}

        for prereq in tech["prereqs"]:
            if prereq not in player["techs"]:
                return {"ok": False, "msg": f"Need prerequisite: {prereq}"}

        player["researching"] = {"name": tech_name, "cost": tech["cost"], "progress": 0}
        return {"ok": True, "msg": f"Researching: {tech_name}"}

