"""AI diplomacy: valuation, proposal generation, deal evaluation.

Design notes
------------
Valuation is asymmetric — the **receiver** values items 10-25% lower than the
**proposer**. This creates rejections: what the proposer thinks is fair, the
receiver may call lopsided. Opinion softens or sharpens the accept threshold.

Each civ keeps a per-pair cooldown so we don't spam dozens of deals with the
same civ in a row. Strategy-specific templates give different flavour to
aggressive, protective, builder, culturalist, etc.
"""
import random
from civgame.constants import GAME_CONFIG
from civgame.data import TECHNOLOGIES, RESOURCES


# Strategic tech eras ordered roughly from ancient to modern; used for tier scoring.
_ERA_MULT = {
    "Ancient": 1.0, "Classical": 1.2, "Medieval": 1.4, "Renaissance": 1.6,
    "Industrial": 1.8, "Modern": 2.0,
}


class AIDiplomacyMixin:
    # ------------------------------------------------------------------
    # Item valuation (perspective-aware)
    # ------------------------------------------------------------------
    def _ai_value_item(self, item, pid, as_receiver=True):
        """Gold-equivalent value of an item.

        `as_receiver=True` means pid is the one receiving it (typical). When
        we compare deals the receiver's valuation is always used.
        """
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
                return 0
            tdata = TECHNOLOGIES.get(t)
            if not tdata:
                return 0
            if any(p not in player["techs"] for p in tdata["prereqs"]):
                return 0
            # Tier-based value: late-era techs are worth more; modern 2× ancient.
            era_mult = _ERA_MULT.get(tdata.get("era", "Ancient"), 1.0)
            base = tdata["cost"] * era_mult
            # Discount when we're near researching it ourselves
            if player.get("researching") and player["researching"].get("name") == t:
                prog = player["researching"].get("progress", 0)
                ratio = prog / max(1, tdata["cost"])
                base *= max(0.3, 1.0 - ratio)
            return int(base)
        if kind == "map":
            known = len(self.explored.get(pid, set()))
            total = len(self.tiles)
            missing = total - known
            return max(15, min(150, missing // 4))
        if kind == "city":
            cid = item.get("city_id")
            if cid is None:
                return 50
            c = self.cities.get(cid)
            if not c:
                return 0
            return 200 + c["population"] * 50
        if kind == "open_borders":
            civilians = sum(1 for u in self.units.values()
                            if u["player"] == pid and u["type"] in ("scout", "caravan", "spy", "settler"))
            return 25 + civilians * 15
        if kind == "defensive_pact":
            my_mil = sum(1 for u in self.units.values() if u["player"] == pid and u["cat"] != "civilian")
            threats = sum(1 for op in self.players if op["id"] != pid and op["alive"]
                          and self.get_opinion(pid, op["id"]) < -10)
            return 40 + threats * 25 + max(0, 10 - my_mil) * 10
        if kind == "declaration_of_friendship":
            loyalty = player.get("loyalty", 0.5)
            # Aggressive civs value DoF less — they want freedom to war
            agg = player.get("aggression", 0.5)
            return int(70 * loyalty * (1.3 - agg))
        if kind == "research_agreement":
            return 180  # worth a late-era tech eventually
        if kind == "trade_route":
            turns = GAME_CONFIG.get("deal_trade_route_duration", 20)
            return 3 * turns
        if kind == "luxury_trade":
            res = item.get("resource")
            if res and res not in self.get_player_resources(pid):
                turns = GAME_CONFIG.get("deal_luxury_trade_duration",
                                         GAME_CONFIG.get("deal_resource_trade_duration", 20))
                return 8 * turns
            return 5
        if kind == "resource_trade":
            res = item.get("resource")
            if res and res not in self.get_player_resources(pid):
                # Strategic resource: high value if we can now build a tier of units
                turns = GAME_CONFIG.get("deal_resource_trade_duration", 20)
                rdata = RESOURCES.get(res, {}) if res else {}
                mult = 10 if rdata.get("type") == "strategic" else 6
                return mult * turns
            return 15
        if kind == "peace_treaty":
            other_id = item.get("with")
            if other_id is not None:
                rel = player["diplomacy"].get(other_id, "peace")
                if rel == "war":
                    # Desperate value if we're losing
                    my_mil = sum(1 for u in self.units.values()
                                 if u["player"] == pid and u["cat"] != "civilian")
                    their_mil = sum(1 for u in self.units.values()
                                    if u["player"] == other_id and u["cat"] != "civilian")
                    if their_mil > my_mil * 1.3:
                        return 250
                    return 100
            return 0
        if kind == "denounce":
            return -60
        return 0

    def _ai_deal_total(self, items, pid):
        return sum(self._ai_value_item(it, pid) for it in items)

    def _ai_evaluate_deal(self, deal):
        """Return True if offer_to (receiver) would accept.

        The asymmetric multiplier is small (1.08) so symmetric agreements
        (DoF↔DoF, OB↔OB) can still pass — but lopsided gold-for-tech deals
        where proposer overvalues what they're offering will be rejected.

        Human proposers get a small goodwill bonus (+10 opinion equivalent)
        so the player isn't rejected on razor-thin margins.
        """
        receiver = deal["offer_to"]
        proposer = deal["offer_by"]
        gain = self._ai_deal_total(deal["give"], receiver)
        loss = self._ai_deal_total(deal["ask"], receiver)
        # Light asymmetry: receiver thinks own stuff ~8% more valuable.
        loss = int(loss * 1.08)
        # Opinion-weighted threshold: -100 → 1.35×, 0 → 1.0×, +100 → 0.75×
        op = self.get_opinion(receiver, proposer)
        # Human-bonus: players get some goodwill to compensate slower valuation
        if self.players[proposer].get("is_human"):
            op += 10
        threshold = max(0.75, min(1.35, 1.0 - op / 400))
        return gain >= loss * threshold

    # ------------------------------------------------------------------
    # Proposal generation
    # ------------------------------------------------------------------
    def _ai_propose_deals(self, pid):
        if not self.players[pid]["alive"]:
            return
        max_proposals = GAME_CONFIG.get("max_proposals_per_turn", 2)
        made = 0
        player = self.players[pid]
        strategy = player.get("strategy", "balanced")
        aggression = player.get("aggression", 0.5)
        loyalty = player.get("loyalty", 0.5)

        pair_cd = GAME_CONFIG.get("deal_pair_cooldown", 5)
        last_deals = player.setdefault("last_deal_turn", {})
        avoid = set(player.get("avoid_proposals_from", {}).keys())

        others = [p for p in self.players if p["id"] != pid and p["alive"]]
        others.sort(key=lambda p: -self.get_opinion(pid, p["id"]))

        # Denounce loop — runs even if no deals made
        self._ai_maybe_denounce(pid)

        for other in others:
            if made >= max_proposals:
                break
            o_id = other["id"]
            if o_id in avoid:
                continue
            # Pair cooldown
            if self.turn - last_deals.get(o_id, -1000) < pair_cd:
                continue
            # Respect target's "leave me alone" flag
            other_avoid = other.get("avoid_proposals_until", {})
            if other_avoid.get(pid, 0) > self.turn:
                continue
            rel = player["diplomacy"].get(o_id, "peace")
            opinion = self.get_opinion(pid, o_id)

            proposals = self._ai_candidate_deals(pid, o_id, rel, opinion, strategy)
            random.shuffle(proposals)  # vary the order we try templates
            for give, ask, label in proposals:
                if made >= max_proposals:
                    break
                # From proposer's view: what we lose vs gain should roughly balance
                my_loss = self._ai_deal_total(give, pid)
                my_gain = self._ai_deal_total(ask, pid)
                if my_gain < my_loss * 0.9:
                    continue
                # Pre-check: will receiver accept? (We still propose ~15% that
                # wouldn't — realistic trial balloons — unless at_war.)
                pred_deal = {"offer_by": pid, "offer_to": o_id, "give": give, "ask": ask}
                accepts = self._ai_evaluate_deal(pred_deal)
                if not accepts and random.random() > 0.15:
                    continue
                r = self.propose_deal(pid, o_id, give, ask)
                if r.get("ok"):
                    self._log_ai(pid, f"DEAL: proposed to {other['name']}: {label}")
                    made += 1
                    # If AI receiver, decide now
                    if not other.get("is_human"):
                        if self._ai_respond_to_deal(r["deal_id"], o_id):
                            last_deals[o_id] = self.turn

    def _ai_maybe_denounce(self, pid):
        """Aggressive civs publicly denounce very-low-opinion non-war targets."""
        player = self.players[pid]
        aggression = player.get("aggression", 0.5)
        if aggression < 0.6:
            return
        for other in self.players:
            if other["id"] == pid or not other["alive"]:
                continue
            rel = player["diplomacy"].get(other["id"], "peace")
            if rel in ("war", "alliance"):
                continue
            if self.has_active(pid, other["id"], "denounce"):
                continue
            if self.has_active(pid, other["id"], "declaration_of_friendship"):
                continue
            op = self.get_opinion(pid, other["id"])
            if op <= -40 and random.random() < aggression * 0.02:
                # Fire denounce as a one-sided agreement via propose+accept shortcut
                self._create_agreement("denounce", pid, other["id"], {})
                self._log_ai(pid, f"DIPLO: DENOUNCED {other['name']} (opinion={op})")

    def _ai_candidate_deals(self, pid, other, rel, opinion, strategy):
        """Return candidate (give, ask, label) templates filtered by strategy."""
        player = self.players[pid]
        other_p = self.players[other]
        agg = player.get("aggression", 0.5)
        loyalty = player.get("loyalty", 0.5)
        trait = player.get("trait", "")
        cands = []

        # Strength estimate for demand/tribute decisions
        def military(x):
            return sum(1 for u in self.units.values() if u["player"] == x and u["cat"] != "civilian")
        my_mil = military(pid)
        their_mil = military(other)
        stronger = my_mil > their_mil * 1.5 + 2

        # ---- Strategy-gated cooperative templates ----
        coop_ok = rel == "peace"

        # 1. Declaration of Friendship
        # Normal case: loyal non-aggressive civs.
        # Axis case: two aggressive civs (agg >= 0.7) with high opinion also DoF —
        # lets warmonger cabals form ("axis of evil").
        other_agg = other_p.get("aggression", 0.5)
        axis_dof = agg >= 0.7 and other_agg >= 0.7 and opinion >= 15
        if coop_ok and not self.has_active(pid, other, "declaration_of_friendship"):
            if axis_dof or (opinion >= 10 and loyalty >= 0.5 and agg < 0.7):
                label = "axis DoF" if axis_dof else "DoF"
                cands.append(([{"type": "declaration_of_friendship"}],
                              [{"type": "declaration_of_friendship"}], label))

        # 2. Tech swap/sale
        my_techs = set(player["techs"])
        their_techs = set(other_p["techs"])
        want_techs = [t for t in their_techs if t not in my_techs
                       and all(pr in my_techs for pr in TECHNOLOGIES.get(t, {}).get("prereqs", []))]
        offer_techs = [t for t in my_techs if t not in their_techs
                         and all(pr in their_techs for pr in TECHNOLOGIES.get(t, {}).get("prereqs", []))]
        if coop_ok and want_techs and offer_techs:
            want = random.choice(want_techs)
            offer = random.choice(offer_techs)
            cands.append(([{"type": "tech", "name": offer}],
                          [{"type": "tech", "name": want}],
                          f"tech {offer}<->{want}"))
        elif coop_ok and want_techs and player["gold"] > 150:
            want = random.choice(want_techs)
            era_mult = _ERA_MULT.get(TECHNOLOGIES[want].get("era", "Ancient"), 1.0)
            price = int(TECHNOLOGIES[want]["cost"] * era_mult)
            if player["gold"] >= price:
                cands.append(([{"type": "gold", "amount": price}],
                              [{"type": "tech", "name": want}],
                              f"buy tech {want}@{price}g"))

        # 3. Open Borders (everyone who isn't hostile)
        if coop_ok and opinion >= -10 and not self.has_active(pid, other, "open_borders"):
            cands.append(([{"type": "open_borders"}],
                          [{"type": "open_borders"}], "OB swap"))

        # 4. Research Agreement (builder/culturalist/loyal friends)
        if coop_ok and opinion >= 20 and strategy in ("builder", "culturalist", "turtle") \
                and not self.has_active(pid, other, "research_agreement"):
            cost = GAME_CONFIG.get("research_agreement_cost", 200)
            if player["gold"] >= cost and other_p["gold"] >= cost:
                cands.append(([{"type": "gold", "amount": cost},
                               {"type": "research_agreement"}],
                              [{"type": "gold", "amount": cost},
                               {"type": "research_agreement"}],
                              "research agreement"))

        # 5. Defensive Pact (threatened, loyal)
        threats = [p for p in self.players if p["id"] not in (pid, other) and p["alive"]
                   and self.get_opinion(pid, p["id"]) < -20]
        if coop_ok and opinion >= 25 and loyalty >= 0.6 and threats \
                and not self.has_active(pid, other, "defensive_pact"):
            cands.append(([{"type": "defensive_pact"}],
                          [{"type": "defensive_pact"}], "defensive pact"))

        # 6. Luxury swap (culturalist, financial)
        my_res = self.get_player_resources(pid)
        their_res = self.get_player_resources(other)
        my_surplus_lux = [r for r in my_res if RESOURCES.get(r, {}).get("type") == "luxury"
                          and r not in their_res]
        their_surplus_lux = [r for r in their_res if RESOURCES.get(r, {}).get("type") == "luxury"
                             and r not in my_res]
        if coop_ok and my_surplus_lux and their_surplus_lux and strategy != "conqueror":
            mine = random.choice(my_surplus_lux)
            theirs = random.choice(their_surplus_lux)
            cands.append(([{"type": "luxury_trade", "resource": mine}],
                          [{"type": "luxury_trade", "resource": theirs}],
                          f"lux {mine}<->{theirs}"))

        # 7. Strategic resource sale
        my_surplus_str = [r for r in my_res if RESOURCES.get(r, {}).get("type") == "strategic"
                          and r not in their_res and my_res[r] >= 1]
        if coop_ok and my_surplus_str and other_p["gold"] >= 100:
            res = random.choice(my_surplus_str)
            cands.append(([{"type": "resource_trade", "resource": res}],
                          [{"type": "gold", "amount": 150}],
                          f"sell {res}"))

        # 8. Trade Route (economic focus)
        if coop_ok and opinion >= 5 and not self.has_active(pid, other, "trade_route"):
            if strategy in ("builder", "economist", "expansionist") or trait == "financial":
                cands.append(([{"type": "trade_route"}],
                              [{"type": "trade_route"}], "trade route"))

        # ---- Aggressive demands ----
        # 9. Demand tribute (aggressive + stronger target)
        if coop_ok and agg >= 0.6 and stronger and other_p["gold"] >= 80:
            tribute_amt = 5 if their_mil > 1 else 3
            cands.append(([],
                          [{"type": "tribute", "amount": tribute_amt},
                           {"type": "gold", "amount": 50}],
                          f"DEMAND tribute {tribute_amt}g/t + 50g"))

        # 10. Demand tech (very aggressive + stronger)
        if coop_ok and agg >= 0.7 and stronger and want_techs:
            want = random.choice(want_techs)
            cands.append(([],
                          [{"type": "tech", "name": want}],
                          f"DEMAND tech {want}"))

        # 11. Sell strategic resource to enemies-of-enemies
        # (not implemented — would be too complex)

        # ---- Peace/war ----
        if rel == "war":
            # Weaker side sues for peace
            if my_mil < their_mil * 0.7 and player["gold"] > 30:
                pay = min(100, player["gold"] // 2)
                cands.append(([{"type": "gold", "amount": pay},
                               {"type": "peace_treaty", "with": other}],
                              [{"type": "peace_treaty", "with": pid}],
                              f"peace + {pay}g"))
            elif my_mil > their_mil * 1.5 and strategy != "conqueror":
                cands.append(([{"type": "peace_treaty", "with": other}],
                              [{"type": "gold", "amount": 100},
                               {"type": "peace_treaty", "with": pid}],
                              "demand peace + 100g"))

        return cands

    def _ai_respond_to_deal(self, deal_id, pid):
        """AI decides. Returns True if accepted (so caller can update cooldowns)."""
        deal = next((d for d in self.pending_deals if d["id"] == deal_id), None)
        if not deal or deal["offer_to"] != pid:
            return False
        proposer = self.players[deal["offer_by"]]["name"]
        if self._ai_evaluate_deal(deal):
            self._log_ai(pid, f"DEAL: accepted from {proposer}")
            self.accept_deal(deal_id, accepting_pid=pid)
            # Cache accepted-deal turn for receiver too (rate-limit our side)
            self.players[pid].setdefault("last_deal_turn", {})[deal["offer_by"]] = self.turn
            return True
        else:
            self._log_ai(pid, f"DEAL: rejected from {proposer}")
            self.reject_deal(deal_id, rejecting_pid=pid)
            return False
