"""Cards, the 60 modifiers and how a card's payout is worked out (in the order the design asks for:
base value -> additive buffs -> multiplicative buffs -> debuffs)."""
import random
from dataclasses import dataclass, field

from _bignum import Big

# --- Cards ---
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
VALUE = {**{str(n): n for n in range(2, 11)}, "J": 10, "Q": 10, "K": 10, "A": 11, "AA": 22, "AAA": 33}
SUITS = ["hearts", "diamonds", "spades", "clubs"]
SUIT_COLOR = {"hearts": (214, 48, 58), "diamonds": (236, 128, 36), "spades": (28, 26, 34), "clubs": (34, 120, 64)}
FACE = {"J", "Q", "K"}
CRIT_MULT = 2.5
MAX_MODS = 5                    # most buffs (and most debuffs) one card can roll
BASE_BUFF_CHANCE = 0.03
BASE_DEBUFF_CHANCE = 0.005
BASE_CRIT_CHANCE = 0.01

# --- Buffs: name, chance weight (%), what it does, colour, card visual ---
# kind: "add" (+% in the additive step), "mult" (x in the multiplicative step), "special" (handled by name)
BUFFS = {
    "Double Pay": (12.0, "mult", 2.0, "Multiplies this card's chips by 2x", (120, 200, 255)),
    "Triple Pay": (5.0, "mult", 3.0, "Multiplies this card's chips by 3x", (90, 170, 255)),
    "Jackpot": (3.0, "special", 0, "Gives either 4x or 8x chips (50/50)", (255, 205, 70)),
    "Steady": (10.0, "special", 0, "Low cards (2-6) count as rank 8-10", (170, 180, 195)),
    "Greedy": (11.0, "add", 0.60, "Gives +60% chips", (110, 220, 120)),
    "Lucky": (5.5, "special", 0, "Gives between 0.7x and 7x chips at random", (90, 220, 110)),
    "Rich": (10.5, "add", 0.40, "Gives +40% chips", (150, 70, 160)),
    "Golden": (3.5, "mult", 2.5, "Boosts chips by 2.5x", (255, 200, 60)),
    "Echo": (1.8, "special", 0, "Plays the card twice, modifiers included", (150, 160, 255)),
    "Vampire": (2.5, "special", 0, "Base chips +10% of your whole deck's chips", (200, 40, 60)),
    "Explosive": (3.2, "mult", 4.0, "Gives 4x chips", (255, 130, 40)),
    "Safe": (7.5, "special", 0, "Removes all debuffs (except Static), or 1.5x if there are none", (190, 195, 205)),
    "Blood": (2.8, "special", 0, "Gives 5x chips, but the next 3 pulls give 0.5x", (180, 20, 30)),
    "Banker": (2.5, "special", 0, "Gives 0.1x to 9x chips", (120, 190, 140)),
    "Flash": (9.0, "special", 0, "Normal chips, lands almost instantly", (255, 240, 120)),
    "Heavy": (8.5, "add", 0.30, "Gives +30% chips but lands slowly", (140, 130, 120)),
    "Jinx": (6.0, "special", 0, "Normal chips, but the next card gets a debuff", (160, 80, 200)),
    "Blessing": (5.5, "special", 0, "Normal chips, and the next card gets a buff", (255, 240, 200)),
    "Pure": (5.0, "special", 0, "Ignores all debuffs (except Static)", (245, 245, 255)),
    "Tax": (6.5, "add", 0.50, "Gives +50% chips, but takes 5% off the next card", (220, 60, 60)),
    "Wildcard": (1.2, "special", 0, "Counts as 3 of this card; every other modifier on it is 3x as strong",
                 (255, 120, 220)),
    "Crown": (4.0, "special", 0, "Counts as an Ace", (255, 215, 90)),
    "Iron": (10.0, "mult", 1.25, "Gives 1.25x chips", (110, 115, 125)),
    "Overflow": (7.0, "special", 0, "Gives 1.1x to 2x chips", (200, 240, 255)),
    "Shattered": (4.5, "add", 0.40, "Gives +40% chips but always brings a random debuff", (200, 220, 240)),
    "Royal": (6.0, "add", 0.50, "Gives +50% chips", (140, 90, 255)),
    "Cursed": (5.0, "add", 0.60, "Gives +60% chips but brings a random debuff", (60, 40, 70)),
    "Pristine": (8.0, "add", 0.30, "Gives +30% chips with no downside", (235, 245, 255)),
    "Overloaded": (4.0, "add", 0.80, "Gives +80% chips", (255, 140, 30)),
    "Final": (1.0, "mult", 5.0, "Gives 5x chips", (20, 20, 24)),
}

