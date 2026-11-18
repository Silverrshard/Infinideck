"""Plain explanations for every skill tree upgrade: what it does, and what your numbers are now and after buying it.
Works it out from the real rules (tree.Stats and meta.MetaStats), so the numbers always match the game."""
import math

import _meta as meta
import _tree as tree
from _bignum import Big
from _cards import RANKS


def pct(v, digits=1):
    return f"{v * 100:.{digits}f}%"


def ace_chance(stats, deck):
    if stats.all_aces:
        return 1.0
    bias = tree.RANK_BIAS * stats.rank_s
    weights = [math.exp(bias * RANKS.index(r)) for r, _ in deck]
    total = sum(weights) or 1
    return sum(w for (r, _), w in zip(deck, weights) if r == "A") / total


def main_node(n, p):
    """A Main tree upgrade."""
    key = tree.PATHS[n.path][0]
    now = tree.Stats(p.bought)
    after = tree.Stats(p.bought | {n.id})
    owned = n.id in p.bought
    a, b = (tree.Stats(p.bought - {n.id}), now) if owned else (now, after)
    arrow = "with it" if owned else "after you buy it"
    if key == "base":
        return (f"Adds +{n.amount.fmt()} chips to the base value of every card you pull (added before any "
                f"multipliers, so they multiply it too). Bonus on every card: +{a.base_bonus.fmt()} now, "
                f"+{b.base_bonus.fmt()} {arrow}.")
    if key == "mult":
        return (f"Multiplies the chips from every card. Chip multiplier: x{a.chip_mult:.2f} now, "
                f"x{b.chip_mult:.2f} {arrow}. This whole path tops out at x100.")
    if key == "speed":
        cd_a, cd_b = 1 / 3 / a.speed, 1 / 3 / b.speed
        return (f"You can pull cards faster (shorter wait between pulls). Pull speed: x{a.speed:.2f} "
                f"({cd_a:.2f} s per card) now, x{b.speed:.2f} ({cd_b:.2f} s) {arrow}. The path tops out at 6x.")
    if key == "buff":
        return (f"Makes it more likely a card gets a buff (a good modifier like Double Pay). Buff chance: "
                f"{pct(a.buff_chance)} now, {pct(b.buff_chance)} {arrow}. The path tops out at 75%.")
    if key == "crit":
        return (f"Makes critical hits more likely. A critical hit pays 2.5x for that card. Crit chance: "
                f"{pct(a.crit_chance)} now, {pct(b.crit_chance, 2)} {arrow}. The path tops out at 25%.")
    if key == "ranks":
        deck = p.deck
        if n.id == tree.FINAL[n.path]:
            return "The last High Ranks upgrade: from now on every card you pull is an Ace (100%)."
        return (f"Higher cards (like K and A) show up more often; low cards still appear. Chance a card is an Ace: "
                f"{pct(ace_chance(a, deck))} now, {pct(ace_chance(b, deck))} {arrow}.")
    if key == "dup":
        return (f"Gives cards a chance to come with 2 to 5 exact copies, and every copy pays too. Copy chance: "
                f"{pct(a.dup_chance, 2)} now, {pct(b.dup_chance, 2)} {arrow}. The path tops out at 10%.")
    if key == "same":
        if n.kind == "first":
            return ("Turns on same-rank streaks: pulling the same rank again right after pays more. 2 in a row: x2, "
                    "3 in a row: x4, 4 in a row: x6, and so on with no limit. A different rank resets it.")
        return (f"Gives the next card a chance to be the same rank as the last one, to keep your streak going. "
                f"Repeat chance: {pct(a.repeat)} now, {pct(b.repeat)} {arrow}. The path tops out at 25%.")
    if key == "clean":
        if n.kind == "first":
            return ("Turns on no-debuff streaks: every card in a row without a debuff adds +1% chips, stacking "
                    "(20 clean cards in a row = +20%). A card with a debuff resets the count.")
        return (f"Each clean card in a row (no debuff) adds more: +{pct(a.clean_mult - 1)} per card now, "
                f"+{pct(b.clean_mult - 1)} {arrow}. The path tops out at +50% per card.")
    if key == "rankup":
        return (f"Gives each card a chance to go up one rank as it's pulled (5 becomes 6, K becomes A, and an Ace "
                f"becomes AA worth 22). Chance: {pct(a.rankup, 2)} now, {pct(b.rankup, 2)} {arrow}. "
                "The path tops out at 6%.")
    return tree.describe(n)


class _Shim:
    """A copy of the profile's upgrade sets, to work out 'after you buy it' numbers."""

    def __init__(self, p, deck_bought=None, t_bought=None):
        self.deck_bought = deck_bought if deck_bought is not None else set(p.deck_bought)
        self.t_bought = t_bought if t_bought is not None else set(p.t_bought)
        self.removal_on = set(p.removal_on) | {n for n in self.t_bought if n in meta.T_NODES
                                               and meta.T_NODES[n].path == 0}
        self.tp, self.tp_total, self.index, self.deck = p.tp, p.tp_total, p.index, p.deck

    def index_base(self):
        return {k for k in self.index if k.split("|")[0] in RANKS}


