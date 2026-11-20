"""Infinideck's rules with no drawing: a profile, pulling a card with every skill tree effect, and banking the
payout. The game and the pacing bot both use this, so tests measure the real thing."""
import math
import random
import time

import _achievements as ach
import _meta as meta
import _perks as perks
import _tree as tree
from _bignum import Big
from _cards import (
    BASE_DEBUFF_CHANCE,
    CRIT_MULT,
    RANKS,
    SUITS,
    VALUE,
    Card,
    Carry,
    resolve,
    roll_modifiers,
)

# --- Settings ---
BASE_COOLDOWN = 1 / 3
STREAK_CAP = 4                  # a same-rank streak multiplies for at most 4 repeats in a row (x18^4 at most)
NEXT_RANK = {**{r: RANKS[i + 1] for i, r in enumerate(RANKS[:-1])}, "A": "AA", "AA": "AAA", "AAA": "AAA"}


# --- One profile's progress ---
class Profile:
    def __init__(self, slot):
        self.slot = slot
        self.balance = Big(0)
        self.tp = 0
        self.tp_total = 0
        self.lifetime = Big(0)
        self.highest = Big(0)
        self.best_card = Big(0)
        self.spent = Big(0)
        self.cards = 0
        self.crits = 0
        self.mod_hits = 0
        self.dups = 0
        self.rank_ups = 0
        self.longest_streak = 0
        self.longest_clean = 0
        self.playtime = 0.0
        self.transcends = 0
        self.shatters = 0
        self.index = {}             # "A|spades" -> best payout seen (Big json)
        self.recent = []            # newest first
        self.rarest = []
        self.payouts = []           # the cards that paid the most, biggest first
        self.tutorial_done = False
        self.tree_tip_done = False
        self.carry = Carry()
        self.deck = [[r, s] for s in SUITS for r in RANKS]
        self.bought = {"root"}
        self.last_rank = None
        self.same_count = 0
        self.clean = 0
        self.deck_bought = {"droot"}
        self.t_bought = {"troot"}
        self.removal_on = set()       # Rank Removal nodes that are switched on
        self.start_picks = []         # Main tree upgrades granted free each run
        self.deck_style = "classic"
        self.run_earned = Big(0)      # chips earned since the last Transcend
        self.tp_k = 0                 # points earned from the Transcend formula (its K)
        self.op_cost = {}             # deck page action -> next price (Big json), fixed after the first buy
        self.tp_spent = 0
        self.tp_lifetime = 0          # every point ever earned (never reset, even by a Shatter)
        self.perks_owned = []         # perk numbers (index into perks.PERKS); duplicates allowed
        self.equipped = []
        self.perk_slots = 1
        self.perk_cap = 5             # how many perks you can hold
        self.perk_req = 5             # perks needed for the next slot sacrifice
        self.sacrifices = 0
        self.perk_state = {}          # counters the perks keep
        self.banished = None          # Suit Banisher's removed suit
        self.ach = {}                 # achievement tracking stats
        self.achievements = []        # unlocked achievement names, in order
        self.created = time.time()

    def index_base(self):
        """The base cards (single rank) found so far."""
        return {k for k in self.index if k.split("|")[0] in RANKS}

    def to_json(self):
        return {"v": 3, "balance": self.balance.to_json(), "tp": self.tp, "tp_total": self.tp_total,
                "lifetime": self.lifetime.to_json(), "highest": self.highest.to_json(),
                "best_card": self.best_card.to_json(), "spent": self.spent.to_json(), "cards": self.cards,
                "crits": self.crits, "mod_hits": self.mod_hits, "dups": self.dups, "rank_ups": self.rank_ups,
                "longest_streak": self.longest_streak, "longest_clean": self.longest_clean,
                "playtime": self.playtime, "transcends": self.transcends, "shatters": self.shatters,
                "index": self.index, "recent": self.recent[:50], "rarest": self.rarest[:50], "payouts": self.payouts[:50],
                "tutorial_done": self.tutorial_done, "tree_tip_done": self.tree_tip_done,
                "carry": self.carry.to_json(), "deck": self.deck, "bought": sorted(self.bought),
                "last_rank": self.last_rank, "same_count": self.same_count, "clean": self.clean,
                "deck_bought": sorted(self.deck_bought), "t_bought": sorted(self.t_bought),
                "removal_on": sorted(self.removal_on), "start_picks": self.start_picks,
                "deck_style": self.deck_style, "run_earned": self.run_earned.to_json(), "tp_k": self.tp_k,
                "op_cost": self.op_cost, "tp_spent": self.tp_spent, "tp_lifetime": self.tp_lifetime,
                "perks_owned": self.perks_owned, "equipped": self.equipped, "perk_slots": self.perk_slots,
                "perk_cap": self.perk_cap, "perk_req": self.perk_req, "sacrifices": self.sacrifices,
                "perk_state": self.perk_state, "banished": self.banished, "ach": self.ach,
                "achievements": self.achievements,
                "created": self.created, "saved": time.time()}

    @staticmethod
    def from_json(slot, d):
        p = Profile(slot)
        if not d:
            return p
        for k in ("balance", "lifetime", "highest", "best_card", "spent", "run_earned"):
            setattr(p, k, Big.from_json(d.get(k, 0)))
        for k in ("tp", "tp_total", "cards", "crits", "mod_hits", "dups", "rank_ups", "longest_streak",
                  "longest_clean", "playtime", "transcends", "shatters", "tutorial_done", "tree_tip_done",
                  "created", "last_rank", "same_count", "clean", "deck_style", "tp_k", "tp_spent", "tp_lifetime",
                  "perks_owned", "equipped", "perk_slots", "perk_cap", "perk_req", "sacrifices", "perk_state",
                  "banished", "ach", "achievements"):
            setattr(p, k, d.get(k, getattr(p, k)))
        p.index = d.get("index", {})
        p.recent = d.get("recent", [])
        p.rarest = d.get("rarest", [])
        p.payouts = d.get("payouts", [])
        p.carry = Carry.from_json(d.get("carry", {}))
        p.deck = d.get("deck", p.deck)
        p.bought = tree.upgrade_ids(set(d.get("bought", [])) | {"root"})   # older saves: same count per path
        p.bought &= set(tree.NODES)                     # ignore nodes that no longer exist
        p.deck_bought = (set(d.get("deck_bought", [])) | {"droot"}) & set(meta.DECK_NODES)
        p.t_bought = (set(d.get("t_bought", [])) | {"troot"}) & set(meta.T_NODES)
        p.removal_on = set(d.get("removal_on", [])) & p.t_bought
        old_picks = d.get("start_picks", [])
        if any(n not in tree.NODES for n in old_picks):
            old_picks = sorted(tree.upgrade_ids(set(old_picks)) - {"root"}, key=lambda n: tree.NODES[n].k)
        p.start_picks = [n for n in old_picks if n in tree.NODES]
        p.op_cost = d.get("op_cost", {})
        return p