# --- Debuffs: name, chance weight (%), what it does, colour ---
DEBUFFS = {
    "Taxed": (9.0, "Gives 20% fewer chips", (200, 50, 50)),
    "Rust": (4.5, "0.4x chips", (170, 90, 40)),
    "Greed Penalty": (2.5, "Takes 10% of your balance", (210, 40, 40)),
    "Hexed": (1.8, "Gives 0 chips", (90, 40, 120)),
    "Leak": (1.2, "Multiplies chips by -1: you lose what it would have given", (90, 200, 80)),
    "Burn": (5.0, "Burns: the next 5 cards in the deck are skipped (they give nothing)", (230, 90, 30)),
    "Blind": (7.5, "Hides how many chips it gave (check the Index)", (80, 80, 90)),
    "Drain": (5.5, "0.5x chips", (190, 30, 40)),
    "Static": (6.0, "Blocks every bonus: only base chips. Pure and Safe can't remove it", (240, 220, 60)),
    "Shatter Risk": (3.5, "50% chance to break and give 0 chips", (230, 230, 240)),
    "Jinxed": (6.5, "The next card gives half chips", (150, 60, 190)),
    "Weighed Down": (7.0, "Lands slowly", (110, 110, 120)),
    "Void": (3.0, "Turns this card into a 2", (40, 20, 70)),
    "Slow": (5.0, "0.3x to 0.9x chips", (140, 140, 150)),
    "Overcharge": (4.0, "Gives chips, but the next two cards get a debuff", (255, 120, 40)),
    "Silenced": (8.0, "Does literally nothing", (120, 120, 130)),
    "Shrink": (5.5, "Makes the card smaller and gives half chips", (150, 150, 170)),
    "Envy": (1.0, "1% chance to lose half your chips", (60, 200, 90)),
    "Corrosion": (4.0, "The next 3 cards give fewer chips (weaker each time)", (110, 190, 70)),
    "Toll": (3.5, "Costs 3% of your chips up front to pick up", (220, 180, 60)),
    "Fog": (6.0, "Hides rank, suit, modifiers and chips (check the Index)", (225, 228, 235)),
    "Brittle": (3.5, "Doubles every penalty on this card", (190, 220, 245)),
    "Spiked": (5.5, "Normal chips, but the next card gives 0.8x", (150, 150, 160)),
    "Decayed": (4.0, "0.4x chips", (100, 110, 80)),
    "Counterfeit": (1.5, "Gives 0 chips and takes 5% of your balance", (150, 150, 140)),
    "Glitch": (5.0, "50% chance to give 0.8x chips", (90, 255, 230)),
    "Heavy Weight": (6.5, "Takes 2 seconds to pick up", (80, 80, 90)),
    "Shock": (3.5, "Gives chips, but the next 2 cards' buffs are switched off", (80, 160, 255)),
    "Siphon": (2.5, "Takes back half of the previous card's chips", (160, 20, 40)),
    "Doom": (1.5, "0.1x chips", (30, 30, 30)),
}
DEBUFF_FACTOR = {"Taxed": 0.8, "Rust": 0.4, "Hexed": 0.0, "Drain": 0.5, "Shrink": 0.5, "Decayed": 0.4, "Doom": 0.1,
                 "Counterfeit": 0.0}
SLOW_PICKUP = {"Heavy": 1.0, "Weighed Down": 1.3, "Heavy Weight": 2.0}     # extra seconds before the next pull


