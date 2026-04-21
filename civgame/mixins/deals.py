"""Deal framework: trade proposals, active agreements, grievances.

A **deal** is a proposed exchange of items. Once accepted, it creates zero or
more **agreements** (duration-based effects like open borders, research
agreement) and applies immediate effects (gold transfer, tech trade).

Items are uniform dicts with a `type` key; see `ITEM_TYPES` below. Deal is
`{"offer_by": pid, "offer_to": pid, "give": [items], "ask": [items], "turn": n}`.
"""
import random
from civgame.constants import GAME_CONFIG
from civgame.data import RESOURCES, TECHNOLOGIES


# Item types a deal may contain. Immediate items apply once; agreement items
# create a record in self.agreements and tick down over turns_left.
IMMEDIATE_TYPES = {"gold", "tech", "map", "city"}
AGREEMENT_TYPES = {"open_borders", "defensive_pact", "declaration_of_friendship",
                   "research_agreement", "trade_route", "resource_trade",
                   "luxury_trade", "gold_per_turn", "tribute", "peace_treaty",
                   "denounce"}
SIGNAL_TYPES = {"demand", "third_party_war", "mediation"}  # one-sided asks


def _duration(kind):
    defaults = {
        "open_borders": 20, "defensive_pact": 30, "declaration_of_friendship": 30,
        "research_agreement": 20, "trade_route": 20, "resource_trade": 20,
        "luxury_trade": 20, "gold_per_turn": 10, "tribute": 10, "denounce": 30,
        "peace_treaty": 20,
    }
    return GAME_CONFIG.get(f"deal_{kind}_duration", defaults.get(kind, 20))


