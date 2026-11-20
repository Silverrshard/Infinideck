"""The Decks tab (10 decks x 5 upgrades, bought with chips, kept forever) and the Transcend tab (5 paths, 144
upgrades, bought with Transcendent Points), plus the Transcend maths.

Transcend requirement (from the design, unchanged): chips needed for the next point = 10^15 x (3K^2 + 3K + 1),
where K is the points already earned from that formula. Summed up, K points need 10^15 x K^3 chips in a run."""
import math

import _tree as tree
from _bignum import Big
from _cards import RANKS, SUITS

# --- Decks: key, name, what each level adds, per-level amount. Unlocking a deck is its first level, and each of its
# 4 upgrades adds another (5 levels). The pricier the deck, the bigger its bonus. ---
DECKS = [
    ("midnight", "Midnight Deck", "x{:g} chips", 1.8),
    ("emerald", "Emerald Deck", "+{:.0%} buff chance", 0.03),
    ("ember", "Ember Deck", "+{:g} critical damage", 1.5),
    ("ivory", "Ivory Deck", "-{:.0%} debuffs", 0.15),
    ("royal", "Royal Deck", "Face cards x{:g}", 4.0),
    ("gold", "Gold Deck", "Aces x{:g}", 3.0),
    ("frost", "Frost Deck", "+{:.0%} pull speed", 0.20),
    ("obsidian", "Obsidian Deck", "Card value x{:g}", 4.0),
    ("prism", "Prism Deck", "+{:.1%} duplicate chance", 0.015),
    ("starfield", "Starfield Deck", "x{:g} chips for every card in your Index", 1.02),
]
DECK_STEPS = 5                  # unlock + 4 upgrades
DECK_R0, DECK_STEP = 190, 105

# --- Transcend paths: key, name, node count ---
T_PATHS = [
    ("remove", "Rank Removal", 24),
    ("tpmult", "Point Multiplier", 30),
    ("start", "Starting Upgrades", 30),
    ("double", "Double Ranks", 30),
    ("boost", "Chip Boost per Point", 30),
    ("auto", "Automation", 2),
]
T_PER_RING = 6
T_R0, T_RING = 170, 78
T_COST = {"remove": 0.0, "tpmult": 0.0, "start": 0.2, "double": 0.1, "boost": 0.0, "auto": 0.5}  # offsets (log10)
T_STEP = 0.30           # the first upgrades in a path cost about 2x the one before (1, 2, 4, 8...)
T_CHEAP = 10            # ... for the first 10, then prices climb towards T_TOP (log10) at the end of the path,
T_TOP = 27.8            # fast at first and slower near the top (points level off near 1e28, so keep below that)
T_CURVE = 0.5
AUTO_COSTS = (3, 2000)  # Automation: Buy All for the Main tree, then Buy All for the Decks too
TP_MULT_MAX = 1000.0
TP_BONUS_PER_TOTAL = 0.01       # every point ever earned: +1% chips, forever
TP_BOOST_EXP = 0.5              # ... and the points' chip boosts are square-rooted, so huge point totals can't run away


def _node(nid, path, kind, x, y, r, title, cost, cur):
    n = tree.Node(nid, path, kind, x, y, r)
    n.title, n.cost, n.cur = title, cost, cur
    return n


def build_decks():
    nodes = {"droot": _node("droot", -1, "root", 0.0, 0.0, 0.0, "Classic Deck", Big(0), "chips")}
    nodes["droot"].style = "classic"
    for d, (key, name, _fmt, _amt) in enumerate(DECKS):
        a = -math.pi / 2 + d * math.tau / len(DECKS)
        prev = "droot"
        for j in range(DECK_STEPS):
            r = DECK_R0 + j * DECK_STEP
            bend = a + 0.13 * j * (1 if d % 2 else -1)           # each deck's line curves a little
            x, y = math.cos(bend) * r, math.sin(bend) * r
            nid = f"d{d}_{j}"
            title = name if j == 0 else f"{name} {tree.roman(j + 1)}"
            cost = Big.from_log(6 + 5.5 * d + (2.0 + 0.6 * d) * j)
            n = _node(nid, d, "first" if j == 0 else "spine", x, y, r, title, cost, "chips")
            n.style = key
            n.k, n.d = j, j / (DECK_STEPS - 1)
            n.parents.append(prev)
            nodes[nid] = n
            prev = nid
    for n in nodes.values():
        for par in n.parents:
            nodes[par].children.append(n.id)
    return nodes


