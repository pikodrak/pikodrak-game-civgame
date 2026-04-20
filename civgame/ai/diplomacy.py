"""AI diplomacy: valuation, proposal generation, deal evaluation.

Every deal item has a gold-equivalent value computed from the proposer's
perspective. A deal is acceptable to the receiver when the value of what
they *receive* is ≥ what they *give*, adjusted by opinion (friends discount
by 10%, enemies require 30% surplus to agree).
"""
import random
from civgame.constants import GAME_CONFIG
from civgame.data import TECHNOLOGIES, RESOURCES


class AIDiplomacyMixin:
    # ------------------------------------------------------------------
    # Item valuation
    # ------------------------------------------------------------------
    def _ai_value_item(self, item, pid, perspective="receive"):
        """Return gold-equivalent value of receiving (or giving away) `item`."""
        player = self.players[pid]
        kind = item["type"]
        if kind == "gold":
            return int(item.get("amount", 0))
        if kind == "gold_per_turn":
            turns = GAME_CONFIG.get("deal_gold_pt_duration", 10)
            return int(item.get("amount", 5)) * turns
        if kind == "tribute":
            turns = GAME_CONFIG.get("deal_tribute_duration", 10)
            return int(item.get("amount", 5)) * turns
        if kind == "tech":
            t = item["name"]
            if t in player["techs"]:
                return 0  # already have
            tdata = TECHNOLOGIES.get(t)
            if not tdata:
                return 0
            # Value scales with tech cost and urgency
            base = tdata["cost"] * 1.5
            if any(p not in player["techs"] for p in tdata["prereqs"]):
                return 0  # can't use without prereqs
            return int(base)
        if kind == "map":
            # Small constant, higher for civs who haven't explored much
            known = len(self.explored.get(pid, set()))
            total = len(self.tiles)
            missing = total - known
            return max(20, min(200, missing // 3))
        if kind == "city":
            cid = item.get("city_id")
            if cid is None:
                return 50
            c = self.cities.get(cid)
            if not c:
                return 0
            return 200 + c["population"] * 50
        if kind == "open_borders":
            # Valuable if you have mobile units and exploration goals
            civilians = sum(1 for u in self.units.values()
                            if u["player"] == pid and u["type"] in ("scout", "caravan", "spy", "settler"))
            return 30 + civilians * 20
        if kind == "defensive_pact":
            # Valuable if we have enemies or weak army
            my_mil = sum(1 for u in self.units.values() if u["player"] == pid and u["cat"] != "civilian")
            threats = sum(1 for op in self.players if op["id"] != pid and op["alive"]
                          and self.get_opinion(pid, op["id"]) < -10)
            return 50 + threats * 30 + max(0, 10 - my_mil) * 15
        if kind == "declaration_of_friendship":
            loyalty = player.get("loyalty", 0.5)
            return int(80 * loyalty)  # 40-80g
        if kind == "research_agreement":
            # Worth a future tech + gold invested
            return 150
        if kind == "trade_route":
            turns = GAME_CONFIG.get("deal_trade_route_duration", 20)
            return 3 * turns  # ~60g
        if kind == "luxury_trade":
            # If we lack this luxury, it's worth +happy
            res = item.get("resource")
            if res and res not in self.get_player_resources(pid):
                turns = GAME_CONFIG.get("deal_luxury_trade_duration",
                                          GAME_CONFIG.get("deal_resource_trade_duration", 20))
                return 10 * turns  # ~200g
            return 10  # duplicate luxury worthless
        if kind == "resource_trade":
            # Strategic resource: value scales with which units we can now build
            res = item.get("resource")
            if res and res not in self.get_player_resources(pid):
                turns = GAME_CONFIG.get("deal_resource_trade_duration", 20)
                return 8 * turns  # ~160g
            return 20
        if kind == "peace_treaty":
            # Only valuable during war
            other_id = item.get("with")
            if other_id is not None:
                rel = player["diplomacy"].get(other_id, "peace")
                if rel == "war":
                    return 150
            return 0
        if kind == "denounce":
            return -50  # cost, not gain (denouncing earns no gold for proposer)
        return 0

    def _ai_deal_total(self, items, pid):
        return sum(self._ai_value_item(it, pid) for it in items)

    def _ai_evaluate_deal(self, deal):
        """Return True if offer_to (the receiver) would accept this deal."""
        receiver = deal["offer_to"]
        proposer = deal["offer_by"]
        # What receiver gains vs what they lose
        gain = self._ai_deal_total(deal["give"], receiver)
        loss = self._ai_deal_total(deal["ask"], receiver)
        # Adjust by opinion
        op = self.get_opinion(receiver, proposer)
        if op >= 30:
            threshold = 0.85  # friends accept 15% unfavourable
        elif op <= -30:
            threshold = 1.30  # enemies demand 30% surplus
        else:
            threshold = 1.00
        return gain >= loss * threshold

    # ------------------------------------------------------------------
    # AI proposal generation
    # ------------------------------------------------------------------
    def _ai_propose_deals(self, pid):
        """Generate up to N proposals this turn aimed at positive-opinion civs."""
        if not self.players[pid]["alive"]:
            return
        max_proposals = GAME_CONFIG.get("max_proposals_per_turn", 2)
        made = 0
        player = self.players[pid]
        strategy = player.get("strategy", "balanced")
        aggression = player.get("aggression", 0.5)
        loyalty = player.get("loyalty", 0.5)

        # Skip civs whose player asked "leave me alone" (flag per player)
        avoid = set(player.get("avoid_proposals_from", {}).keys())

        others = [p for p in self.players if p["id"] != pid and p["alive"]]
        # Prioritize by opinion desc (propose good deals to friends first)
        others.sort(key=lambda p: -self.get_opinion(pid, p["id"]))

        for other in others:
            if made >= max_proposals:
                break
            o_id = other["id"]
            if o_id in avoid:
                continue
            # Skip if avoid window from target applies
            other_avoid = other.get("avoid_proposals_until", {})
            if other_avoid.get(pid, 0) > self.turn:
                continue
            rel = player["diplomacy"].get(o_id, "peace")
            opinion = self.get_opinion(pid, o_id)

            # Try different deal templates based on strategy and opinion
            proposals = self._ai_candidate_deals(pid, o_id, rel, opinion, strategy)
            for give, ask, label in proposals:
                if made >= max_proposals:
                    break
                # Proposer values theirs: what they're giving away shouldn't
                # exceed what they're asking for, by more than 10%.
                my_loss = self._ai_deal_total(give, pid)
                my_gain = self._ai_deal_total(ask, pid)
                if my_gain < my_loss * 0.9:
                    continue  # not worth it to us
                # Check whether receiver would accept (predict)
                pred_deal = {"offer_by": pid, "offer_to": o_id, "give": give, "ask": ask}
                if not self._ai_evaluate_deal(pred_deal):
                    continue
                # Propose
                r = self.propose_deal(pid, o_id, give, ask)
                if r.get("ok"):
                    self._log_ai(pid, f"DEAL: proposed to {other['name']}: {label}")
                    made += 1
                    # If target is AI, they immediately decide
                    if not other.get("is_human"):
                        self._ai_respond_to_deal(r["deal_id"], o_id)

    def _ai_candidate_deals(self, pid, other, rel, opinion, strategy):
        """Yield (give, ask, label) tuples of candidate deals to propose."""
        player = self.players[pid]
        other_p = self.players[other]
        cands = []

        # 1. Declaration of Friendship (if high opinion & not at war)
        if rel == "peace" and opinion >= 10 and not self.has_active(pid, other, "declaration_of_friendship"):
            cands.append(([{"type": "declaration_of_friendship"}],
                          [{"type": "declaration_of_friendship"}], "DoF"))

        # 2. Tech trade — I want a tech they have, they can pay me another tech or gold
        my_techs = set(player["techs"])
        their_techs = set(other_p["techs"])
        want_techs = [t for t in their_techs if t not in my_techs
                       and all(pr in my_techs for pr in TECHNOLOGIES.get(t, {}).get("prereqs", []))]
        offer_techs = [t for t in my_techs if t not in their_techs
                         and all(pr in their_techs for pr in TECHNOLOGIES.get(t, {}).get("prereqs", []))]
        if rel == "peace" and want_techs and offer_techs:
            want = random.choice(want_techs)
            offer = random.choice(offer_techs)
            cands.append(([{"type": "tech", "name": offer}],
                          [{"type": "tech", "name": want}],
                          f"tech {offer}<->{want}"))
        elif rel == "peace" and want_techs and player["gold"] > 100:
            want = random.choice(want_techs)
            price = int(TECHNOLOGIES[want]["cost"] * 1.5)
            if player["gold"] >= price:
                cands.append(([{"type": "gold", "amount": price}],
                              [{"type": "tech", "name": want}],
                              f"buy tech {want}@{price}g"))

        # 3. Open Borders swap
        if rel == "peace" and not self.has_active(pid, other, "open_borders") and opinion >= 0:
            cands.append(([{"type": "open_borders"}],
                          [{"type": "open_borders"}], "OB swap"))

        # 4. Research Agreement (friends only)
        if rel == "peace" and opinion >= 15 and not self.has_active(pid, other, "research_agreement"):
            cost = GAME_CONFIG.get("research_agreement_cost", 100)
            if player["gold"] >= cost and other_p["gold"] >= cost:
                cands.append(([{"type": "gold", "amount": cost},
                               {"type": "research_agreement"}],
                              [{"type": "gold", "amount": cost},
                               {"type": "research_agreement"}],
                              "research agreement"))

        # 5. Defensive Pact (friends with threats)
        threats = [p for p in self.players if p["id"] not in (pid, other) and p["alive"]
                   and self.get_opinion(pid, p["id"]) < -20]
        if rel == "peace" and opinion >= 25 and threats and not self.has_active(pid, other, "defensive_pact"):
            cands.append(([{"type": "defensive_pact"}],
                          [{"type": "defensive_pact"}], "defensive pact"))

        # 6. Luxury/resource trade — asymmetric resource swaps
        my_res = self.get_player_resources(pid)
        their_res = self.get_player_resources(other)
        my_surplus_lux = [r for r in my_res if RESOURCES.get(r, {}).get("type") == "luxury"
                          and r not in their_res]
        their_surplus_lux = [r for r in their_res if RESOURCES.get(r, {}).get("type") == "luxury"
                             and r not in my_res]
        if rel == "peace" and my_surplus_lux and their_surplus_lux:
            mine = random.choice(my_surplus_lux)
            theirs = random.choice(their_surplus_lux)
            cands.append(([{"type": "luxury_trade", "resource": mine}],
                          [{"type": "luxury_trade", "resource": theirs}],
                          f"lux {mine}<->{theirs}"))

        # Strategic resource: I have iron, they lack — offer for gold/gpt
        my_surplus_str = [r for r in my_res if RESOURCES.get(r, {}).get("type") == "strategic"
                          and r not in their_res and my_res[r] >= 1]
        if rel == "peace" and my_surplus_str and other_p["gold"] >= 80:
            res = random.choice(my_surplus_str)
            cands.append(([{"type": "resource_trade", "resource": res}],
                          [{"type": "gold", "amount": 120}],
                          f"sell {res}"))

        # 7. Trade Route (economic civs)
        if rel == "peace" and opinion >= 5 and not self.has_active(pid, other, "trade_route"):
            if strategy in ("builder", "economist") or player.get("trait") == "financial":
                cands.append(([{"type": "trade_route"}],
                              [{"type": "trade_route"}], "trade route"))

        # 8. Peace offer if at war
        if rel == "war":
            my_mil = sum(1 for u in self.units.values() if u["player"] == pid and u["cat"] != "civilian")
            their_mil = sum(1 for u in self.units.values() if u["player"] == other and u["cat"] != "civilian")
            # Weaker side offers peace with tribute
            if my_mil < their_mil * 0.7 and player["gold"] > 30:
                cands.append(([{"type": "gold", "amount": min(100, player["gold"] // 2)},
                               {"type": "peace_treaty", "with": other}],
                              [{"type": "peace_treaty", "with": pid}],
                              "peace + gold"))
            elif my_mil > their_mil * 1.5:
                cands.append(([{"type": "peace_treaty", "with": other}],
                              [{"type": "gold", "amount": 100},
                               {"type": "peace_treaty", "with": pid}],
                              "demand peace + gold"))

        return cands

    def _ai_respond_to_deal(self, deal_id, pid):
        """AI receiver decides on a pending deal immediately."""
        deal = next((d for d in self.pending_deals if d["id"] == deal_id), None)
        if not deal or deal["offer_to"] != pid:
            return
        if self._ai_evaluate_deal(deal):
            proposer = self.players[deal["offer_by"]]["name"]
            self._log_ai(pid, f"DEAL: accepted from {proposer}")
            self.accept_deal(deal_id, accepting_pid=pid)
        else:
            proposer = self.players[deal["offer_by"]]["name"]
            self._log_ai(pid, f"DEAL: rejected from {proposer}")
            self.reject_deal(deal_id, rejecting_pid=pid)