def weight_share(table, name):
    return table[name][0] / sum(v[0] for v in table.values())


# --- A card ---
@dataclass
class Card:
    ranks: list                    # ["7"], ["A", "5"] (double-ranked), ["AA"], ["AAA"]
    suit: str
    buffs: list = field(default_factory=list)
    debuffs: list = field(default_factory=list)
    crit: bool = False
    dup: bool = False              # a duplicate copy (purple tag)
    rarity: float = 1.0            # chance of this exact modifier set, 0..1

    def label(self):
        return "".join(self.ranks)

    def base_value(self):
        return sum(VALUE[r] for r in self.ranks)

    def is_face(self):
        return any(r in FACE for r in self.ranks)

    def name(self):
        return f"{self.label()} of {self.suit.title()}"

    def copy(self):
        return Card(list(self.ranks), self.suit, list(self.buffs), list(self.debuffs), self.crit, True, self.rarity)

    def to_json(self):
        return {"r": self.ranks, "s": self.suit, "b": self.buffs, "d": self.debuffs, "c": self.crit, "u": self.dup}


def roll_modifiers(card, buff_chance, debuff_chance, rng, forced_buff=False, forced_debuff=False, weights=None):
    """Rolls buffs and debuffs onto a fresh card and works out how rare the result is.
    weights: optional {buff: weight} that replaces the normal buff odds (perks use it)."""
    rarity = 1.0
    picked = []
    buff_chance = min(buff_chance, 0.999)
    table = {k: (weights[k], *v[1:]) for k, v in BUFFS.items()} if weights else BUFFS
    while (forced_buff and not picked) or (len(picked) < MAX_MODS and rng.random() < buff_chance):
        name = weighted(table, picked, rng)
        p = weight_share(table, name)
        rarity *= p if forced_buff and not picked else buff_chance * p
        picked.append(name)
    card.buffs = picked
    bad = []
    must_debuff = forced_debuff or any(b in ("Shattered", "Cursed") for b in picked)
    while (must_debuff and not bad) or (len(bad) < MAX_MODS and rng.random() < debuff_chance):
        name = weighted(DEBUFFS, bad, rng)
        p = weight_share(DEBUFFS, name)
        rarity *= p if must_debuff and not bad else debuff_chance * p
        bad.append(name)
    card.debuffs = bad
    card.rarity = rarity
    return card


def weighted(table, taken, rng):
    names = [n for n in table if n not in taken]
    total = sum(table[n][0] for n in names)
    x = rng.random() * total
    for n in names:
        x -= table[n][0]
        if x <= 0:
            return n
    return names[-1]


# --- Working out a payout ---
@dataclass
class Carry:
    """Effects one card leaves on the next cards."""
    mult: list = field(default_factory=list)       # [factor, cards left, source]
    no_buffs: int = 0                              # Shock
    give_debuff: int = 0                           # Jinx buff, Overcharge
    give_buff: int = 0                             # Blessing
    skip: int = 0                                  # Burn
    last_payout: Big = field(default_factory=Big)

    def to_json(self):
        return {"mult": [[f, n, s] for f, n, s in self.mult], "nb": self.no_buffs, "gd": self.give_debuff,
                "gb": self.give_buff, "sk": self.skip, "lp": self.last_payout.to_json()}

    @staticmethod
    def from_json(d):
        c = Carry()
        c.mult = [list(x) for x in d.get("mult", [])]
        c.no_buffs, c.give_debuff, c.give_buff = d.get("nb", 0), d.get("gd", 0), d.get("gb", 0)
        c.skip = d.get("sk", 0)
        c.last_payout = Big.from_json(d.get("lp", 0))
        return c


@dataclass
class Payout:
    chips: Big                      # added to the balance
    steps: list                     # [(label, text, colour kind)] for the Index breakdown
    balance_hit: Big                # taken straight from the balance (Greed Penalty, Toll...)
    hidden: bool = False            # Blind
    fogged: bool = False            # Fog
    crit: bool = False
    triggered: int = 0              # modifiers that did something
    slow: float = 0.0               # extra seconds before the next pull
    multiplier: float = 1.0         # total multiplier on this card (for records)