def t_log(i, last):
    """log10 of the price of upgrade i in a Transcend path."""
    if i < T_CHEAP or last <= T_CHEAP:
        return T_STEP * i
    start = T_STEP * T_CHEAP
    return start + (T_TOP - start) * ((i - T_CHEAP + 1) / (last - T_CHEAP + 1)) ** T_CURVE


def build_transcend():
    nodes = {"troot": _node("troot", -1, "root", 0.0, 0.0, 0.0, "Transcend", Big(0), "tp")}
    per_path = []
    sector = math.tau / len(T_PATHS)
    for p, (key, name, count) in enumerate(T_PATHS):
        ids = []
        last = count - 1
        weights = [math.exp(1.8 * k / last) for k in range(count)]
        total = sum(weights)
        for i in range(count):
            ring, slot = divmod(i, T_PER_RING)
            if ring % 2:
                slot = T_PER_RING - 1 - slot                        # snake back and forth across the sector
            a = -math.pi / 2 - sector / 2 + p * sector + (slot + 0.5) / T_PER_RING * sector * 0.9 + sector * 0.05
            r = T_R0 + ring * T_RING
            nid = f"t{p}_{i}"
            d = i / max(1, last)
            lg = T_COST[key] + t_log(i, last)
            cost = Big(math.ceil(10 ** lg)) if lg < 15 else Big.from_log(lg)
            if key == "remove":
                rank = RANKS[i % 12]
                title = f"Remove two {rank}s" if i < 12 else f"Remove the last two {rank}s"
            elif key == "auto":
                title = ("Buy All", "Buy All: Decks")[i]
                cost = Big(AUTO_COSTS[i])
            else:
                title = f"{name} {tree.roman(i + 1)}"
            n = _node(nid, p, "first" if i == 0 else "spine", math.cos(a) * r, math.sin(a) * r, r, title, cost, "tp")
            n.k, n.d, n.share = i, d, weights[i] / total
            n.parents.append("troot" if i == 0 else ids[-1])
            nodes[nid] = n
            ids.append(nid)
        per_path.append(ids)
    for n in nodes.values():
        for par in n.parents:
            nodes[par].children.append(n.id)
    return nodes, per_path


DECK_NODES = build_decks()
T_NODES, T_PER_PATH = build_transcend()
REMOVE_SUITS = (("hearts", "clubs"), ("diamonds", "spades"))     # first pass, then second pass


