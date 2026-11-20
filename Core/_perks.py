"""The 100 perks from the design and the rules that make them work. A perk only does anything while it is equipped.
The engine calls into Perks at each step of a pull, so the game and the pacing bot share the same perk rules."""
import math
from collections import deque

from _bignum import Big
from _cards import BUFFS, FACE, RANKS, SUITS, VALUE

# name, description, has a downside
PERKS = [
    ("Pulsar Switch", ("Alternating different suits in a row gives 50x. Same suit twice in a row slows pull speed by "
                      "30% for 4 seconds."), True),
    ("Golden Ratio", "Exact ascending ranks (2, 3, 4... Ace) give 1,000x. Breaking the climb takes 8% of your chips.",
     True),
    ("Face Focus", "Every face card or Ace in your last 10 pulls gives +0.4x, stacking.", False),
    ("Even Streak", "3 even ranks in a row gives a permanent +15% chips. An odd rank or face card resets it.", False),
    ("Odd Force", "5 odd ranks in a row spawns 3 duplicate cards. An even rank or face card resets the count.", False),
    ("Suit Flush", "4 different suits in 4 pulls gives 120x on the 4th card.", False),
    ("Royals Charge", "2 face cards in a row make the next number card give 30x.", False),
    ("Crown Rebound", "A King then a 2 gives chips equal to 12% of your balance.", False),
    ("Twin Suit", "A card matching the previous card's suit copies all of its modifiers.", False),
    ("Climb", "Each exact +1 rank in a row adds +4x (stacks).", False),
    ("Drop", "Each exact -1 rank in a row halves the cooldown (stacks up to 4 times).", False),
    ("Full House Surge", "All 4 suits of the same rank within 12 pulls gives 600x.", False),
    ("Bookend Loop", "If the 1st and 5th card of a 5-card set share a rank, the chips from those 5 pulls are squared.",
     False),
    ("Double Strike", "Two identical ranks in a row gives 60x.", False),
    ("Spectrum", "Red, black, red, black gives 80x and clears the debuffs on the table.", False),
    ("Century Mark", "Every 100th card is a guaranteed 800x critical hit.", False),
    ("Ten Count", "Two cards in a row that add up to exactly 10 give 25,000,000,000 chips.", False),
    ("Patience", "After any debuff, the next card gives 45x.", False),
    ("Overdrive", "4 buffed cards within 6 pulls gives +400% chips for 20 seconds.", False),
    ("Aftershock", "When a modifier triggers, it has a 40% chance to trigger one extra time.", False),
    ("Yield", "Every 40th card gives 7% of your current chips.", False),
    ("Market Cap", "Every new highest chip milestone (each new power of ten) adds +800 base chips for good.", False),
    ("Entry Fee", "Cards give 90x, but you lose 15% of the chips they make.", True),
    ("Greed Multiplier", "While you have at least 1 Transcendent Point, all chips x12,000.", False),
    ("Sky Drop", "Every 10th card gives your Transcendent Points x 2,000,000 chips.", False),
    ("Index Stacker", "+1.2% chips for every unique card in your Index.", False),
    ("Rebound Credit", "When your chips would drop below 0, the next 8 cards give 1,200x.", False),
    ("Royal Guard", "King, Queen and Jack as your last 3 cards gives +600% chips.", False),
    ("Gold Touch", "Every 40th card becomes a 1,200x gold card.", False),
    ("Bank Vault", "12% of every buffed card's value is stored. Every 80 pulls it all comes out.", False),
    ("Clean Sweep", "Every debuff that gets removed or avoided by a perk adds +40 base chips for good.", False),
    ("Milestone Wave", "Reaching a new chip scale (1M, 1B, 1T...) gives 40x for 25 seconds.", False),
    ("Safety Net", "If a debuff would take more than 70% of your chips, you keep 55% of your highest balance.", False),
    ("Cashback", "Skill tree purchases refund 60% of their cost.", False),
    ("Collection Bonus", "+0.15x chips for every card in your Index.", False),
    ("Whale", "+15 base chips on every card for each Transcendent Point you hold.", False),
    ("Low Tier Scaling", "Ranks 2 to 5 get a multiplier that grows with the cards you've pulled.", False),
    ("Loaded Odds", "+20% chance for buffs.", False),
    ("Morph", "12% chance a card turns into your highest-paying Index card.", False),
    ("Crit Meter", "4 missed crits in a row force a 600x critical hit on the 5th.", False),
    ("Purge Blast", "A card with a buff and a debuff deletes the debuff and gives 700x.", False),
    ("Jackpot Hour", "Every 45th card makes rare buffs 8x more common for 12 seconds.", False),
    ("Max Output", "Lucky, Banker, Overflow and Jackpot always roll their best.", False),
    ("Chain Crit", "3 critical hits in a row gives 12,000x.", False),
    ("Glitch Value", "1.5% chance for 2,000,000,000,000 chips, but the cooldown doubles for 8 pulls.", True),
    ("Card Lock", "Right-click up to 2 cards on the table to pin them there.", False),
    ("Clean Run", "300 cards with no debuff switches debuffs off for the next 100 pulls.", False),
    ("Wild Power", "Wildcard becomes 12x stronger.", False),
    ("Shockwave", "A card with modifiers pays 40x what the other cards on the table paid.", False),
    ("Flip Luck", "Each debuff has a 45% chance to become a strong buff instead.", False),
    ("Multiplier Wheel", "Every 20th card gives a random multiplier from 15x to 8,000x.", False),
    ("Triple Repeat", "The same rank and suit 3 times in one session makes the 3rd one 1,500x.", False),
    ("Bad Luck Protection", "3 cards with no buff in a row guarantee a buff on the 4th.", False),
    ("Suit Lock", "Pulling a card locks the next 8 pulls to its suit.", True),
    ("Rage Crit", "Taking a debuff gives +30% critical chance for the next 40 pulls.", False),
    ("Ace Maker", "2s have a 25% chance to become Aces.", False),
    ("Suit Banisher", "Once you have 1 Quadrillion chips, you can remove one suit from your deck (Deck page).", False),
    ("Rank Up", "Jacks and Queens have a 35% chance to become Kings or Aces.", False),
    ("Bottom Cut", "Removes ranks 2 to 5 from your deck, but adds 0.08 seconds to the cooldown.", True),
    ("Fusion", "A card with the same rank as the card before it fuses into a 4x version.", False),
    ("Top Stack", "Every 8th card is one of your 3 highest-paying Index cards.", False),
    ("Rainbow Coat", "All cards give +650% chips.", False),
    ("Stone Face", "All cards gain +1,200 base chips.", False),
    ("Echo Shell", "Cards that leave the table leave a ghost that pays 8% of what they paid.", False),
    ("Foil Trim", "Face cards and Aces always crit for 150x.", False),
    ("Felt Multiplier", "Cards that land near the centre of the table give +70%.", False),
    ("Tree Bypass", "All skill tree upgrades cost 55% less.", False),
    ("Rune Inscription", "Aces gain +12,000 base chips.", False),
    ("Suit Scale", "+30% chips for every different suit on the table.", False),
    ("Bounce Multiplier", "Cards give +90% when they land.", False),
    ("Sticker Multiplier", "Every modifier effect on a card is 6x as strong.", False),
    ("Armor Plating", "Immune to Shatter Risk, Brittle, Void and Doom.", False),
    ("Glow Edge", "Each card on the table gives +8% chips.", False),
    ("Red Stamp", "Every 5th card gives 1,200x.", False),
    ("Speed Demon", "Pulling faster than 0.4 seconds apart gives +150 base chips per pull.", False),
    ("High Roller Roulette", "50% chance for 80,000x, 50% chance to lose 18% of your chips.", True),
    ("King Lockdown", "Kings give 2,000,000x but lock pulling for 4 seconds.", True),
    ("High Stakes", "All gains x80, and every chip penalty x80.", True),
    ("Dark Hour", "Every 3 minutes, 12 seconds of 15,000x cards.", False),
    ("Supernova Burst", "Every 100th card gives 150,000x.", False),
    ("Turbo Pull", "Every minute, 8 seconds with no cooldown, but double debuff chance.", True),
    ("Legendary Luck", "Every 3rd card is guaranteed a strong buff.", False),
    ("Void Reversal", "Doom and Void give 15,000x instead of hurting you.", False),
    ("Fast Draw", "Cooldown 85% shorter, but debuff chance 40% higher.", True),
    ("Sacrifice", "Every 200th card spends 55% of your chips to gain Transcendent Points.", True),
    ("Speed Frenzy", "8 fast pulls in a row start 45 seconds of 3x chips.", False),
    ("Ghost Draw", "Every 9th card gives an extra hidden 1,500x payout.", False),
    ("Debuff Payoff", "3 debuffed cards in a row make the next card 2,000,000x.", False),
    ("Ace Focus", "Aces give 150x, but ranks 2 to 5 only give 1 chip.", True),
    ("Triple Zero", "When your chips end in 000, the next card is 1,500x.", False),
    ("Last Chance", "Under 5,000 chips, the next card is 3,000,000x.", False),
    ("Transcend Carryover", ("After Transcending you keep 40% of your last run's best card multiplier as a "
                            "starting multiplier."), False),
    ("Mirror Pull", "8% chance the next card is an exact copy of the one you just pulled.", False),
    ("Soft Reset", "The first 15 cards after Transcending give 25x.", False),
    ("Rank Hammer", "Every 25th card raises its own rank by 2 (an Ace becomes AA).", False),
    ("Suit Storm", "6 cards of the same suit within 8 pulls gives 900x.", False),
    ("Crit Cascade", "A critical hit has a 30% chance to make the next card crit too.", False),
    ("Empty Table", "With 3 or fewer cards on the table, +120% chips.", False),
    ("Full Table", "With 10 or more cards on the table, +180% chips.", False),
    ("Final Gamble", "1% chance any card gives 50,000,000x. 3% chance it takes 25% of your chips instead.", True),
]
NAMES = [p[0] for p in PERKS]
STRONG = ["Final", "Explosive", "Golden", "Jackpot", "Wildcard", "Triple Pay", "Blood", "Overloaded"]
RARE_BUFFS = {b for b, v in BUFFS.items() if v[0] <= 3.5}
RED = {"hearts", "diamonds"}
TABLE_MAX = 24