class Result:
    __slots__ = ("burned", "card", "center", "payout", "ranked_up")

    def __init__(self, card, payout, burned=False, ranked_up=False):
        self.card, self.payout, self.burned, self.ranked_up = card, payout, burned, ranked_up
        self.center = False                 # Felt Multiplier: this card landed near the centre


# --- The rules ---
class Engine:
    def __init__(self, profile, rng=None):
        self.p = profile
        self.rng = rng or random.Random()
        self.unlocked = []                  # achievements unlocked since the game last looked
        self.perks = perks.Perks(self)
        self.refresh()
        if "run_start" not in self.p.ach:
            ach.new_run(self.p)

    def refresh(self):
        """Call after buying upgrades or changing the deck."""
        self.st = tree.Stats(self.p.bought)
        self.meta = meta.MetaStats(self.p)
        if hasattr(self, "perks"):
            self.perks.refresh()
            self.deck = self.perks.deck_filter(meta.effective_deck(self.p, self.meta))
        else:
            self.deck = meta.effective_deck(self.p, self.meta)
        bias = tree.RANK_BIAS * self.st.rank_s
        self.weights = [math.exp(bias * RANKS.index(r)) for r, _ in self.deck]
        self.aces = [e for e in self.deck if e[0] == "A"]
        self.ranks_in_deck = {r for r, _ in self.deck}
        self.deck_total = sum(VALUE[r] for r, _ in self.deck)
        m = self.meta
        self.global_mult = self.st.chip_mult * m.deck_mult * m.tp_chip_mult * m.value_mult * (1 + m.index_bonus)

    def cooldown(self):
        return self.perks.cooldown(BASE_COOLDOWN / (self.st.speed * self.meta.speed_mult))

    def tick(self, dt):
        """Play time moves on (perk timers and achievements use it)."""
        self.p.playtime += dt

    def check_achievements(self):
        got = ach.check(self.p, self)
        self.unlocked.extend(got)
        return got

    # --- Buying ---
    def tab_of(self, nid):
        if nid in tree.NODES:
            return tree.NODES, self.p.bought
        if nid in meta.DECK_NODES:
            return meta.DECK_NODES, self.p.deck_bought
        return meta.T_NODES, self.p.t_bought

    def price(self, nid):
        nodes, _ = self.tab_of(nid)
        n = nodes[nid]
        return n.cost if n.cur == "tp" else self.perks.tree_price(n.cost)

    def can_afford(self, nid):
        nodes, _ = self.tab_of(nid)
        n = nodes[nid]
        return self.p.tp >= int(n.cost) if n.cur == "tp" else self.p.balance >= self.price(nid)

    def can_buy(self, nid):
        nodes, bought = self.tab_of(nid)
        return meta.available(nodes, nid, bought) and self.can_afford(nid)

    def buy(self, nid):
        if not self.can_buy(nid):
            return False
        nodes, bought = self.tab_of(nid)
        n = nodes[nid]
        if n.cur == "tp":
            self.p.tp -= int(n.cost)
            self.p.tp_spent += int(n.cost)
        else:
            cost = self.price(nid)
            self.p.balance = self.p.balance - cost + self.perks.refund(cost)
            self.p.spent = self.p.spent + cost
        bought.add(nid)
        if nid in meta.T_NODES and meta.T_NODES[nid].path == 0:
            self.p.removal_on.add(nid)
        self.refresh()
        self.track_buy(nid, nodes, bought)
        return True

    def buy_all(self, nodes):
        """Automation's Buy All: buys every affordable upgrade in one tab, cheapest first, until none are left.
        Returns how many it bought."""
        bought_set = self.tab_of(next(iter(nodes)))[1]
        got = 0
        while True:
            ready = [nid for nid in nodes if meta.available(nodes, nid, bought_set) and self.can_afford(nid)]
            if not ready:
                return got
            nid = min(ready, key=self.price)
            if not self.buy(nid):
                return got
            got += 1

    def track_buy(self, nid, nodes, bought):
        a = self.p.ach
        a["buys"] = a.get("buys", 0) + 1
        a["run_buys"] = a.get("run_buys", 0) + 1
        n = nodes[nid]
        if nodes is tree.NODES:
            key = tree.PATHS[n.path][0]
            if key == "mult":
                a["mult_bought"] = True
                a["run_mult"] = True
            if key == "speed":
                a["run_speed"] = True
            if key in ("same", "clean") and n.kind != "first":
                a["loop"] = True
        if nodes is meta.T_NODES:
            a["t_bought"] = True
        if len(bought) == len(nodes):
            a["tab_maxed"] = True
            if nodes is meta.T_NODES:
                a["t_maxed"] = True
        if self.all_maxed():
            if not a.get("all_maxed"):
                a["last_upgrade"] = True
            a["all_maxed"] = True
        self.check_achievements()

    def all_maxed(self):
        p = self.p
        return (len(p.bought) == len(tree.NODES) and len(p.deck_bought) == len(meta.DECK_NODES)
                and len(p.t_bought) == len(meta.T_NODES))

    # --- Perks and Shattering ---
    def can_shatter(self):
        return self.all_maxed() and len(self.p.perks_owned) < self.p.perk_cap

    def shatter(self):
        """Gives up every tree, chips and points for one random perk (the odds can't be changed)."""
        if not self.can_shatter():
            return None
        p, a = self.p, self.p.ach
        if p.balance >= 1e15:
            a["shatter_rich"] = True
        times = [x for x in a.get("shatter_times", []) if p.playtime - x <= 600]
        if times:
            a["fast_shatter"] = True
        a["shatter_times"] = (times + [p.playtime])[-5:]
        if "The End?" in p.achievements:
            a["after_end"] = True
        perk = self.rng.randrange(len(perks.PERKS))
        p.perks_owned.append(perk)
        p.shatters += 1
        p.balance = Big(0)
        p.run_earned = Big(0)
        p.bought, p.deck_bought, p.t_bought = {"root"}, {"droot"}, {"troot"}
        p.removal_on, p.start_picks = set(), []
        p.tp = p.tp_total = p.tp_k = 0
        p.deck = [[r, s] for s in SUITS for r in RANKS]
        p.deck_style, p.op_cost, p.banished = "classic", {}, None
        p.carry = Carry()
        p.last_rank, p.same_count, p.clean = None, 0, 0
        ach.new_run(p)
        self.refresh()
        self.check_achievements()
        return perk

    def can_sacrifice(self):
        p = self.p
        return p.sacrifices < 5 and len(p.perks_owned) - len(p.equipped) >= p.perk_req

    def sacrifice(self):
        """Gives up every perk (and everything else) for one more slot and a bigger perk inventory."""
        if not self.can_sacrifice():
            return False
        p = self.p
        p.sacrifices += 1
        p.perk_slots = 5 if p.perk_req >= 80 else min(5, p.perk_slots + 1)
        p.perk_cap *= 2
        p.perk_req *= 2
        p.perks_owned, p.equipped, p.perk_state = [], [], {}
        p.balance = Big(0)
        p.run_earned = Big(0)
        p.bought, p.deck_bought, p.t_bought = {"root"}, {"droot"}, {"troot"}
        p.removal_on, p.start_picks = set(), []
        p.tp = p.tp_total = p.tp_k = 0
        p.deck = [[r, s] for s in SUITS for r in RANKS]
        p.deck_style, p.op_cost, p.banished = "classic", {}, None
        p.carry = Carry()
        ach.new_run(p)
        self.refresh()
        self.check_achievements()
        return True

    def toggle_equip(self, perk):
        """Equips an owned perk into the next free slot, or takes it off. Returns True if something changed."""
        p, a = self.p, self.p.ach
        if perk in p.equipped:
            p.equipped.remove(perk)
        elif perk in p.perks_owned and len(p.equipped) < p.perk_slots:
            p.equipped.append(perk)
            a["equipped"] = True
            if perks.PERKS[perk][2]:
                a["equip_negative"] = True
        else:
            return False
        if len(p.equipped) == 5:
            bad = [perks.PERKS[i][2] for i in p.equipped]
            if not any(bad):
                a["five_good"] = True
            if all(bad):
                a["five_bad"] = True
        self.refresh()
        self.check_achievements()
        return True

    # --- Transcending ---
    def transcend_points(self):
        return meta.points_for(self.p, self.meta)

    def transcend(self):
        """Resets this run for Transcendent Points. Keeps decks, the Transcend tree, the Index and stats."""
        base, gain = self.transcend_points()
        if not base:
            return 0
        p, a = self.p, self.p.ach
        if not a.get("run_mult"):
            a["no_mult_run"] = True
        if not a.get("run_speed"):
            a["no_speed_run"] = True
        self.perks.on_transcend(a.get("run_best_log", 0.0))
        p.tp_k += base
        p.tp += gain
        p.tp_total += gain
        p.tp_lifetime += gain
        p.transcends += 1
        ach.new_run(p)
        p.balance = Big(0)
        p.run_earned = Big(0)
        p.carry = Carry()
        p.last_rank, p.same_count, p.clean = None, 0, 0
        self.refresh()
        self.grant_start()
        return gain

    def grant_start(self):
        """Gives this run's free starting upgrades (only ones whose prerequisites are picked too)."""
        p = self.p
        picks = p.start_picks[:self.meta.start_slots]
        p.bought = meta.valid_start(picks)
        if len(p.bought) > 1:
            p.ach["start_pick"] = True
        self.refresh()
        self.check_achievements()

    # --- Pulling ---
    def draw_rank(self):
        p, rng = self.p, self.rng
        if self.st.same_on and p.last_rank in self.ranks_in_deck and rng.random() < self.st.repeat:
            return p.last_rank, rng.choice(SUITS)
        if self.st.all_aces and self.aces:
            return tuple(rng.choice(self.aces))
        return tuple(rng.choices(self.deck, self.weights)[0])

    def pull(self):
        """Pulls one card (plus any duplicates). Returns a list of Results; the first is the real card."""
        p, st, rng = self.p, self.st, self.rng
        carry = p.carry
        pk = self.perks
        forced = pk.draw()
        rank, suit = forced or self.draw_rank()
        card = Card([rank], suit)
        ranked_up = rng.random() < st.rankup
        if ranked_up:
            card.ranks = [NEXT_RANK[rank]]
        pk.alter(card)
        if self.meta.double and rng.random() < self.meta.double:
            second = rng.choices(self.deck, self.weights)[0][0]
            first = card.ranks[0]
            if first == "AA":
                card.ranks = ["AAA"]
            elif first == "A" and second == "A":
                card.ranks = ["AA"]
            elif first != "AAA":
                card.ranks = [first, second]
        forced_buff, forced_debuff = carry.give_buff > 0, carry.give_debuff > 0
        carry.give_buff = max(0, carry.give_buff - 1)
        carry.give_debuff = max(0, carry.give_debuff - 1)
        p_add, p_deb, p_force, p_weights = pk.mod_params()
        roll_modifiers(card, st.buff_chance + self.meta.buff_add + p_add,
                       BASE_DEBUFF_CHANCE * self.meta.debuff_scale * p_deb, rng, forced_buff or p_force, forced_debuff,
                       p_weights)
        pk.after_mods(card)
        burned = carry.skip > 0
        if burned:
            carry.skip -= 1
            card.buffs, card.debuffs = [], []
        streak = Big(1)
        clean = 1.0
        if not burned:
            p.same_count = p.same_count + 1 if rank == p.last_rank else 1
            p.last_rank = rank
            p.longest_streak = max(p.longest_streak, p.same_count)
            p.clean = 0 if card.debuffs else p.clean + 1
            p.longest_clean = max(p.longest_clean, p.clean)
            if st.same_on and p.same_count >= 2:                       # every repeat multiplies again (up to 8)
                streak = Big(st.same_mult) ** min(p.same_count - 1, STREAK_CAP)
            if st.clean_on and p.clean > 0:
                clean = 1 + (st.clean_mult - 1) * p.clean               # x1.01 per card = +1% per card in a row
        mult = self.global_mult
        if card.is_face():
            mult *= self.meta.face_mult
        if any(r.startswith("A") for r in card.ranks):
            mult *= self.meta.ace_mult
        ctx = {"balance": p.balance, "base_bonus": st.base_bonus, "crit_chance": st.crit_chance,
               "crit_mult": CRIT_MULT + self.meta.crit_dmg, "chip_mult": mult,
               "streak_mult": streak if streak != 1 else 1.0, "clean_mult": clean, "deck_total": self.deck_total}
        pk.ctx(card, ctx)
        dup_chance = st.dup_chance + self.meta.dup_add
        before = Carry.from_json(carry.to_json()) if not burned and dup_chance else None
        payout = resolve(card, ctx, carry, rng)
        if burned:
            payout.chips = Big(0)
            payout.balance_hit = Big(0)
            payout.steps = [("Burned", "skipped by Burn", "debuff")]
        card.crit = payout.crit
        extra = pk.after(card, payout, burned)
        pk.finish(card, payout, burned)
        main = Result(card, payout, burned, ranked_up)
        if "center" in pk.events:
            main.center = True
            pk.events.remove("center")
        out = [main]
        if extra and not burned:                             # Odd Force: exact copies
            for _ in range(extra):
                c = card.copy()
                pay = resolve(c, ctx, Carry(), rng)
                c.crit = pay.crit
                out.append(Result(c, pay))
        if before is not None and rng.random() < dup_chance:
            copies = 2 + min(3, int(rng.random() ** (1 / (1 + 2 * st.dup_power)) * 4))
            for _ in range(copies):
                c = card.copy()
                c.crit = False
                pay = resolve(c, ctx, Carry.from_json(before.to_json()), rng)
                c.crit = pay.crit
                out.append(Result(c, pay))
        return out

    def bank(self, res, record=True):
        """Adds one result's chips to the balance and the stats. Returns the chips gained."""
        p, card, pay = self.p, res.card, res.payout
        p.cards += 1
        p.crits += pay.crit
        p.mod_hits += pay.triggered
        p.dups += card.dup
        p.rank_ups += res.ranked_up and not card.dup
        gained = pay.chips
        high_before, best_before = Big(p.highest), Big(p.best_card)
        p.balance = p.balance + gained - pay.balance_hit
        went_negative = p.balance < 0
        if went_negative:
            p.balance = Big(0)
        if gained > 0:
            p.lifetime = p.lifetime + gained
            p.run_earned = p.run_earned + gained
        if p.balance > p.highest:
            p.highest = Big(p.balance)
        if gained > p.best_card:
            p.best_card = Big(gained)
        self.perks.on_bank(gained, went_negative)
        ach.on_card(p, res, gained, self, high_before, best_before)
        if p.cards % 25 == 0 or gained > high_before:
            self.check_achievements()
        if res.burned:
            return gained
        key = f"{card.label()}|{card.suit}"
        best = p.index.get(key)
        if best is None or gained > Big.from_json(best):
            p.index[key] = gained.to_json()
        if not record:
            return gained
        entry = {"card": card.to_json(), "chips": gained.to_json(), "steps": pay.steps, "rarity": card.rarity,
                 "hit": pay.balance_hit.to_json(), "t": time.time(), "hidden": pay.hidden or pay.fogged}
        p.recent.insert(0, entry)
        del p.recent[50:]
        if gained > 0 and not entry["hidden"] and (
                len(p.payouts) < 50 or gained > Big.from_json(p.payouts[-1]["chips"])):
            p.payouts.append(entry)
            p.payouts.sort(key=lambda e: Big.from_json(e["chips"]), reverse=True)
            del p.payouts[50:]
        if card.buffs or card.debuffs:
            p.rarest.append(entry)
            p.rarest.sort(key=lambda e: e["rarity"])
            del p.rarest[50:]
        return gained
