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
    "Double Pay": (12.0, "mult", 5.0, "x5 chips", (120, 200, 255)),
    "Triple Pay": (5.0, "mult", 12.0, "x12 chips", (90, 170, 255)),
    "Jackpot": (3.0, "special", 0, "Either x10 or x30 chips (50/50)", (255, 205, 70)),
    "Steady": (10.0, "special", 0, "A low card (2 to 6) is worth 10 instead, and the card pays x3", (170, 180, 195)),
    "Greedy": (11.0, "add", 3.00, "+300% chips", (110, 220, 120)),
    "Lucky": (5.5, "special", 0, "A random x2 to x25 chips", (90, 220, 110)),
    "Rich": (10.5, "add", 2.50, "+250% chips", (150, 70, 160)),
    "Golden": (3.5, "mult", 8.0, "x8 chips", (255, 200, 60)),
    "Echo": (1.8, "special", 0, "The card pays 4 times (x4 chips)", (150, 160, 255)),
    "Vampire": (2.5, "special", 0, "Adds the value of your whole deck to this card, then x3 chips", (200, 40, 60)),
    "Explosive": (3.2, "mult", 15.0, "x15 chips", (255, 130, 40)),
    "Safe": (7.5, "special", 0, "Removes every debuff on the card, then x3 chips (x6 if it had none)",
             (190, 195, 205)),
    "Blood": (2.8, "special", 0, "x25 chips, but your next 3 cards pay x0.75", (180, 20, 30)),
    "Banker": (2.5, "special", 0, "A random x1 to x40 chips", (120, 190, 140)),
    "Flash": (9.0, "special", 0, "x3 chips, lands instantly and you can pull again straight away", (255, 240, 120)),
    "Heavy": (8.5, "add", 4.00, "+400% chips, but lands a little slower", (140, 130, 120)),
    "Jinx": (6.0, "special", 0, "x6 chips, but your next card gets a debuff", (160, 80, 200)),
    "Blessing": (5.5, "special", 0, "x3 chips, and your next 2 cards each get a buff", (255, 240, 200)),
    "Pure": (5.0, "special", 0, "Ignores every debuff on the card, then x4 chips", (245, 245, 255)),
    "Tax": (6.5, "add", 4.00, "+400% chips, but your next card pays x0.95", (220, 60, 60)),
    "Wildcard": (1.2, "special", 0, "x5 chips, and every other modifier on the card is 3 times as strong",
                 (255, 120, 220)),
    "Crown": (4.0, "special", 0, "The card is worth as much as an Ace (11), then x4 chips", (255, 215, 90)),
    "Iron": (10.0, "mult", 3.0, "x3 chips", (110, 115, 125)),
    "Overflow": (7.0, "special", 0, "A random x2 to x10 chips", (200, 240, 255)),
    "Shattered": (4.5, "add", 6.00, "+600% chips, but always brings a random debuff", (200, 220, 240)),
    "Royal": (6.0, "add", 3.50, "+350% chips", (140, 90, 255)),
    "Cursed": (5.0, "add", 8.00, "+800% chips, but always brings a random debuff", (60, 40, 70)),
    "Pristine": (8.0, "add", 2.00, "+200% chips, no downside", (235, 245, 255)),
    "Overloaded": (4.0, "add", 5.00, "+500% chips", (255, 140, 30)),
    "Final": (1.0, "mult", 50.0, "x50 chips", (20, 20, 24)),
}