class DealsMixin:
    # ------------------------------------------------------------------
    # Opinion / grievance memory
    # ------------------------------------------------------------------
    def _ensure_memory(self, pid):
        p = self.players[pid]
        if "opinion_modifiers" not in p:
            p["opinion_modifiers"] = []   # [{"source","target","value","expires"}]
        if "memory" not in p:
            p["memory"] = {}              # other_id -> {counters}
        return p

    def _add_opinion(self, pid, target, source, value, turns=None):
        p = self._ensure_memory(pid)
        expires = None if turns is None else self.turn + turns
        # Merge duplicates by source: refresh value/expiry
        for m in p["opinion_modifiers"]:
            if m["target"] == target and m["source"] == source:
                m["value"] = value
                m["expires"] = expires
                return
        p["opinion_modifiers"].append({
            "target": target, "source": source, "value": value, "expires": expires,
        })

    def _bump_memory(self, pid, target, key, delta=1):
        p = self._ensure_memory(pid)
        rec = p["memory"].setdefault(target, {})
        rec[key] = rec.get(key, 0) + delta

    def get_opinion(self, pid, target):
        """Compound opinion score (-100..+100).

        Components:
        - Legacy `relations` score (trade + time drift)
        - Active opinion_modifiers (DoF, denounce, trade boost, broken promise)
        - Persistent memory penalties: broken promises, betrayals, stolen cities
        """
        p = self._ensure_memory(pid)
        base = p.get("relations", {}).get(target, 0)
        mods = sum(m["value"] for m in p["opinion_modifiers"] if m["target"] == target)
        mem = p["memory"].get(target, {})
        # Memory penalties (permanent)
        penalty = (
            mem.get("broken_promises", 0) * -20
            + mem.get("cities_taken_from_me", 0) * -15
            + mem.get("betrayals", 0) * -25
            + mem.get("wars_declared_on_me", 0) * -10
            + mem.get("warmonger_count", 0) * -8     # stigma per war declared on anyone
            + mem.get("trades_completed", 0) * +2    # small long-term bonus
            + mem.get("gifts_received", 0) * +5
        )
        return max(-100, min(100, base + mods + penalty))

    def get_opinion_breakdown(self, pid, target):
        """Human-readable list of reasons affecting opinion for UI tooltips."""
        p = self._ensure_memory(pid)
        out = []
        base = p.get("relations", {}).get(target, 0)
        if base:
            out.append({"source": "past_interactions", "value": base})
        for m in p["opinion_modifiers"]:
            if m["target"] == target:
                out.append({"source": m["source"], "value": m["value"],
                            "expires": m.get("expires")})
        return out

    # ------------------------------------------------------------------
    # Deal proposal / acceptance
    # ------------------------------------------------------------------
    def propose_deal(self, offer_by, offer_to, give, ask):
        """Create a pending deal. Returns {ok, deal_id} or {ok:False, msg}."""
        if offer_by == offer_to:
            return {"ok": False, "msg": "Cannot deal with self"}
        if offer_by >= len(self.players) or offer_to >= len(self.players):
            return {"ok": False, "msg": "Invalid player"}
        # War or cooldown check (peace treaties are allowed even during war)
        rel = self.players[offer_by]["diplomacy"].get(offer_to, "peace")
        is_peace_deal = any(it["type"] == "peace_treaty" for it in give + ask)
        if rel == "war" and not is_peace_deal:
            return {"ok": False, "msg": "Cannot trade while at war"}

        deal_id = self._next_deal_id()
        deal = {
            "id": deal_id,
            "offer_by": offer_by,
            "offer_to": offer_to,
            "give": list(give),
            "ask": list(ask),
            "turn": self.turn,
            "expires": self.turn + 5,  # auto-reject after 5 turns
        }
        self.pending_deals.append(deal)
        return {"ok": True, "deal_id": deal_id}

    def _next_deal_id(self):
        existing = [d["id"] for d in getattr(self, "pending_deals", [])]
        existing += [a.get("id", 0) for a in getattr(self, "agreements", [])]
        return max(existing + [0]) + 1

    def accept_deal(self, deal_id, accepting_pid=None):
        """Apply a deal's effects. Items flow: offer_by's `give` -> offer_to,
        offer_to's `ask` items -> offer_by (so both sides transfer).
        """
        deal = next((d for d in self.pending_deals if d["id"] == deal_id), None)
        if not deal:
            return {"ok": False, "msg": "Deal not found"}
        if accepting_pid is not None and accepting_pid != deal["offer_to"]:
            return {"ok": False, "msg": "Not your deal to accept"}
        a = deal["offer_by"]
        b = deal["offer_to"]
        # Check feasibility before applying
        if not self._deal_feasible(deal):
            self.pending_deals.remove(deal)
            return {"ok": False, "msg": "Deal items no longer available"}
        # Apply each item from a to b (give), then from b to a (ask)
        for item in deal["give"]:
            self._apply_item(item, a, b)
        for item in deal["ask"]:
            self._apply_item(item, b, a)
        # Memory: positive trade boost
        self._add_opinion(a, b, f"trade_{deal_id}", +5, turns=20)
        self._add_opinion(b, a, f"trade_{deal_id}", +5, turns=20)
        self._bump_memory(a, b, "trades_completed")
        self._bump_memory(b, a, "trades_completed")
        self.pending_deals.remove(deal)
        return {"ok": True, "msg": f"Deal {deal_id} completed"}

    def reject_deal(self, deal_id, rejecting_pid=None):
        deal = next((d for d in self.pending_deals if d["id"] == deal_id), None)
        if not deal:
            return {"ok": False, "msg": "Deal not found"}
        if rejecting_pid is not None and rejecting_pid != deal["offer_to"]:
            return {"ok": False, "msg": "Not your deal to reject"}
        # Small opinion hit for proposer
        self._add_opinion(deal["offer_by"], deal["offer_to"], "recent_reject", -2, turns=15)
        self.pending_deals.remove(deal)
        return {"ok": True, "msg": "Rejected"}

    def _deal_feasible(self, deal):
        a, b = deal["offer_by"], deal["offer_to"]
        pa = self.players[a]
        pb = self.players[b]
        for item in deal["give"]:
            if item["type"] == "gold" and pa["gold"] < item["amount"]:
                return False
            if item["type"] == "tech" and item["name"] not in pa["techs"]:
                return False
            if item["type"] == "city":
                if not any(c["id"] == item["city_id"] and c["player"] == a for c in self.cities.values()):
                    return False
        for item in deal["ask"]:
            if item["type"] == "gold" and pb["gold"] < item["amount"]:
                return False
            if item["type"] == "tech" and item["name"] not in pb["techs"]:
                return False
            if item["type"] == "city":
                if not any(c["id"] == item["city_id"] and c["player"] == b for c in self.cities.values()):
                    return False
        return True

    # ------------------------------------------------------------------
    # Item application (source -> dest)
    # ------------------------------------------------------------------
    def _apply_item(self, item, src, dst):
        kind = item["type"]
        p_src = self.players[src]
        p_dst = self.players[dst]
        if kind == "gold":
            amt = int(item["amount"])
            p_src["gold"] -= amt
            p_dst["gold"] += amt
        elif kind == "tech":
            t = item["name"]
            if t in p_src["techs"] and t not in p_dst["techs"]:
                p_dst["techs"].append(t)
        elif kind == "map":
            # Give dst access to src's explored tiles
            src_exp = self.explored.get(src, set())
            self.explored[dst] = self.explored.get(dst, set()) | set(src_exp)
        elif kind == "city":
            cid = item["city_id"]
            if cid in self.cities and self.cities[cid]["player"] == src:
                self.cities[cid]["player"] = dst
                self.cities[cid]["hp"] = min(self.cities[cid]["max_hp"], self.cities[cid]["hp"])
        elif kind in AGREEMENT_TYPES:
            self._create_agreement(kind, src, dst, item)
        # signal types (demand/third_party_war/mediation) handled by AI outside deals

    def _create_agreement(self, kind, src, dst, params):
        """Record a duration-based agreement. src initiated, dst received."""
        ag = {
            "id": self._next_deal_id(),
            "type": kind,
            "players": [src, dst],
            "turns_left": _duration(kind),
            "params": {},
        }
        if kind == "resource_trade":
            ag["params"] = {
                "resource": params.get("resource"),
                "from": src, "to": dst,
                "receivers": [dst],
            }
        elif kind == "luxury_trade":
            ag["params"] = {
                "resource": params.get("resource"),
                "receivers": [src, dst],
            }
        elif kind == "gold_per_turn":
            ag["params"] = {"amount": int(params.get("amount", 5)), "from": src, "to": dst}
        elif kind == "tribute":
            ag["params"] = {"amount": int(params.get("amount", 5)), "from": src, "to": dst}
        elif kind == "research_agreement":
            ag["params"] = {"contributed": {src: 0, dst: 0},
                            "pending_tech": None}
        elif kind == "trade_route":
            ag["params"] = {"bonus": 3}
        elif kind == "denounce":
            ag["params"] = {"by": src, "target": dst}
            # Instant reputation hit
            self._add_opinion(dst, src, f"denounced_us_{ag['id']}", -20, turns=_duration("denounce"))
            # Third parties who dislike dst gain opinion of src
            for p in self.players:
                if p["id"] == src or p["id"] == dst or not p["alive"]:
                    continue
                op = self.get_opinion(p["id"], dst)
                if op < 0:
                    self._add_opinion(p["id"], src, f"shared_denouncer_{ag['id']}", +3, turns=20)
        elif kind == "declaration_of_friendship":
            # Mutual trust boost
            self._add_opinion(src, dst, f"dof_{ag['id']}", +15, turns=_duration("declaration_of_friendship"))
            self._add_opinion(dst, src, f"dof_{ag['id']}", +15, turns=_duration("declaration_of_friendship"))
        elif kind == "peace_treaty":
            # Apply immediate peace (bypasses normal cooldown rejection)
            self.players[src]["diplomacy"][dst] = "peace"
            self.players[dst]["diplomacy"][src] = "peace"
            cd = GAME_CONFIG.get("diplo_peace_cooldown", 15)
            self.players[src].setdefault("diplo_cooldown", {})[dst] = cd
            self.players[dst].setdefault("diplo_cooldown", {})[src] = cd
        self.agreements.append(ag)
        return ag

    # ------------------------------------------------------------------
    # Tick agreements each turn
    # ------------------------------------------------------------------
    def _tick_agreements(self, events):
        """Decrement durations, fire per-turn effects, expire finished ones."""
        remaining = []
        for ag in self.agreements:
            kind = ag["type"]
            a, b = ag["players"]
            # Per-turn effects (run once per agreement per turn — not per player turn).
            # We run this at the end of the whole round (via current_player == 0 tick).
            if kind == "gold_per_turn":
                src = ag["params"]["from"]
                dst = ag["params"]["to"]
                amt = ag["params"]["amount"]
                if self.players[src]["gold"] >= amt:
                    self.players[src]["gold"] -= amt
                    self.players[dst]["gold"] += amt
                else:
                    # Source can't pay → agreement defaults (broken promise)
                    self._bump_memory(dst, src, "broken_promises")
                    self._add_opinion(dst, src, f"broken_gpt_{ag['id']}", -10, turns=30)
                    events.append(f"{self.players[src]['name']} defaulted on gold-per-turn to {self.players[dst]['name']}")
                    continue  # skip append — drop agreement
            elif kind == "tribute":
                src = ag["params"]["from"]
                dst = ag["params"]["to"]
                amt = ag["params"]["amount"]
                if self.players[src]["gold"] >= amt:
                    self.players[src]["gold"] -= amt
                    self.players[dst]["gold"] += amt
                else:
                    # Defaulted — the overlord takes offense
                    self._bump_memory(dst, src, "broken_promises")
                    self._add_opinion(dst, src, f"broken_tribute_{ag['id']}", -20, turns=30)
                    continue
            elif kind == "trade_route":
                bonus = ag["params"].get("bonus", 3)
                self.players[a]["gold"] += bonus
                self.players[b]["gold"] += bonus
            elif kind == "research_agreement":
                # Both contribute a small science each turn; when expired, both get random tech
                for pid in (a, b):
                    ag["params"]["contributed"][pid] = ag["params"]["contributed"].get(pid, 0) + 5

            ag["turns_left"] -= 1
            if ag["turns_left"] <= 0:
                # Finalize: deliver pending effects
                if kind == "research_agreement":
                    pool_a = ag["params"]["contributed"].get(a, 0)
                    pool_b = ag["params"]["contributed"].get(b, 0)
                    if pool_a > 0 and pool_b > 0:
                        self._deliver_research_agreement(a, b, events)
                elif kind in ("declaration_of_friendship", "denounce", "peace_treaty",
                              "defensive_pact", "open_borders", "luxury_trade",
                              "resource_trade", "tribute", "gold_per_turn", "trade_route"):
                    events.append(f"Agreement expired: {kind} between {self.players[a]['name']} and {self.players[b]['name']}")
                continue  # drop
            remaining.append(ag)
        self.agreements = remaining

        # Also expire stale proposals and opinion modifiers
        self.pending_deals = [d for d in self.pending_deals if d.get("expires", 999999) > self.turn]
        for p in self.players:
            if "opinion_modifiers" in p:
                p["opinion_modifiers"] = [m for m in p["opinion_modifiers"]
                                           if m.get("expires") is None or m["expires"] > self.turn]

    def _deliver_research_agreement(self, a, b, events):
        """Grant each side a currently-researchable tech. Capped to one tech
        below Modern era — Industrial techs are allowed (gunpowder chain),
        Modern space-race techs are off-limits.

        20% chance of failure to model research setbacks.
        """
        BLOCKED_ERAS = {"Modern"}  # rocketry, nuclear_fission, space_program, etc.
        for pid in (a, b):
            if random.random() < 0.2:
                events.append(f"{self.players[pid]['name']}: research agreement yielded no breakthrough")
                continue
            player = self.players[pid]
            avail = [t for t, d in TECHNOLOGIES.items()
                     if t not in player["techs"]
                     and d.get("era") not in BLOCKED_ERAS
                     and all(pr in player["techs"] for pr in d["prereqs"])]
            if avail:
                avail.sort(key=lambda t: TECHNOLOGIES[t]["cost"])
                candidates = avail[:3]
                granted = random.choice(candidates)
                player["techs"].append(granted)
                events.append(f"{player['name']} gained {granted} from research agreement")
            else:
                events.append(f"{self.players[pid]['name']}: research agreement yielded no new tech")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def get_active_agreements(self, pid):
        """All active agreements involving player pid."""
        return [ag for ag in self.agreements if pid in ag["players"]]

    def has_active(self, pid, other, kind):
        return any(ag["type"] == kind and pid in ag["players"] and other in ag["players"]
                   for ag in self.agreements)

    def incoming_deals(self, pid):
        return [d for d in self.pending_deals if d["offer_to"] == pid]

    def outgoing_deals(self, pid):
        return [d for d in self.pending_deals if d["offer_by"] == pid]