def resolve(card, ctx, carry, rng):
    """ctx: dict with balance, base_bonus (Big), crit_chance, chip_mult (float), streak_mult (float),
    deck_total (int). Returns a Payout and updates `carry` for the next cards."""
    steps = []
    buffs = list(card.buffs)
    debuffs = list(card.debuffs)
    hit = Big(0)
    triggered = 0

    if carry.no_buffs > 0 and buffs:                 # Shock from an earlier card
        steps.append(("Shocked", "buffs off", "debuff"))
        buffs = []
    carry.no_buffs = max(0, carry.no_buffs - 1)
    static = "Static" in debuffs
    if not static and ("Pure" in buffs or "Safe" in buffs) and debuffs:
        steps.append(("Pure" if "Pure" in buffs else "Safe", f"removed {len(debuffs)} debuff(s)", "buff"))
        debuffs = []
        triggered += 1

    # 1. Base value
    if "Void" in debuffs:
        base = 2
        steps.append(("Void", "now a 2", "debuff"))
    else:
        base = card.base_value()
        if "Crown" in buffs and not static and base < 11:
            base = 11
            steps.append(("Crown", "counts as an Ace", "buff"))
        if "Steady" in buffs and not static and base <= 6:
            base = rng.choice((8, 9, 10))
            steps.append(("Steady", f"counts as {base}", "buff"))
    value = Big(base) + ctx.get("base_bonus", Big(0))
    if "Vampire" in buffs and not static:
        value = value + 0.1 * ctx.get("deck_total", 380)
        steps.append(("Vampire", f"+{0.1 * ctx.get('deck_total', 380):.0f}", "chips"))
    steps.insert(0, ("Card value", value.fmt(), "chips"))
    if static:
        steps.append(("Static", "base chips only", "debuff"))
        carry.last_payout = value
        return Payout(value, steps, hit, triggered=triggered + 1)

    wild = "Wildcard" in buffs
    wild_x = 3.0 * ctx.get("wild_power", 1.0)
    boost = (wild_x if wild else 1.0) * ctx.get("mod_boost", 1.0)   # Wildcard makes every other modifier 3x as strong
    top = ctx.get("max_output", False)                 # perk: random modifiers always roll their best

    # 2. Additive buffs
    add = 0.0
    for b in buffs:
        _w, kind, amount, *_ = BUFFS[b]
        if kind == "add":
            add += amount * boost
            triggered += 1
    if add:
        value = value * (1 + add)
        steps.append(("Bonus", f"+{add * 100:.0f}%", "buff"))

    # 3. Multiplicative buffs
    mult = 1.0
    for b in buffs:
        _w, kind, amount, *_ = BUFFS[b]
        m = None
        if kind == "mult":
            m = amount
        elif b == "Jackpot":
            m = 8.0 if top else rng.choice((4.0, 8.0))
        elif b == "Lucky":
            m = 7.0 if top else rng.uniform(0.7, 7.0)
        elif b == "Banker":
            m = 9.0 if top else rng.uniform(0.1, 9.0)
        elif b == "Overflow":
            m = 2.0 if top else rng.uniform(1.1, 2.0)
        elif b == "Blood":
            m = 5.0
            carry.mult.append([0.5, 3, "Blood"])
        elif b == "Safe" and not card.debuffs:
            m = 1.5
        if m is not None:
            m = 1 + (m - 1) * boost
            mult *= m
            triggered += 1
            steps.append((b, f"x{m:.2f}".rstrip("0").rstrip("."), "mult"))
    if wild:
        mult *= wild_x
        steps.append(("Wildcard", f"x{wild_x:g} (counts as {wild_x:g} cards)", "mult"))
        triggered += 1
    if "Tax" in buffs:
        carry.mult.append([0.95, 1, "Tax"])
    if "Jinx" in buffs:
        carry.give_debuff += 1
        triggered += 1
    if "Blessing" in buffs:
        carry.give_buff += 1
        triggered += 1
    value = value * mult

    crit = ctx.get("force_crit", False) or rng.random() < ctx.get("crit_chance", BASE_CRIT_CHANCE)
    if crit:
        value = value * ctx.get("crit_mult", CRIT_MULT)
        steps.append(("Critical hit", f"x{ctx.get('crit_mult', CRIT_MULT):g}", "crit"))
    streak = ctx.get("streak_mult", 1.0)
    if streak != 1.0:
        value = value * streak
        steps.append(("Streak", f"x{streak.fmt()}" if isinstance(streak, Big) else f"x{streak:.3g}", "streak"))
    chip_mult = ctx.get("chip_mult", 1.0)
    if chip_mult != 1.0:
        value = value * chip_mult
        steps.append(("Chip multiplier", f"x{chip_mult:.3g}", "mult"))
    if "Echo" in buffs:
        value = value * 2
        steps.append(("Echo", "played twice", "buff"))
        triggered += 1

    # 4. Debuffs (and penalties carried from earlier cards)
    brittle = "Brittle" in debuffs
    for entry in carry.mult:
        factor, _left, source = entry
        value = value * factor
        steps.append((source, f"x{factor:g} (from an earlier card)", "debuff"))
        entry[1] -= 1
    carry.mult = [e for e in carry.mult if e[1] > 0]

    def penalty(factor):
        return max(0.0, 1 - 2 * (1 - factor)) if brittle and 0 <= factor < 1 else factor

    balance = ctx.get("balance", Big(0))
    for d in debuffs:
        f = None
        if d in DEBUFF_FACTOR:
            f = DEBUFF_FACTOR[d]
        elif d == "Leak":
            f = -2.0 if brittle else -1.0
        elif d == "Slow":
            f = rng.uniform(0.3, 0.9)
        elif d == "Shatter Risk":
            f = 0.0 if rng.random() < 0.5 else 1.0
        elif d == "Glitch":
            f = 0.8 if rng.random() < 0.5 else 1.0
        if f is not None:
            f = penalty(f)
            value = value * f
            steps.append((d, f"x{f:.2f}".rstrip("0").rstrip("."), "debuff"))
            triggered += 1
        take = None
        if d == "Greed Penalty":
            take = 0.10
        elif d == "Counterfeit":
            take = 0.05
        elif d == "Toll":
            take = 0.03
        elif d == "Envy" and rng.random() < 0.01:
            take = 0.5
        if take is not None and balance > 0:
            take = min(1.0, take * (2 if brittle else 1))
            amount = balance * take
            hit = hit + amount
            steps.append((d, f"-{take * 100:.0f}% of your chips", "debuff"))
            triggered += 1
        if d == "Siphon" and carry.last_payout > 0:
            amount = carry.last_payout * (1.0 if brittle else 0.5)
            hit = hit + amount
            steps.append(("Siphon", f"-{amount.fmt()} (half the last card)", "debuff"))
            triggered += 1
        if d == "Jinxed":
            carry.mult.append([0.5, 1, "Jinxed"])
        elif d == "Spiked":
            carry.mult.append([0.8, 1, "Spiked"])
        elif d == "Corrosion":
            carry.mult.extend([[0.7, 1, "Corrosion"], [0.8, 2, "Corrosion"], [0.9, 3, "Corrosion"]])
        elif d == "Overcharge":
            carry.give_debuff += 2
        elif d == "Shock":
            carry.no_buffs = 2
        elif d == "Burn":
            carry.skip = 5
    slow = sum(SLOW_PICKUP.get(n, 0) for n in buffs + debuffs)
    if "Flash" in buffs:
        slow = 0.0
    carry.last_payout = value if value > 0 else Big(0)
    final_mult = float(value / Big(base)) if base and abs(value.log10()) < 300 else 0.0
    return Payout(value, steps, hit, hidden="Blind" in debuffs, fogged="Fog" in debuffs, crit=crit,
                  triggered=triggered, slow=slow, multiplier=final_mult)


def new_rng(seed=None):
    return random.Random(seed)