# --- Debuffs: name, chance weight (%), what it does, colour ---
DEBUFFS = {
    "Taxed": (9.0, "x0.9 chips (10% less)", (200, 50, 50)),
    "Rust": (4.5, "x0.6 chips", (170, 90, 40)),
    "Greed Penalty": (2.5, "Takes 3% of the chips you have", (210, 40, 40)),
    "Hexed": (1.8, "x0.2 chips", (90, 40, 120)),
    "Leak": (1.2, "Instead of paying, you lose half of what it would have paid", (90, 200, 80)),
    "Burn": (5.0, "Your next 3 cards are burned and pay nothing", (230, 90, 30)),
    "Blind": (7.5, "Hides how many chips it paid (you still get them; see the Index)", (80, 80, 90)),
    "Drain": (5.5, "x0.7 chips", (190, 30, 40)),
    "Static": (6.0, "Switches off this card's buffs (your upgrades still count). Pure and Safe can't remove it",
               (240, 220, 60)),
    "Shatter Risk": (3.5, "25% chance the card breaks and pays nothing", (230, 230, 240)),
    "Jinxed": (6.5, "Your next card pays x0.75", (150, 60, 190)),
    "Weighed Down": (7.0, "Lands slowly (you wait 0.4 s longer)", (110, 110, 120)),
    "Void": (3.0, "The card is worth 5, whatever its rank", (40, 20, 70)),
    "Slow": (5.0, "A random x0.6 to x1 chips", (140, 140, 150)),
    "Overcharge": (4.0, "Pays normally, but your next card gets a debuff", (255, 120, 40)),
    "Silenced": (8.0, "Does nothing at all", (120, 120, 130)),
    "Shrink": (5.5, "The card shrinks and pays x0.75", (150, 150, 170)),
    "Envy": (1.0, "1% chance to lose 10% of the chips you have", (60, 200, 90)),
    "Corrosion": (4.0, "Your next 3 cards pay a little less (x0.85, x0.9, x0.95)", (110, 190, 70)),
    "Toll": (3.5, "Costs 1% of the chips you have", (220, 180, 60)),
    "Fog": (6.0, "Hides the card's rank, suit, modifiers and chips (you still get them)", (225, 228, 235)),
    "Brittle": (3.5, "Every other penalty on this card is 1.5 times as bad", (190, 220, 245)),
    "Spiked": (5.5, "Pays normally, but your next card pays x0.9", (150, 150, 160)),
    "Decayed": (4.0, "x0.6 chips", (100, 110, 80)),
    "Counterfeit": (1.5, "x0.3 chips, and takes 1% of the chips you have", (150, 150, 140)),
    "Glitch": (5.0, "50% chance of x0.9 chips", (90, 255, 230)),
    "Heavy Weight": (6.5, "You wait 0.8 s longer before the next pull", (80, 80, 90)),
    "Shock": (3.5, "Pays normally, but your next card's buffs are switched off", (80, 160, 255)),
    "Siphon": (2.5, "Takes back a quarter of what your last card paid", (160, 20, 40)),
    "Doom": (1.5, "x0.3 chips", (30, 30, 30)),
}
DEBUFF_FACTOR = {"Taxed": 0.9, "Rust": 0.6, "Hexed": 0.2, "Drain": 0.7, "Shrink": 0.75, "Decayed": 0.6, "Doom": 0.3,
                 "Counterfeit": 0.3}
SLOW_PICKUP = {"Heavy": 0.3, "Weighed Down": 0.4, "Heavy Weight": 0.8}     # extra seconds before the next pull
BUFF_MULT = {"Flash": 3.0, "Jinx": 6.0, "Blessing": 3.0, "Pure": 4.0, "Crown": 4.0, "Steady": 3.0, "Vampire": 3.0,
             "Blood": 25.0}                                                 # specials that also multiply