def deck_node(n, p):
    """A Decks tab upgrade."""
    if n.id == "droot":
        return "The deck you start with. Click any deck you own to use its card back."
    key, name, _fmt, _amt = meta.DECKS[n.path]
    if n.k == 0:
        return (f"Unlocks the {name}: a new look for the back of your cards (click it once owned to use it). It also "
                f"opens its 4 upgrades, which give a bonus forever, whichever deck you're using.")
    owned = n.id in p.deck_bought
    with_it = meta.MetaStats(_Shim(p, deck_bought=set(p.deck_bought) | {n.id}))
    without = meta.MetaStats(_Shim(p, deck_bought=set(p.deck_bought) - {n.id}))
    a, b = without, with_it
    arrow = "with it" if owned else "after you buy it"
    texts = {
        "midnight": (f"All chips x1.15 more, forever. Midnight bonus: x{a.deck_mult:.2f} now, "
                     f"x{b.deck_mult:.2f} {arrow}."),
        "emerald": (f"+1% chance for every card to get a buff, forever (on top of the Main tree's Buff Chance). "
                    f"Extra buff chance: +{pct(a.buff_add, 0)} now, +{pct(b.buff_add, 0)} {arrow}."),
        "ember": (f"Critical hits pay more: +0.5x each. A crit pays x{2.5 + a.crit_dmg:g} now, "
                  f"x{2.5 + b.crit_dmg:g} {arrow}."),
        "ivory": (f"10% fewer debuffs (bad modifiers), forever. Debuffs are {pct(1 - a.debuff_scale, 0)} rarer now, "
                  f"{pct(1 - b.debuff_scale, 0)} rarer {arrow}."),
        "royal": (f"Face cards (J, Q and K) pay x1.5 more. Face card bonus: x{a.face_mult:.2f} now, "
                  f"x{b.face_mult:.2f} {arrow}."),
        "gold": f"Aces pay x1.6 more. Ace bonus: x{a.ace_mult:.2f} now, x{b.ace_mult:.2f} {arrow}.",
        "frost": (f"You pull cards 6% faster, forever (on top of the Main tree's Pull Speed). Speed bonus: "
                  f"+{pct(a.speed_mult - 1, 0)} now, +{pct(b.speed_mult - 1, 0)} {arrow}."),
        "obsidian": (f"Every card's chips x1.3. Obsidian bonus: x{a.value_mult:.2f} now, x{b.value_mult:.2f} "
                     f"{arrow}."),
        "prism": (f"+0.4% chance for a card to come with 2 to 5 copies (on top of the Main tree's Duplicates). "
                  f"Extra copy chance: +{pct(a.dup_add)} now, +{pct(b.dup_add)} {arrow}."),
        "starfield": (f"+0.4% chips for each different card you've found in your Index (you've found "
                      f"{len(p.index_base())} of 52). Bonus: +{pct(a.index_bonus)} now, +{pct(b.index_bonus)} "
                      f"{arrow}."),
    }
    return texts[key]


def transcend_node(n, p):
    """A Transcend tab upgrade."""
    if n.id == "troot":
        return "Where every Transcend path starts. Transcend upgrades are bought with Transcendent Points and stay forever."
    key = meta.T_PATHS[n.path][0]
    owned = n.id in p.t_bought
    a = meta.MetaStats(_Shim(p, t_bought=set(p.t_bought) - {n.id}))
    b = meta.MetaStats(_Shim(p, t_bought=set(p.t_bought) | {n.id}))
    arrow = "with it" if owned else "after you buy it"
    if key == "remove":
        rank, suits = meta.removal_of(n.id)
        size_a = len(meta.effective_deck(p, a))
        size_b = len(meta.effective_deck(p, b))
        return (f"Takes the {rank} of {suits[0].title()} and the {rank} of {suits[1].title()} out of your deck for "
                f"good, so better cards come up more often. Your deck: {size_a} cards now, {size_b} {arrow}. You can "
                "switch it off and on again by clicking it once you own it.")
    if key == "tpmult":
        return (f"You get more Transcendent Points every time you Transcend. Points multiplier: x{a.tp_mult:.2f} now, "
                f"x{b.tp_mult:.2f} {arrow}. The path tops out at x1,000.")
    if key == "start":
        return (f"One more starting upgrade: after buying it, click it to pick a Main tree upgrade you get for free "
                f"at the start of every run (every time you Transcend). Free slots: {a.start_slots} now, "
                f"{b.start_slots} {arrow}.")
    if key == "double":
        if n.k == 0:
            return ("Gives cards a 5% chance to get a second rank added, and both ranks pay: an A5 card pays 11 + 5 "
                    "= 16. Two Aces make AA (22), and AA plus an Ace makes AAA (33).")
        return (f"Raises the chance a card gets a second rank (A5 pays 11 + 5). Chance: {pct(a.double)} now, "
                f"{pct(b.double)} {arrow}. The path tops out at 75%.")
    if key == "boost":
        held = p.tp
        mult_a = 1 + a.per_point * held
        mult_b = 1 + b.per_point * held
        return (f"Every Transcendent Point you're holding (not spent) gives extra chips. Per point: "
                f"+{pct(a.per_point, 0)} now, +{pct(b.per_point, 0)} {arrow}. With your {Big(held).fmt()} points "
                f"that's x{Big(mult_a).fmt()} now, x{Big(mult_b).fmt()} {arrow}. The path tops out at +25% a point.")
    return meta.describe(n)


def explain(tab, n, p):
    try:
        if tab == "Main":
            return main_node(n, p)
        if tab == "Decks":
            return deck_node(n, p)
        return transcend_node(n, p)
    except (KeyError, ValueError, ZeroDivisionError, OverflowError):
        return tree.describe(n) if tab == "Main" else meta.describe(n)

