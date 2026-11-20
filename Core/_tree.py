"""The Main skill tree: 10 paths of 55 upgrades (a 40-node line plus 5 side branches that rejoin it), laid out
like an Obsidian graph around a centre node. Costs and power are made by formulas, not written by hand.

Capped paths share out their cap with growing weights, so later nodes give more and the last node lands exactly
on the cap (chip x100, pull speed 6x, buff 75%, crit 25%, duplicates 10%, rank-up 6%, no-debuff streak x1.5,
same-rank streak x18 per repeat)."""
import itertools
import math

from _bignum import Big

# --- Settings ---
SPINE = 40                      # nodes along each path's main line
BRANCH_AT = (3, 11, 19, 27, 35)  # a branch leaves spine node i and rejoins at i + 4
BRANCH_LEN = 3
START_R = 170                   # distance of each path's first node from the centre
STEP_R = 60                     # distance between spine nodes
SWIRL = 0.00045                 # paths curve round as they go out
WOBBLE = 58                     # ... and wave from side to side (pixels), more the further out they go
WOBBLE_WAVE = 230               # length of one side-to-side wave (pixels along the path)
WEIGHT_GROWTH = 1.6             # later nodes get a bigger share of a capped path's total
BASE_CRIT = 0.01
BASE_BUFF = 0.03
RANK_BIAS = 0.5                 # High Ranks: weight of rank i is exp(RANK_BIAS * 12 * s * i / 12)

# Base Value node k gives +10 ** (BASE_E * d ** BASE_P) chips to every card's base value, where d is how far along
# its path the node is (0..1). Costs follow the same curve, so income and prices climb together, plus COST_G * d
# (each tier takes a bit longer than the last) and a steep tail (COST_TAIL from TAIL_AT on), so the last upgrades of
# each path need a lot: by then a Transcend for points is the better move.
BASE_E = 40.0
BASE_P = 1.7
COST_G = 10.0
TAIL_AT = 0.5                   # tuned with the pacing bot (_claude_tools\infinideck_pacing.py)
COST_TAIL = 37.0
SAME_MAX = 18.0                 # Same-Rank Streak: the last upgrade makes every repeat x18

# key, name, cost start (log10), short description
PATHS = [
    ("base", "Base Value", 1.0, "Raises the base value of every card"),
    ("mult", "Chip Multiplier", 1.3, "Multiplies all chips (up to 100x)"),
    ("speed", "Pull Speed", 1.4, "Shorter cooldown between pulls (up to 6x faster)"),
    ("buff", "Buff Chance", 1.6, "More cards roll buffs (up to 75%)"),
    ("crit", "Critical Hits", 1.5, "More critical hits, each x2.5 (up to 25%)"),
    ("ranks", "High Ranks", 1.8, "Higher ranks come more often; the last node makes every card an Ace"),
    ("dup", "Duplicates", 2.2, "Cards can come with 2 to 5 exact copies (up to 10%)"),
    ("same", "Same-Rank Streak", 2.4, "Every repeat of the same rank in a row multiplies chips (up to x18 each)"),
    ("clean", "No-Debuff Streak", 2.6, "Every card in a row without a debuff multiplies chips (up to x1.5 each)"),
    ("rankup", "Rank Up", 2.0, "Cards can rise one rank when pulled (up to 6%)"),
]
CAPS = {"mult": 100.0, "speed": 5.0, "buff": 0.75 - BASE_BUFF, "crit": 0.25 - BASE_CRIT, "dup": 0.10,
        "rankup": 0.06, "clean": 0.49, "same": 0.25}