def mod_info(name):
    """What a modifier does, in plain words (for tooltips everywhere)."""
    if name in BUFFS:
        return BUFFS[name][3]
    if name in DEBUFFS:
        return DEBUFFS[name][1]
    return ""


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
        steps.append(("Shocked", "buffs switched off", "debuff"))
        buffs = []
    carry.no_buffs = max(0, carry.no_buffs - 1)
    static = "Static" in debuffs
    if static and buffs:
        steps.append(("Static", "buffs switched off", "debuff"))
        buffs = []
    if ("Pure" in buffs or "Safe" in buffs) and debuffs:
        kept = ["Static"] if static else []
        steps.append(("Pure" if "Pure" in buffs else "Safe", f"removed {len(debuffs) - len(kept)} debuff(s)", "buff"))
        debuffs = kept
        triggered += 1

    # 1. Base value
    if "Void" in debuffs:
        base = 5
        steps.append(("Void", f"{card.label()} is now worth 5", "debuff"))
    else:
        base = card.base_value()
        if "Crown" in buffs and base < 11:
            steps.append(("Crown", f"{card.label()} is now worth 11 (an Ace)", "buff"))
            base = 11
        if "Steady" in buffs and base <= 6:
            steps.append(("Steady", f"{card.label()} is now worth 10", "buff"))
            base = 10
    value = Big(base) + ctx.get("base_bonus", Big(0))
    if "Vampire" in buffs:
        value = value + ctx.get("deck_total", 380)
        steps.append(("Vampire", f"+{ctx.get('deck_total', 380):,} (your deck's value)", "chips"))
    steps.insert(0, ("Card value", value.fmt(), "chips"))

    wild = "Wildcard" in buffs
    wild_x = 5.0 * ctx.get("wild_power", 1.0)
    boost = (3.0 * ctx.get("wild_power", 1.0) if wild else 1.0) * ctx.get("mod_boost", 1.0)  # Wildcard: others 3x
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
            m = 30.0 if top else rng.choice((10.0, 30.0))
        elif b == "Lucky":
            m = 25.0 if top else rng.uniform(2.0, 25.0)
        elif b == "Banker":
            m = 40.0 if top else rng.uniform(1.0, 40.0)
        elif b == "Overflow":
            m = 10.0 if top else rng.uniform(2.0, 10.0)
        elif b == "Blood":
            m = BUFF_MULT[b]
            carry.mult.append([0.75, 3, "Blood"])
        elif b == "Safe":
            m = 6.0 if not card.debuffs else 3.0
        elif b == "Echo":
            m = 4.0
        elif b in BUFF_MULT:
            m = BUFF_MULT[b]
        if m is not None:
            m = 1 + (m - 1) * boost
            mult *= m
            triggered += 1
            steps.append((b, f"x{m:.2f}".rstrip("0").rstrip("."), "mult"))
    if wild:
        mult *= wild_x
        steps.append(("Wildcard", f"x{wild_x:g}", "mult"))
        triggered += 1
    if "Tax" in buffs:
        carry.mult.append([0.95, 1, "Tax"])
    if "Jinx" in buffs:
        carry.give_debuff += 1
    if "Blessing" in buffs:
        carry.give_buff += 2
    value = value * mult

    crit = ctx.get("force_crit", False) or rng.random() < ctx.get("crit_chance", BASE_CRIT_CHANCE)
    if crit:
        value = value * ctx.get("crit_mult", CRIT_MULT)
        steps.append(("Critical hit", f"x{ctx.get('crit_mult', CRIT_MULT):g}", "crit"))
    streak = ctx.get("streak_mult", 1.0)
    if streak != 1.0:
        value = value * streak
        steps.append(("Same-rank streak", f"x{streak.fmt()}" if isinstance(streak, Big) else f"x{streak:.3g}",
                      "streak"))
    clean = ctx.get("clean_mult", 1.0)
    if clean != 1.0:
        value = value * clean
        steps.append(("No-debuff streak", f"x{clean.fmt()}" if isinstance(clean, Big) else f"x{clean:.3g}", "streak"))
    chip_mult = ctx.get("chip_mult", 1.0)
    if chip_mult != 1.0:
        value = value * chip_mult
        steps.append(("Upgrades and decks", f"x{Big(chip_mult).fmt()}" if chip_mult >= 1e6 else f"x{chip_mult:.3g}",
                      "mult"))

    # 4. Debuffs (and penalties carried from earlier cards)
    brittle = "Brittle" in debuffs
    for entry in carry.mult:
        factor, _left, source = entry
        value = value * factor
        steps.append((source, f"x{factor:g} (from an earlier card)", "debuff"))
        entry[1] -= 1
    carry.mult = [e for e in carry.mult if e[1] > 0]

    def penalty(factor):
        return max(0.0, 1 - 1.5 * (1 - factor)) if brittle and 0 <= factor < 1 else factor

    balance = ctx.get("balance", Big(0))
    for d in debuffs:
        f = None
        if d in DEBUFF_FACTOR:
            f = DEBUFF_FACTOR[d]
        elif d == "Leak":
            f = -0.75 if brittle else -0.5
        elif d == "Slow":
            f = rng.uniform(0.6, 1.0)
        elif d == "Shatter Risk":
            f = 0.0 if rng.random() < 0.25 else 1.0
        elif d == "Glitch":
            f = 0.9 if rng.random() < 0.5 else 1.0
        if f is not None:
            f = penalty(f)
            value = value * f
            steps.append((d, f"x{f:.2f}".rstrip("0").rstrip("."), "debuff"))
            triggered += 1
        take = None
        if d == "Greed Penalty":
            take = 0.03
        elif d == "Counterfeit" or d == "Toll":
            take = 0.01
        elif d == "Envy" and rng.random() < 0.01:
            take = 0.10
        if take is not None and balance > 0:
            take = min(1.0, take * (1.5 if brittle else 1))
            amount = balance * take
            hit = hit + amount
            steps.append((d, f"-{take * 100:.1f}% of your chips".replace(".0%", "%"), "debuff"))
            triggered += 1
        if d == "Siphon" and carry.last_payout > 0:
            amount = carry.last_payout * (0.375 if brittle else 0.25)
            hit = hit + amount
            steps.append(("Siphon", f"-{amount.fmt()} (a quarter of your last card)", "debuff"))
            triggered += 1
        if d == "Jinxed":
            carry.mult.append([0.75, 1, "Jinxed"])
        elif d == "Spiked":
            carry.mult.append([0.9, 1, "Spiked"])
        elif d == "Corrosion":
            carry.mult.extend([[0.85, 1, "Corrosion"], [0.9, 2, "Corrosion"], [0.95, 3, "Corrosion"]])
        elif d == "Overcharge":
            carry.give_debuff += 1
        elif d == "Shock":
            carry.no_buffs = 1
        elif d == "Burn":
            carry.skip = 3
    slow = sum(SLOW_PICKUP.get(n, 0) for n in buffs + debuffs)
    if "Flash" in buffs:
        slow = 0.0
    carry.last_payout = value if value > 0 else Big(0)
    final_mult = float(value / Big(base)) if base and abs(value.log10()) < 300 else 0.0
    return Payout(value, steps, hit, hidden="Blind" in debuffs, fogged="Fog" in debuffs, crit=crit,
                  triggered=triggered, slow=slow, multiplier=final_mult)


def new_rng(seed=None):
    return random.Random(seed)