def rank_i(r):
    return RANKS.index(r) if r in RANKS else 12


def is_face(r):
    return r in FACE


class Perks:
    def __init__(self, engine):
        self.eng = engine
        self.p = engine.p
        self.hist = deque(maxlen=20)        # recent cards: dict(r, suit, buffs, debuffs, crit, val)
        self.table = deque()                # what is on the table (for table perks): [rank, suit, mods, raw chips]
        self.session = {}                   # (rank, suit) -> times seen this session (Triple Repeat)
        self.last_pull_t = -10.0
        self.wait = 0.0                     # extra lock after this pull (King Lockdown)
        self.extra_dups = 0
        self.last_log_mult = 0.0
        self.events = []                    # things the game can show (Spectrum clears the table...)
        self.raw = Big(0)                   # this card's chips before bonus payouts
        self.refresh()

    def refresh(self):
        self.on = {NAMES[i] for i in self.p.equipped if 0 <= i < len(NAMES)}

    @property
    def s(self):
        return self.p.perk_state

    def has(self, name):
        return name in self.on

    def timer(self, name):
        return self.s.get("until", {}).get(name, -1) > self.p.playtime

    def start(self, name, seconds):
        self.s.setdefault("until", {})[name] = self.p.playtime + seconds

    # --- Deck and cooldown ---
    def deck_filter(self, deck):
        if self.has("Bottom Cut"):
            deck = [e for e in deck if e[0] not in ("2", "3", "4", "5")] or deck
        if self.has("Suit Banisher") and self.p.banished:
            deck = [e for e in deck if e[1] != self.p.banished] or deck
        return deck

    def cooldown(self, base):
        if not self.on:
            return base
        f = 1.0
        if self.has("Fast Draw"):
            f *= 0.15
        if self.has("Drop"):
            f *= 0.5 ** min(4, self.s.get("drop", 0))
        if self.has("Pulsar Switch") and self.timer("Pulsar Switch"):
            f /= 0.7
        if self.has("Glitch Value") and self.s.get("glitch_slow", 0) > 0:
            f *= 2
        cd = base * f
        if self.has("Bottom Cut"):
            cd += 0.08
        if self.has("Turbo Pull") and self.p.playtime % 60 < 8:
            cd = 0.0
        return cd

    def take_wait(self):
        w, self.wait = self.wait, 0.0
        return w

    # --- Drawing a card ---
    def draw(self):
        """A forced (rank, suit), or None for a normal draw."""
        if not self.on:
            return None
        s, rng = self.s, self.eng.rng
        n = s.get("n", 0) + 1
        if self.has("Mirror Pull") and self.hist and rng.random() < 0.08:
            h = self.hist[-1]
            s["mirror"] = True
            return h["ranks"][0], h["suit"]
        if self.has("Top Stack") and n % 8 == 0 and self.p.index:
            top = sorted(self.p.index, key=lambda k: Big.from_json(self.p.index[k]), reverse=True)[:3]
            rank, suit = rng.choice(top).split("|")
            if rank in VALUE:
                return rank, suit
        if self.has("Suit Lock") and s.get("lock_left", 0) > 0:
            pool = [e for e in self.eng.deck if e[1] == s.get("lock_suit")]
            if pool:
                return tuple(rng.choice(pool))
        return None

    def alter(self, card):
        if not self.on:
            return
        rng, s = self.eng.rng, self.s
        r = card.ranks[0]
        if self.has("Ace Maker") and r == "2" and rng.random() < 0.25:
            card.ranks = ["A"]
        if self.has("Rank Up") and r in ("J", "Q") and rng.random() < 0.35:
            card.ranks = [rng.choice(("K", "A"))]
        if self.has("Rank Hammer") and (s.get("n", 0) + 1) % 25 == 0:
            r = card.ranks[0]
            two = {"K": "AA", "A": "AAA", "AA": "AAA", "AAA": "AAA"}
            card.ranks = [two.get(r) or RANKS[min(12, rank_i(r) + 2)]]
        if self.has("Morph") and self.p.index and rng.random() < 0.12:
            best = max(self.p.index, key=lambda k: Big.from_json(self.p.index[k]))
            rank, suit = best.split("|")
            if rank in VALUE:
                card.ranks, card.suit = [rank], suit

    def mod_params(self):
        """(extra buff chance, debuff chance factor, force a buff, buff weights or None)"""
        if not self.on:
            return 0.0, 1.0, False, None
        s = self.s
        add = 0.20 if self.has("Loaded Odds") else 0.0
        deb = 1.0
        if self.has("Fast Draw"):
            deb *= 1.4
        if self.has("Turbo Pull") and self.p.playtime % 60 < 8:
            deb *= 2
        if self.has("Clean Run") and s.get("clean_left", 0) > 0:
            deb = 0.0
        force = self.has("Bad Luck Protection") and s.get("no_buff", 0) >= 3
        weights = None
        if self.has("Jackpot Hour") and self.timer("Jackpot Hour"):
            weights = {b: v[0] * (8 if b in RARE_BUFFS else 1) for b, v in BUFFS.items()}
        return add, deb, force, weights

    def after_mods(self, card):
        if not self.on:
            return
        rng, s = self.eng.rng, self.s
        removed = 0
        if s.pop("mirror", False) and self.hist:
            card.buffs, card.debuffs = list(self.hist[-1]["buffs"]), list(self.hist[-1]["debuffs"])
        if self.has("Twin Suit") and self.hist and self.hist[-1]["suit"] == card.suit:
            for b in self.hist[-1]["buffs"]:
                if b not in card.buffs and len(card.buffs) < 5:
                    card.buffs.append(b)
            for d in self.hist[-1]["debuffs"]:
                if d not in card.debuffs and len(card.debuffs) < 5:
                    card.debuffs.append(d)
        if self.has("Legendary Luck") and (s.get("n", 0) + 1) % 3 == 0 and not any(b in STRONG for b in card.buffs):
            card.buffs = (card.buffs + [rng.choice(STRONG)])[-5:]
        if self.has("Flip Luck") and card.debuffs:
            keep = []
            for d in card.debuffs:
                if rng.random() < 0.45:
                    pick = rng.choice([b for b in STRONG if b not in card.buffs] or STRONG)
                    if len(card.buffs) < 5:
                        card.buffs.append(pick)
                    removed += 1
                else:
                    keep.append(d)
            card.debuffs = keep
        if self.has("Armor Plating"):
            before = len(card.debuffs)
            card.debuffs = [d for d in card.debuffs if d not in ("Shatter Risk", "Brittle", "Void", "Doom")]
            removed += before - len(card.debuffs)
        if self.has("Clean Run") and s.get("clean_left", 0) > 0 and card.debuffs:
            removed += len(card.debuffs)
            card.debuffs = []
        s["void_rev"] = 0
        if self.has("Void Reversal"):
            n = sum(1 for d in card.debuffs if d in ("Doom", "Void"))
            if n:
                card.debuffs = [d for d in card.debuffs if d not in ("Doom", "Void")]
                s["void_rev"] = n
        s["purge"] = False
        if self.has("Purge Blast") and card.buffs and card.debuffs:
            removed += len(card.debuffs)
            card.debuffs = []
            s["purge"] = True
        if removed and self.has("Clean Sweep"):
            s["sweep"] = s.get("sweep", 0) + 40 * removed

    def ctx(self, card, ctx):
        if not self.on:
            return
        s, p = self.s, self.p
        base = Big(0)
        if self.has("Stone Face"):
            base = base + 1200
        if self.has("Market Cap"):
            base = base + s.get("mcap", 0)
        if self.has("Clean Sweep"):
            base = base + s.get("sweep", 0)
        if self.has("Whale"):
            base = base + Big(p.tp) * 15
        if self.has("Rune Inscription") and card.ranks[0].startswith("A"):
            base = base + 12000
        if self.has("Speed Demon") and p.playtime - self.last_pull_t < 0.4:
            base = base + 150
        if base:
            ctx["base_bonus"] = ctx["base_bonus"] + base
        if self.has("Rage Crit") and s.get("rage", 0) > 0:
            ctx["crit_chance"] += 0.30
        if self.has("Crit Cascade") and s.get("cascade"):
            ctx["force_crit"] = True
        if self.has("Crit Meter") and s.get("miss", 0) >= 4:
            ctx["force_crit"], ctx["crit_mult"] = True, 600.0
        if self.has("Foil Trim") and (card.is_face() or card.ranks[0].startswith("A")):
            ctx["force_crit"], ctx["crit_mult"] = True, 150.0
        if self.has("Century Mark") and (s.get("n", 0) + 1) % 100 == 0:
            ctx["force_crit"], ctx["crit_mult"] = True, 800.0
        if self.has("Max Output"):
            ctx["max_output"] = True
        if self.has("Sticker Multiplier"):
            ctx["mod_boost"] = 6.0
        if self.has("Wild Power"):
            ctx["wild_power"] = 12.0

    # --- After the card is worked out ---
    def after(self, card, pay, burned):
        """Applies the perk multipliers and extras to a payout. Returns how many extra duplicates to spawn."""
        self.extra_dups = 0
        if not self.on or burned:
            self.last_log_mult = 0.0
            return 0
        s, p, rng = self.s, self.p, self.eng.rng
        n = s.get("n", 0) + 1
        h = list(self.hist)
        r = card.ranks[0]
        ri = rank_i(r)
        prev = h[-1] if h else None
        acc = [0.0]                                       # sum of log10 of every perk multiplier
        ones = False                                      # Ace Focus: low cards pay exactly 1
        flat = Big(0)
        steps = []

        def x(name, m):
            acc[0] += math.log10(m)
            steps.append((name, f"x{Big(m).fmt() if m >= 1e6 else f'{m:g}'}", "mult"))

        on = self.has
        if on("Pulsar Switch") and prev:
            if prev["suit"] == card.suit:
                self.start("Pulsar Switch", 4)
            elif len(h) >= 2 and h[-2]["suit"] != prev["suit"]:
                x("Pulsar Switch", 50)
        if on("Golden Ratio"):
            if prev and ri == rank_i(prev["r"]) + 1:
                s["gr"] = s.get("gr", 1) + 1
                if s["gr"] >= 3:
                    x("Golden Ratio", 1000)
            else:
                if s.get("gr", 1) >= 3:
                    pay.balance_hit = pay.balance_hit + p.balance * 0.08
                    steps.append(("Golden Ratio broken", "-8% of your chips", "debuff"))
                s["gr"] = 1
        if on("Face Focus"):
            k = sum(1 for c in h[-9:] if is_face(c["r"]) or c["r"].startswith("A")) + \
                (card.is_face() or r.startswith("A"))
            if k:
                x("Face Focus", 1 + 0.4 * k)
        if on("Even Streak"):
            if r in ("2", "4", "6", "8", "10"):
                s["even"] = s.get("even", 0) + 1
                if s["even"] >= 3:
                    s["even_bonus"] = s.get("even_bonus", 0) + 0.15
                    s["even"] = 0
            else:
                s["even"] = 0
            if s.get("even_bonus"):
                x("Even Streak", 1 + s["even_bonus"])
        if on("Odd Force"):
            if r in ("3", "5", "7", "9"):
                s["odd"] = s.get("odd", 0) + 1
                if s["odd"] >= 5:
                    self.extra_dups = 3
                    s["odd"] = 0
            else:
                s["odd"] = 0
        if on("Suit Flush") and len(h) >= 3 and len({c["suit"] for c in h[-3:]} | {card.suit}) == 4:
            x("Suit Flush", 120)
        if on("Royals Charge"):
            if s.get("royal") and not card.is_face() and not r.startswith("A"):
                x("Royals Charge", 30)
                s["royal"] = False
            if prev and card.is_face() and is_face(prev["r"]):
                s["royal"] = True
        if on("Crown Rebound") and prev and prev["r"] == "K" and r == "2":
            flat = flat + p.balance * 0.12
            steps.append(("Crown Rebound", "12% of your chips", "chips"))
        if on("Climb"):
            s["climb"] = s.get("climb", 0) + 1 if prev and ri == rank_i(prev["r"]) + 1 else 0
            if s["climb"]:
                x("Climb", 1 + 4 * s["climb"])
        if on("Drop"):
            s["drop"] = s.get("drop", 0) + 1 if prev and ri == rank_i(prev["r"]) - 1 else 0
        if on("Full House Surge"):
            suits = {c["suit"] for c in h[-11:] if c["r"] == r} | {card.suit}
            if len(suits) == 4:
                x("Full House Surge", 600)
        if on("Double Strike") and prev and prev["r"] == r:
            x("Double Strike", 60)
        if on("Spectrum") and len(h) >= 3:
            cols = [c["suit"] in RED for c in h[-3:]] + [card.suit in RED]
            if cols == [True, False, True, False]:
                x("Spectrum", 80)
                self.events.append("spectrum")
        if on("Ten Count") and prev and prev["val"] + card.base_value() == 10:
            flat = flat + Big(25e9)
            steps.append(("Ten Count", "+25B chips", "chips"))
        if on("Patience") and prev and prev["debuffs"]:
            x("Patience", 45)
        if on("Overdrive"):
            if sum(1 for c in h[-5:] if c["buffs"]) + bool(card.buffs) >= 4 and not self.timer("Overdrive"):
                self.start("Overdrive", 20)
            if self.timer("Overdrive"):
                x("Overdrive", 5)
        if on("Aftershock") and pay.triggered:
            extra = sum(1 for _ in range(min(pay.triggered, 10)) if rng.random() < 0.4)
            if extra:
                x("Aftershock", 1.5 ** extra)
        if on("Yield") and n % 40 == 0:
            flat = flat + p.balance * 0.07
            steps.append(("Yield", "7% of your chips", "chips"))
        if on("Entry Fee"):
            x("Entry Fee", 90 * 0.85)
        if on("Greed Multiplier") and p.tp >= 1:
            x("Greed Multiplier", 12000)
        if on("Sky Drop") and n % 10 == 0 and p.tp:
            flat = flat + Big(p.tp) * 2e6
            steps.append(("Sky Drop", "points x 2M", "chips"))
        if on("Index Stacker"):
            x("Index Stacker", 1 + 0.012 * len(p.index))
        if on("Rebound Credit") and s.get("rebound", 0) > 0:
            s["rebound"] -= 1
            x("Rebound Credit", 1200)
        if on("Royal Guard") and len(h) >= 2 and {h[-2]["r"], h[-1]["r"], r} == {"K", "Q", "J"}:
            x("Royal Guard", 7)
        if on("Gold Touch") and n % 40 == 0:
            x("Gold Touch", 1200)
        if on("Milestone Wave") and self.timer("Milestone Wave"):
            x("Milestone Wave", 40)
        if on("Collection Bonus"):
            x("Collection Bonus", 1 + 0.15 * len(p.index))
        if on("Low Tier Scaling") and r in ("2", "3", "4", "5"):
            x("Low Tier Scaling", 1 + p.cards / 500)
        if on("Crit Meter"):
            s["miss"] = 0 if pay.crit else s.get("miss", 0) + 1
        if on("Purge Blast") and s.get("purge"):
            x("Purge Blast", 700)
        if on("Chain Crit"):
            s["chain"] = s.get("chain", 0) + 1 if pay.crit else 0
            if s["chain"] >= 3:
                x("Chain Crit", 12000)
                s["chain"] = 0
        if on("Glitch Value"):
            s["glitch_slow"] = max(0, s.get("glitch_slow", 0) - 1)
            if rng.random() < 0.015:
                flat = flat + Big(2e12)
                s["glitch_slow"] = 8
                steps.append(("Glitch Value", "+2T chips", "chips"))
        if on("Shockwave") and (card.buffs or card.debuffs) and self.table:
            others = Big(0)
            for t in self.table:
                others = others + t[3]
            if others > 0:
                flat = flat + others * 40
                steps.append(("Shockwave", "40x the table", "chips"))
        if on("Multiplier Wheel") and n % 20 == 0:
            x("Multiplier Wheel", round(10 ** rng.uniform(math.log10(15), math.log10(8000))))
        if on("Triple Repeat"):
            k = (r, card.suit)
            self.session[k] = self.session.get(k, 0) + 1
            if self.session[k] >= 3:
                x("Triple Repeat", 1500)
                self.session[k] = 0
        if on("Fusion") and prev and prev["r"] == r:
            x("Fusion", 4)
        if on("Rainbow Coat"):
            x("Rainbow Coat", 7.5)
        if on("Felt Multiplier") and rng.random() < 0.25:
            x("Felt Multiplier", 1.7)
            self.events.append("center")
        if on("Suit Scale"):
            suits = {t[1] for t in self.table} | {card.suit}
            x("Suit Scale", 1 + 0.3 * len(suits))
        if on("Bounce Multiplier"):
            x("Bounce Multiplier", 1.9)
        if on("Glow Edge"):
            x("Glow Edge", 1 + 0.08 * len(self.table))
        if on("Red Stamp") and n % 5 == 0:
            x("Red Stamp", 1200)
        if on("High Roller Roulette"):
            if rng.random() < 0.5:
                x("High Roller Roulette", 80000)
            else:
                pay.balance_hit = pay.balance_hit + p.balance * 0.18
                steps.append(("High Roller Roulette", "-18% of your chips", "debuff"))
        if on("King Lockdown") and r == "K":
            x("King Lockdown", 2e6)
            self.wait = 4.0
        if on("High Stakes"):
            x("High Stakes", 80)
            if pay.balance_hit > 0:
                pay.balance_hit = pay.balance_hit * 80
        if on("Dark Hour") and p.playtime % 180 < 12:
            x("Dark Hour", 15000)
        if on("Supernova Burst") and n % 100 == 0:
            x("Supernova Burst", 150000)
        if on("Void Reversal") and s.get("void_rev"):
            x("Void Reversal", 15000.0 ** s["void_rev"])
        if on("Speed Frenzy"):
            s["fast"] = s.get("fast", 0) + 1 if p.playtime - self.last_pull_t < 0.5 else 0
            if s["fast"] >= 8 and not self.timer("Speed Frenzy"):
                self.start("Speed Frenzy", 45)
                s["fast"] = 0
            if self.timer("Speed Frenzy"):
                x("Speed Frenzy", 3)
        if on("Ghost Draw") and n % 9 == 0 and pay.chips > 0:
            flat = flat + pay.chips * 1500
            steps.append(("Ghost Draw", "hidden 1,500x", "chips"))
        if on("Debuff Payoff"):
            if s.get("payoff"):
                x("Debuff Payoff", 2e6)
                s["payoff"] = False
            s["debuffed"] = s.get("debuffed", 0) + 1 if card.debuffs else 0
            if s["debuffed"] >= 3:
                s["payoff"], s["debuffed"] = True, 0
        if on("Ace Focus"):
            if r.startswith("A"):
                x("Ace Focus", 150)
            elif r in ("2", "3", "4", "5"):
                pay.chips = Big(1)
                ones = True
                steps.append(("Ace Focus", "only 1 chip", "debuff"))
        if on("Triple Zero"):
            if s.get("zero"):
                x("Triple Zero", 1500)
                s["zero"] = False
            b = p.balance
            s["zero"] = (b < 1e15 and int(float(b)) % 1000 == 0 and b > 0) or (b >= 1e15 and rng.random() < 0.001)
        if on("Last Chance") and p.balance < 5000:
            x("Last Chance", 3e6)
        if on("Transcend Carryover") and s.get("carry_mult", 1) > 1:
            x("Transcend Carryover", s["carry_mult"])
        if on("Soft Reset") and s.get("soft", 0) > 0:
            s["soft"] -= 1
            x("Soft Reset", 25)
        if on("Suit Storm") and sum(1 for c in h[-7:] if c["suit"] == card.suit) + 1 >= 6:
            x("Suit Storm", 900)
        if on("Empty Table") and len(self.table) <= 3:
            x("Empty Table", 2.2)
        if on("Full Table") and len(self.table) >= 10:
            x("Full Table", 2.8)
        if on("Final Gamble"):
            roll = rng.random()
            if roll < 0.01:
                x("Final Gamble", 5e7)
            elif roll < 0.04:
                pay.balance_hit = pay.balance_hit + p.balance * 0.25
                steps.append(("Final Gamble", "-25% of your chips", "debuff"))
        # Bank Vault: store 12% of buffed cards, release every 80 pulls
        if on("Bank Vault"):
            if card.buffs and pay.chips > 0:
                s["vault"] = (Big.from_json(s.get("vault", 0)) + pay.chips * 0.12).to_json()
            if n % 80 == 0 and s.get("vault"):
                flat = flat + Big.from_json(s["vault"])
                steps.append(("Bank Vault", "released", "chips"))
                s["vault"] = 0
        # apply
        self.last_log_mult = acc[0]
        if pay.chips > 0 and acc[0] and not ones:
            pay.chips = pay.chips * Big.from_log(acc[0])
        self.raw = pay.chips if pay.chips > 0 else Big(0)  # before bonus payouts: what table perks look at
        if flat > 0:
            pay.chips = pay.chips + flat
        if on("Bookend Loop"):                            # 5-card sets: same rank on the 1st and 5th squares them
            if n % 5 == 1:
                s["book_rank"], s["book_sum"] = r, Big(0).to_json()
            total = Big.from_json(s.get("book_sum", 0)) + self.raw
            s["book_sum"] = total.to_json()
            if n % 5 == 0 and s.get("book_rank") == r and total > 1:
                bonus = total * total - total
                pay.chips = pay.chips + bonus
                pay.steps.append(("Bookend Loop", "5 pulls squared", "mult"))
        if pay.balance_hit > p.balance:
            pay.balance_hit = Big(p.balance)
        if on("Safety Net") and pay.balance_hit > p.balance * 0.7:
            keep = p.highest * 0.55
            pay.balance_hit = max(Big(0), p.balance - keep)
            steps.append(("Safety Net", "kept 55% of your best", "buff"))
        pay.steps.extend(steps)
        return self.extra_dups

    def finish(self, card, pay, burned):
        """Bookkeeping after a pull: history, the table, counters."""
        s, p = self.s, self.p
        if not burned:
            s["n"] = s.get("n", 0) + 1
            self.hist.append({"r": card.ranks[0], "ranks": list(card.ranks), "suit": card.suit,
                              "buffs": list(card.buffs), "debuffs": list(card.debuffs), "crit": pay.crit,
                              "val": card.base_value()})
            if self.on:
                s["no_buff"] = 0 if card.buffs else s.get("no_buff", 0) + 1
                s["clean_count"] = 0 if card.debuffs else s.get("clean_count", 0) + 1
                if s.get("clean_left", 0) > 0:
                    s["clean_left"] -= 1
                elif s["clean_count"] >= 300 and self.has("Clean Run"):
                    s["clean_left"], s["clean_count"] = 100, 0
                if card.debuffs:
                    s["rage"] = 40
                elif s.get("rage", 0) > 0:
                    s["rage"] -= 1
                s["cascade"] = pay.crit and self.eng.rng.random() < 0.3
                if self.has("Suit Lock"):
                    if s.get("lock_left", 0) > 0:
                        s["lock_left"] -= 1
                    else:
                        s["lock_suit"], s["lock_left"] = card.suit, 8
        self.last_pull_t = p.playtime
        raw = self.raw if self.on else (pay.chips if pay.chips > 0 else Big(0))
        self.raw = Big(0)
        self.table.append([card.ranks[0], card.suit, bool(card.buffs or card.debuffs), raw])
        while len(self.table) > TABLE_MAX:
            gone = self.table.popleft()
            if self.has("Echo Shell") and gone[3] > 0:
                ghost = gone[3] * 0.08
                p.balance = p.balance + ghost
                p.lifetime = p.lifetime + ghost
                p.run_earned = p.run_earned + ghost

    def on_bank(self, gained, went_negative):
        if not self.on:
            return
        s, p = self.s, self.p
        if went_negative and self.has("Rebound Credit"):
            s["rebound"] = 8
        if p.highest > 0:
            lg = int(p.highest.log10())
            if self.has("Market Cap") and lg > s.get("mcap_log", -1):
                if s.get("mcap_log", -1) >= 0:
                    s["mcap"] = s.get("mcap", 0) + 800 * (lg - s["mcap_log"])
                s["mcap_log"] = lg
            scale = lg // 3
            if self.has("Milestone Wave") and scale > s.get("scale", 0):
                if s.get("scale", 0) >= 2:
                    self.start("Milestone Wave", 25)
                s["scale"] = scale
        if self.has("Jackpot Hour") and s.get("n", 0) % 45 == 0 and s.get("n", 0):
            self.start("Jackpot Hour", 12)
        if self.has("Sacrifice") and s.get("n", 0) % 200 == 0 and s.get("n", 0) and p.balance > 0:
            import _meta as meta
            spent = p.balance * 0.55
            pts = meta.formula_points(spent, p.tp_k)
            if pts:
                p.balance = p.balance - spent
                p.tp_k += pts
                gain = int(pts * self.eng.meta.tp_mult)
                p.tp += gain
                p.tp_total += gain
                p.tp_lifetime += gain

    def on_transcend(self, best_log_mult):
        s = self.s
        s["soft"] = 15
        s["carry_mult"] = max(1.0, 0.4 * 10 ** min(300.0, best_log_mult))

    def tree_price(self, cost):
        return cost * 0.45 if self.has("Tree Bypass") else cost

    def refund(self, cost):
        return cost * 0.6 if self.has("Cashback") else Big(0)


SUITS_ALL = SUITS