def removal_of(nid):
    """(rank, suits) a Rank Removal node takes out of the deck."""
    i = T_NODES[nid].k
    return RANKS[i % 12], REMOVE_SUITS[i // 12]


def available(nodes, nid, bought):
    return nid not in bought and all(par in bought for par in nodes[nid].parents)


# --- What decks and Transcend add up to ---
class MetaStats:
    def __init__(self, p):
        level = [sum(1 for j in range(DECK_STEPS) if f"d{d}_{j}" in p.deck_bought) for d in range(len(DECKS))]
        lv = {DECKS[d][0]: level[d] for d in range(len(DECKS))}
        amt = {k: a for k, _n, _f, a in DECKS}
        self.levels = lv
        self.deck_mult = amt["midnight"] ** lv["midnight"]
        self.buff_add = amt["emerald"] * lv["emerald"]
        self.crit_dmg = amt["ember"] * lv["ember"]
        self.debuff_scale = max(0.0, 1 - amt["ivory"] * lv["ivory"])
        self.face_mult = amt["royal"] ** lv["royal"]
        self.ace_mult = amt["gold"] ** lv["gold"]
        self.speed_mult = 1 + amt["frost"] * lv["frost"]
        self.value_mult = amt["obsidian"] ** lv["obsidian"]
        self.dup_add = amt["prism"] * lv["prism"]
        self.index_bonus = amt["starfield"] ** (lv["starfield"] * len(p.index_base())) - 1
        share = [0.0] * len(T_PATHS)
        count = [0] * len(T_PATHS)
        for nid in p.t_bought:
            n = T_NODES.get(nid)
            if n is not None and n.path >= 0:
                share[n.path] += n.share
                count[n.path] += 1
        full = [count[i] == T_PATHS[i][2] for i in range(len(T_PATHS))]
        self.tp_mult = TP_MULT_MAX if full[1] else TP_MULT_MAX ** share[1]
        self.start_slots = count[2]
        first_d = T_NODES[T_PER_PATH[3][0]].share
        self.double = 0.0 if not count[3] else 0.75 if full[3] else \
            0.05 + 0.70 * (share[3] - first_d) / (1 - first_d)
        first_b = T_NODES[T_PER_PATH[4][0]].share
        self.per_point = 0.0 if not count[4] else 0.25 if full[4] else \
            0.02 + 0.23 * (share[4] - first_b) / (1 - first_b)
        self.tp_chip_mult = ((1 + TP_BONUS_PER_TOTAL * p.tp_total) * (1 + self.per_point * p.tp)) ** TP_BOOST_EXP
        self.buy_all = count[5] >= 1            # Automation: a Buy All button in the Main tree
        self.buy_all_decks = count[5] >= 2      # ... and in the Decks tab
        self.removed = {removal_of(n) for n in p.t_bought if n in p.removal_on and T_NODES[n].path == 0}


def effective_deck(p, meta):
    """The deck with Rank Removal applied (never empty: Aces are never removed)."""
    gone = set()
    for rank, suits in meta.removed:
        for s in suits:
            gone.add((rank, s))
    out = [e for e in p.deck if (e[0], e[1]) not in gone]
    return out or [[r, s] for s in SUITS for r in ("A",)]


def describe(n):
    if n.id == "droot":
        return "The deck you start with. Click a deck you own to use its card back."
    if n.id == "troot":
        return "Where every Transcend path begins."
    if n.id in DECK_NODES:
        key, name, fmt, amt = DECKS[n.path]
        if n.k == 0:
            return f"Unlocks the {name} card back and its first bonus ({fmt.format(amt)}, forever)."
        return fmt.format(amt) + " more (forever)"
    key = T_PATHS[n.path][0]
    if key == "remove":
        rank, suits = removal_of(n.id)
        return (f"Removes the {rank} of {suits[0].title()} and {suits[1].title()} from your deck, forever. "
                "You can switch it off and on after buying it.")
    if key == "tpmult":
        return f"x{TP_MULT_MAX ** n.share:.3f} Transcendent Points per Transcend (the path tops out at x1,000)"
    if key == "start":
        return "One more starting upgrade: pick a Main tree upgrade you get free at the start of every run"
    if key == "double":
        if n.k == 0:
            return "5% chance a card gets a second rank (A5, 5K...). AA becomes AAA"
        first = T_NODES[T_PER_PATH[3][0]].share
        return f"+{0.70 * n.share / (1 - first) * 100:.2f}% second-rank chance (the path tops out at 75%)"
    if key == "boost":
        if n.k == 0:
            return "Every Transcendent Point you hold gives +2% chips"
        first = T_NODES[T_PER_PATH[4][0]].share
        return f"+{0.23 * n.share / (1 - first) * 100:.2f}% chips per point you hold (the path tops out at 25%)"
    if key == "auto":
        return AUTO_TEXT[n.k]
    return ""


AUTO_TEXT = (("Adds a Buy All button to the Main tree: it buys every upgrade you can afford, cheapest first, "
              "again and again until you can't afford any more."),
             "Adds the Buy All button to the Decks tab too.")


# --- Transcending ---
def needed(k):
    """Chips needed in one run for point number k + 1."""
    return Big(1e15) * (3 * k * k + 3 * k + 1)


def formula_points(run_chips, k):
    """How many points the formula gives for this run's chips, starting from k points."""
    if run_chips < needed(k):
        return 0
    total = Big(k) ** 3 + run_chips / Big(1e15)
    est = Big.from_log(total.log10() / 3)
    if est.e < 15:
        g = int(float(est))
        while (g + 1) ** 3 <= float(total):
            g += 1
        while g ** 3 > float(total):
            g -= 1
        return max(0, g - k)
    return int(float(est)) - k if est.e < 300 else 0


def points_for(p, meta):
    base = formula_points(p.run_earned, p.tp_k)
    return base, int(base * meta.tp_mult) if base else 0


def valid_start(picks):
    """Keeps only starting picks whose prerequisites are also picked (in Main tree order)."""
    ok = {"root"}
    changed = True
    picks = [n for n in picks if n in tree.NODES]
    while changed:
        changed = False
        for n in picks:
            if n not in ok and all(par in ok for par in tree.NODES[n].parents):
                ok.add(n)
                changed = True
    return ok