ROMAN = [(50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def roman(n):
    out = ""
    for v, s in ROMAN:
        while n >= v:
            out += s
            n -= v
    return out


class Node:
    __slots__ = ("amount", "children", "cost", "cur", "d", "id", "k", "kind", "parents", "path", "r", "share",
                 "style", "title", "x", "y")

    def __init__(self, nid, path, kind, x, y, r):
        self.id, self.path, self.kind, self.x, self.y, self.r = nid, path, kind, x, y, r
        self.parents, self.children = [], []
        self.d = self.share = 0.0
        self.k = 0
        self.cost = Big(0)
        self.amount = Big(0)
        self.title = ""
        self.cur = "chips"
        self.style = None


def cost_log(path, d):
    tail = max(0.0, d - TAIL_AT) / (1 - TAIL_AT)
    return PATHS[path][2] + BASE_E * d ** BASE_P + COST_G * d + COST_TAIL * tail ** 2


def build():
    """Returns (nodes by id, list of node ids per path). The same layout as before version 1.1: a 40-node line per
    path that swirls and waves, with 5 short side branches that leave it and rejoin it."""
    nodes = {"root": Node("root", -1, "root", 0.0, 0.0, 0.0)}
    nodes["root"].title = "Start"
    per_path = []
    for p in range(len(PATHS)):
        a0 = -math.pi / 2 + p * math.tau / len(PATHS)

        def wave(radius, p=p):
            return WOBBLE * math.sin(radius / WOBBLE_WAVE + p * 1.7) * min(1.0, (radius - START_R) / 320)

        def place(radius, off, a0=a0):
            a = a0 + radius * SWIRL
            off += wave(radius)
            return (math.cos(a) * radius - math.sin(a) * off, math.sin(a) * radius + math.cos(a) * off)

        ids = []
        spine = []
        for i in range(SPINE):
            r = START_R + i * STEP_R
            nid = f"{p}s{i}"
            n = Node(nid, p, "first" if i == 0 else "spine", *place(r, 0), r)
            n.parents.append("root" if i == 0 else spine[-1])
            nodes[nid] = n
            spine.append(nid)
            ids.append(nid)
        for b, i in enumerate(BRANCH_AT):
            side = 1 if (b + p) % 2 == 0 else -1
            r0, r1 = START_R + i * STEP_R, START_R + (i + 4) * STEP_R
            prev = spine[i]
            for j in range(BRANCH_LEN):
                f = (j + 1) / (BRANCH_LEN + 1)
                r = r0 + (r1 - r0) * f
                width = math.tau * r / len(PATHS)
                off = side * min(96.0, width * 0.3) * math.sin(f * math.pi) ** 0.6
                nid = f"{p}b{b}_{j}"
                n = Node(nid, p, "branch", *place(r, off), r)
                n.parents.append(prev)
                nodes[nid] = n
                ids.append(nid)
                prev = nid
            nodes[spine[i + 4]].parents.append(prev)        # the branch rejoins the path
        ids.sort(key=lambda n: (nodes[n].r, nodes[n].kind != "spine"))
        last = len(ids) - 1
        weights = [math.exp(WEIGHT_GROWTH * k / last) for k in range(len(ids))]
        total = sum(weights)
        for k, nid in enumerate(ids):
            n = nodes[nid]
            n.k, n.d, n.share = k, k / last, weights[k] / total
            n.title = f"{PATHS[p][1]} {roman(k + 1)}"
            n.cost = Big.from_log(cost_log(p, n.d))
            if PATHS[p][0] == "base":
                n.amount = Big(round(10 ** (BASE_E * n.d ** BASE_P))) if n.d < 0.4 else \
                    Big.from_log(BASE_E * n.d ** BASE_P)
        per_path.append(ids)
    for n in nodes.values():
        for par in n.parents:
            nodes[par].children.append(n.id)
    return nodes, per_path


NODES, PER_PATH = build()
PER_PATH_IDS = PER_PATH
FINAL = {p: ids[-1] for p, ids in enumerate(PER_PATH)}
FIRST = {p: ids[0] for p, ids in enumerate(PER_PATH)}
MAX_R = max(n.r for n in NODES.values())


def available(nid, bought):
    return nid not in bought and all(par in bought for par in NODES[nid].parents)


def upgrade_ids(ids):
    """Turns node ids from older saves (40-node lines with side branches) into today's ids: a path with k upgrades
    bought keeps k upgrades, the first k of its line."""
    if all(n in NODES or n == "root" for n in ids):
        return set(ids)
    count = [0] * len(PATHS)
    for nid in ids:
        if nid != "root" and nid[:1].isdigit():
            count[int(nid.split("s")[0].split("b")[0].split("n")[0])] += 1
    out = {"root"}
    for p, k in enumerate(count):
        out |= set(PER_PATH_IDS[p][:k])
    return out


class Stats:
    """Everything the bought nodes add up to."""

    def __init__(self, bought):
        share = [0.0] * len(PATHS)
        base = Big(0)
        for nid in bought:
            n = NODES.get(nid)
            if n is None or n.path < 0:
                continue
            share[n.path] += n.share
            if PATHS[n.path][0] == "base":
                base = base + n.amount
        s = {PATHS[i][0]: min(1.0, v) for i, v in enumerate(share)}
        done = {PATHS[p][0]: FINAL[p] in bought for p in range(len(PATHS))}
        started = {PATHS[p][0]: FIRST[p] in bought for p in range(len(PATHS))}
        self.base_bonus = base
        self.chip_mult = 100.0 if done["mult"] else 100.0 ** s["mult"]
        self.speed = 6.0 if done["speed"] else 1 + CAPS["speed"] * s["speed"]
        self.buff_chance = 0.75 if done["buff"] else BASE_BUFF + CAPS["buff"] * s["buff"]
        self.crit_chance = 0.25 if done["crit"] else BASE_CRIT + CAPS["crit"] * s["crit"]
        self.rank_s = s["ranks"]
        self.all_aces = done["ranks"]
        self.dup_chance = 0.10 if done["dup"] else CAPS["dup"] * s["dup"]
        self.dup_power = s["dup"]
        self.rankup = 0.06 if done["rankup"] else CAPS["rankup"] * s["rankup"]
        self.same_on = started["same"]
        first_same = NODES[FIRST[7]].share
        same_frac = max(0.0, s["same"] - first_same) / (1 - first_same)
        self.repeat = CAPS["same"] * same_frac
        self.same_mult = SAME_MAX if done["same"] else 2.0 + (SAME_MAX - 2.0) * same_frac   # x per repeat
        self.clean_on = started["clean"]
        first_clean = NODES[FIRST[8]].share
        self.clean_mult = 1.5 if done["clean"] else \
            1.01 + CAPS["clean"] * max(0.0, s["clean"] - first_clean) / (1 - first_clean)
        self.share = s


def describe(n):
    """What one node does, in plain words."""
    key = PATHS[n.path][0] if n.path >= 0 else "root"
    if key == "root":
        return "Where every path begins."
    sh = n.share
    if key == "base":
        return f"+{n.amount.fmt()} base chips on every card"
    if key == "mult":
        return f"x{100 ** sh:.3f} chips (the path tops out at x100)"
    if key == "speed":
        return f"+{CAPS['speed'] * sh * 100:.1f}% pull speed (the path tops out at 6x)"
    if key == "buff":
        return f"+{CAPS['buff'] * sh * 100:.2f}% buff chance (the path tops out at 75%)"
    if key == "crit":
        return f"+{CAPS['crit'] * sh * 100:.2f}% critical chance (the path tops out at 25%)"
    if key == "ranks":
        if n.id == FINAL[n.path]:
            return "Every card you pull is an Ace"
        return "Higher ranks come more often (low ranks still appear)"
    if key == "dup":
        return f"+{CAPS['dup'] * sh * 100:.3f}% chance of 2 to 5 exact copies (tops out at 10%)"
    if key == "same":
        if n.kind == "first":
            return "Unlocks same-rank streaks: every repeat of the last rank multiplies chips by x2, and it stacks"
        first = NODES[FIRST[n.path]].share
        return (f"+{CAPS['same'] * sh / (1 - first) * 100:.2f}% chance the next card repeats the last rank, and a "
                f"bigger multiplier for every repeat (up to x18)")
    if key == "clean":
        if n.kind == "first":
            return "Unlocks no-debuff streaks: x1.01 chips for every card in a row without a debuff"
        first = NODES[FIRST[n.path]].share
        return f"+{CAPS['clean'] * sh / (1 - first):.4f} to the per-card streak multiplier (tops out at x1.5)"
    if key == "rankup":
        return f"+{CAPS['rankup'] * sh * 100:.3f}% chance a card rises one rank (an Ace becomes AA)"
    return ""


def depth_color(r):
    """White at the centre, then red, round the rainbow, to dark purple at the edge."""
    stops = [(0.0, (255, 255, 255)), (0.1, (255, 70, 70)), (0.22, (255, 150, 50)), (0.34, (255, 225, 70)),
             (0.46, (90, 225, 110)), (0.58, (60, 210, 230)), (0.70, (70, 120, 255)), (0.82, (150, 80, 240)),
             (1.0, (110, 40, 170))]
    t = max(0.0, min(1.0, r / MAX_R))
    for (t0, c0), (t1, c1) in itertools.pairwise(stops):
        if t <= t1:
            f = (t - t0) / (t1 - t0)
            return tuple(int(a + (b - a) * f) for a, b in zip(c0, c1))
    return stops[-1][1]
