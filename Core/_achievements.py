"""The 191 achievements (171 normal, 20 secret) and the stats that track them.
Each entry: name, description, check(p, a, eng), progress(p, a) -> (have, need) or None."""
import functools
import re
from pathlib import Path

import _meta as meta
import _tree as tree
from _bignum import Big
from _cards import BUFFS, DEBUFFS, FACE, RANKS


def life(n):
    return (lambda p, a, e: p.lifetime >= n), (lambda p, a: (p.lifetime, Big(n)))


def high(n):
    return (lambda p, a, e: p.highest >= n), (lambda p, a: (p.highest, Big(n)))


def high_log(n):
    return (lambda p, a, e: p.highest.log10() >= n), None


def count(field, n, src="p"):
    if src == "p":
        return (lambda p, a, e: getattr(p, field) >= n), (lambda p, a: (getattr(p, field), n))
    return (lambda p, a, e: a.get(field, 0) >= n), (lambda p, a: (a.get(field, 0), n))


def flag(name):
    return (lambda p, a, e: bool(a.get(name))), None


def mult(n):
    return (lambda p, a, e: a.get("max_log_mult", 0) >= n), None


def digits(n):
    return (lambda p, a, e: p.highest.digits() >= n), (lambda p, a: (p.highest.digits(), n))


def maxed(p):
    return (len(p.bought) == len(tree.NODES) and len(p.deck_bought) == len(meta.DECK_NODES)
            and len(p.t_bought) == len(meta.T_NODES))


def distinct(p):
    return len(set(p.perks_owned))


NORMAL = [
    ("First Fortune", "Earn 1,000 chips.", *life(1e3)),
    ("Getting Somewhere", "Earn 1 million chips.", *life(1e6)),
    ("Millionaire's Mindset", "Earn 1 billion chips.", *life(1e9)),
    ("Trillionaire", "Earn 1 trillion chips.", *life(1e12)),
    ("Beyond Comprehension", "Earn 1 quadrillion chips.", *life(1e15)),
    ("Numbers Go Brrr", "Earn 1 quintillion chips.", *life(1e18)),
    ("Financial Singularity", "Reach 10^100 chips.", *high(Big(1, 100))),
    ("There Is No Ceiling", "Reach 10^500 chips.", *high(Big(1, 500))),
    ("Trust the Deck", "Pull your first card.", *count("cards", 1)),
    ("It's All Random", "Pull 100 cards.", *count("cards", 100)),
    ("Cardboard Addict", "Pull 10,000 cards.", *count("cards", 10_000)),
    ("An Unreasonable Amount", "Pull 1 million cards.", *count("cards", 1_000_000)),
    ("Face Value", "Pull your first face card.", *flag("face_seen")),
    ("Ace in the Hole", "Pull 100 Aces.", *count("aces", 100, "a")),
    ("Déjà Vu", "Pull the same rank 10 times in a row.", *count("longest_streak", 10)),
    ("Perfect Sequence", "Pull five ranks in a row in ascending order.", *count("asc_max", 5, "a")),
    ("Multiplication Table", "Unlock your first multiplier upgrade.", *flag("mult_bought")),
    ("Compound Interest", "Reach a x100 multiplier on one card.", *mult(2)),
    ("Overkill", "Reach a x1,000,000 multiplier on one card.", *mult(6)),
    ("Multiplicatively Unstable", "Reach a x1 billion multiplier on one card.", *mult(9)),
    ("This Can't Be Legal", "Earn 1 trillion chips from one card.",
     lambda p, a, e: p.best_card >= 1e12, lambda p, a: (p.best_card, Big(1e12))),
    ("Exponential Growth", "Beat your previous highest chip balance with one card.", *flag("beat_high")),
    ("One More Upgrade", "Buy 100 skill tree upgrades.", *count("buys", 100, "a")),
    ("A Slight Improvement", "Buy 500 skill tree upgrades.", *count("buys", 500, "a")),
    ("Completionist's Burden", "Max out one skill tree tab.", *flag("tab_maxed")),
    ("No Node Left Behind", "Max out every skill tree tab.", *flag("all_maxed")),
    ("A Higher Purpose", "Transcend for the first time.", *count("transcends", 1)),
    ("Starting Over, Again", "Transcend 10 times.", *count("transcends", 10)),
    ("Ascending", "Earn 100 Transcendent Points in total.", *count("tp_lifetime", 100)),
    ("Beyond the Beyond", "Earn 1,000 Transcendent Points in total.", *count("tp_lifetime", 1000)),
    ("Nothing Is Permanent", "Buy a Transcend upgrade.", *flag("t_bought")),
    ("A Better Beginning", "Start a run with a starting upgrade.", *flag("start_pick")),
    ("Enlightenment", "Max out the Transcend tree.", *flag("t_maxed")),
    ("Break the Cycle", "Shatter for the first time.", *count("shatters", 1)),
    ("Unfair Advantage", "Equip your first perk.", *flag("equipped")),
    ("Worth the Sacrifice", "Sacrifice perks to unlock a slot.", *count("sacrifices", 1)),
    ("A Full Hand", "Unlock all five perk slots.", *count("perk_slots", 5)),
    ("The Collection Grows", "Own 10 different perks.",
     lambda p, a, e: distinct(p) >= 10, lambda p, a: (distinct(p), 10)),
    ("Perkfection", "Own all 100 perks.", lambda p, a, e: distinct(p) >= 100, lambda p, a: (distinct(p), 100)),
    ("Power at a Price", "Equip a perk with a downside.", *flag("equip_negative")),
    ("The Odds Were WHAT?", "See a card rarer than 1 in a million.", *count("ultra", 1, "a")),
    ("I've Seen This Before", "Pull every rank from 2 to Ace.",
     lambda p, a, e: len(a.get("ranks_seen", [])) >= 13, lambda p, a: (len(a.get("ranks_seen", [])), 13)),
    ("A Small Number", "Reach a x10^100 multiplier on one card.", *mult(100)),
    ("The Multiplier Is the Message", "Reach a x10^50 multiplier on one card.", *mult(50)),
    ("Why Did I Do That?", "Shatter with at least 1 quadrillion chips.", *flag("shatter_rich")),
    ("Royal Flush of Luck", "Pull 10 face cards in a row.", *count("face_run_max", 10, "a")),
    ("Speedrunner", "Reach 1 million chips within 5 minutes of starting a run.", *flag("speedrun")),
    ("Patient Investor", "Play one profile for 10 hours.",
     lambda p, a, e: p.playtime >= 36000, lambda p, a: (int(p.playtime // 3600), 10)),
    ("Dedicated", "Pull 100,000 cards.", *count("cards", 100_000)),
    ("All According to Plan", "Buy 50 upgrades in one run.", *count("run_buys", 50, "a")),
]

SECRET = [
    ("...", "See five cards rarer than 1 in a million.", *count("ultra", 5, "a")),
    ("You Weren't Supposed to See This", "Unlock another secret achievement.", *flag("secret_any")),
    ("A Glitch in Reality", "Get a card with three or more modifiers.", *count("max_mods", 3, "a")),
    ("Wrong Place, Wrong Time", "See two ultra-rare cards in a row.", *count("ultra_run_max", 2, "a")),
    ("The Forbidden Number", "Reach 10^1000 chips.", *high_log(1000)),
    ("It Was Supposed to Be Impossible", "Pull five Aces in a row without anything forcing Aces.",
     *count("ace_run_fair", 5, "a")),
    ("Nothing to See Here", "Open the achievements 100 times.", *count("menu_opens", 100, "a")),
    ("We Don't Talk About That", "Get a negative card payout.", *flag("negative_pay")),
    ("The End?", "Max out every skill tree and own every perk.",
     lambda p, a, e: maxed(p) and distinct(p) >= 100, None),
    ("The Beginning.", "Shatter after unlocking The End?", *flag("after_end")),
    ("Against All Odds", "See a rare card (1 in 1,000 or rarer) in your first 10 pulls.", *flag("early_rare")),
    ("Unreasonably Lucky", "Get the same rare modifier three times in one run.", *flag("rare_triple")),
    ("Déjà Vu²", "Pull the same rank 20 times in a row.", *count("longest_streak", 20)),
    ("The Royal Treatment", "Pull 25 face cards in a row.", *count("face_run_max", 25, "a")),
    ("Ace Attorney", "Pull 50 Aces in one run.", *count("run_aces_max", 50, "a")),
    ("The Deck Is Lying", "Pull 100 cards in a row without an Ace.", *count("no_ace_max", 100, "a")),
    ("Mathematical Error", "Reach a multiplier above 10^1000 on one card.", *mult(1000)),
    ("Beyond Infinity", "Reach a chip balance with at least 10,000 digits.", *digits(10_000)),
    ("A Number With No Name", "Reach a chip balance with at least 100,000 digits.", *digits(100_000)),
    ("What Comes After?", "Reach a chip balance with at least 1 million digits.", *digits(1_000_000)),
    ("Unstoppable", "Earn 1 quadrillion chips from one card.", lambda p, a, e: p.best_card >= 1e15, None),
    ("Pocket Change", "Earn less than 10 chips from a card after 1 trillion lifetime chips.", *flag("pocket")),
    ("A Little Overkill", "Put a multiplier over x1 million on one card.", *mult(6)),
    ("Negative Thinking", "Get a card with a debuff.", *flag("any_debuff")),
    ("Double Trouble", "Get a card with at least two multiplying buffs.", *count("max_mult_buffs", 2, "a")),
    ("The Perfect Storm", "Get a card with both a buff and a debuff.", *flag("buff_and_debuff")),
    ("Against the Grain", "Transcend without buying Chip Multiplier upgrades that run.", *flag("no_mult_run")),
    ("No Shortcuts", "Transcend without buying Pull Speed upgrades that run.", *flag("no_speed_run")),
    ("A Fresh Start", "Shatter twice within 10 minutes.", *flag("fast_shatter")),
    ("Why Stop Now?", "Shatter 10 times.", *count("shatters", 10)),
    ("Sacrificial Lamb", "Sacrifice five perks at once.", *count("sacrifices", 1)),
    ("Perk Hoarder", "Own 50 different perks.", lambda p, a, e: distinct(p) >= 50, None),
    ("The Collector's Curse", "Own every perk with none equipped.",
     lambda p, a, e: distinct(p) >= 100 and not p.equipped, None),
    ("Power Overwhelming", "Equip five perks with no downside.", *flag("five_good")),
    ("Chaos Theory", "Equip five perks that each have a downside.", *flag("five_bad")),
    ("Rules Are Suggestions", "Get a perk multiplier above x1 billion on one card.",
     lambda p, a, e: a.get("perk_log_max", 0) >= 9, None),
    ("One in a Million", "See something with a 1 in a million chance or lower.", *count("ultra", 1, "a")),
    ("The Longest Run", "Play one run for 24 hours.", *flag("long_run")),
    ("Insomnia", "Play one profile for 100 hours.", lambda p, a, e: p.playtime >= 360000, None),
    ("A New Record", "Beat your best single-card payout by 100 times.", *flag("record_x100")),
    ("The Rich Get Richer", "Earn 99% of your lifetime chips in one run.", *flag("rich_run")),
    ("The Final Rank", "Get an AA card.", *flag("aa")),
    ("Triple Trouble", "Get an AAA card.", *flag("aaa")),
    ("The Impossible Hand", "Pull the same rank and suit five times in a row.", *count("ident_max", 5, "a")),
    ("Perfectly Imperfect", "Get a card with three debuffs.", *count("max_debuffs", 3, "a")),
    ("Nothing Can Stop Me", "Max out the Pull Speed path.", lambda p, a, e: tree.FINAL[2] in p.bought, None),
    ("Probability Is Broken", "Max out the Buff Chance path.", lambda p, a, e: tree.FINAL[3] in p.bought, None),
    ("One Last Upgrade", "Buy the very last skill tree upgrade.", *flag("last_upgrade")),
    ("The Infinite Loop", "Buy an upgrade that makes an earlier one stronger.", *flag("loop")),
    ("Infinideck", "Unlock every other achievement.", lambda p, a, e: len(p.achievements) >= 190, None),
]
# Only these 20 stay secret; the other 30 from the design's secret list are normal achievements (asked for after
# a playtest: 50 hidden ones were too many).
KEEP_SECRET = {"...", "You Weren't Supposed to See This", "Wrong Place, Wrong Time", "The Forbidden Number",
               "It Was Supposed to Be Impossible", "Nothing to See Here", "We Don't Talk About That", "The End?",
               "The Beginning.", "Against All Odds", "Unreasonably Lucky", "The Deck Is Lying", "Mathematical Error",
               "What Comes After?", "Pocket Change", "The Collector's Curse", "Chaos Theory", "Rules Are Suggestions",
               "The Impossible Hand", "Infinideck"}
def best(n):
    return (lambda p, a, e: p.best_card >= n), (lambda p, a: (p.best_card, Big(n)))


def path_done(i):
    return (lambda p, a, e: tree.FINAL[i] in p.bought), None


def decks_owned(p):
    return sum(1 for nid, n in meta.DECK_NODES.items() if n.kind == "first" and nid in p.deck_bought)


def index_found(n):
    return (lambda p, a, e: len(p.index_base()) >= n), (lambda p, a: (len(p.index_base()), n))


def ach_count(n):
    return (lambda p, a, e: len(p.achievements) >= n), (lambda p, a: (len(p.achievements), n))


EXTRA = [                       # 91 more normal achievements (added after the first playtest)
    ("Pocket Money", "Earn 100 chips.", *life(100)),
    ("Six Figures", "Earn 100,000 chips.", *life(1e5)),
    ("Sextillionaire", "Earn 1 sextillion chips (10^21).", *life(1e21)),
    ("Septillion Club", "Earn 10^24 chips.", *life(1e24)),
    ("Thirty Zeros", "Earn 10^30 chips.", *life(1e30)),
    ("Forty Zeros", "Earn 10^40 chips.", *life(1e40)),
    ("Half a Hundred", "Earn 10^50 chips.", *life(Big(1, 50))),
    ("Seventy-Five", "Earn 10^75 chips.", *life(Big(1, 75))),
    ("A Googol Twice Over", "Reach 10^200 chips.", *high(Big(1, 200))),
    ("Three Hundred Zeros", "Reach 10^300 chips.", *high(Big(1, 300))),
    ("Past the Calculator", "Reach 10^750 chips.", *high(Big(1, 750))),
    ("Warming Up", "Pull 500 cards.", *count("cards", 500)),
    ("A Thousand Cards", "Pull 1,000 cards.", *count("cards", 1000)),
    ("Shuffling Along", "Pull 2,500 cards.", *count("cards", 2500)),
    ("Five Grand", "Pull 5,000 cards.", *count("cards", 5000)),
    ("Card Shark", "Pull 25,000 cards.", *count("cards", 25_000)),
    ("Deck Whisperer", "Pull 50,000 cards.", *count("cards", 50_000)),
    ("Quarter Million", "Pull 250,000 cards.", *count("cards", 250_000)),
    ("Half a Million", "Pull 500,000 cards.", *count("cards", 500_000)),
    ("Millions of Cards", "Pull 5 million cards.", *count("cards", 5_000_000)),
    ("First Crit", "Land your first critical hit.", *count("crits", 1)),
    ("Critical Thinking", "Land 100 critical hits.", *count("crits", 100)),
    ("Critical Mass", "Land 1,000 critical hits.", *count("crits", 1000)),
    ("Always Critical", "Land 10,000 critical hits.", *count("crits", 10_000)),
    ("Crit Machine", "Land 100,000 critical hits.", *count("crits", 100_000)),
    ("Modified", "Have modifiers do something 100 times.", *count("mod_hits", 100)),
    ("Heavily Modified", "Have modifiers do something 10,000 times.", *count("mod_hits", 10_000)),
    ("Modifier Overload", "Have modifiers do something 1 million times.", *count("mod_hits", 1_000_000)),
    ("Seeing Double", "Get your first duplicate card.", *count("dups", 1)),
    ("Copy Machine", "Get 100 duplicate cards.", *count("dups", 100)),
    ("Photocopier", "Get 10,000 duplicate cards.", *count("dups", 10_000)),
    ("Level Up", "Have a card go up a rank.", *count("rank_ups", 1)),
    ("Promotion Season", "Have 100 cards go up a rank.", *count("rank_ups", 100)),
    ("Climbing the Ranks", "Have 10,000 cards go up a rank.", *count("rank_ups", 10_000)),
    ("Twice in a Row", "Pull the same rank 3 times in a row.", *count("longest_streak", 3)),
    ("Five of a Kind", "Pull the same rank 5 times in a row.", *count("longest_streak", 5)),
    ("Lucky Seven", "Pull the same rank 7 times in a row.", *count("longest_streak", 7)),
    ("Fifteen Strong", "Pull the same rank 15 times in a row.", *count("longest_streak", 15)),
    ("Clean Hands", "Pull 50 cards in a row with no debuff.", *count("longest_clean", 50)),
    ("Spotless", "Pull 100 cards in a row with no debuff.", *count("longest_clean", 100)),
    ("Squeaky Clean", "Pull 500 cards in a row with no debuff.", *count("longest_clean", 500)),
    ("Untouchable", "Pull 1,000 cards in a row with no debuff.", *count("longest_clean", 1000)),
    ("Pristine Record", "Pull 5,000 cards in a row with no debuff.", *count("longest_clean", 5000)),
    ("Just One More Hour", "Play one profile for 1 hour.",
     lambda p, a, e: p.playtime >= 3600, lambda p, a: (int(p.playtime // 60), 60)),
    ("Afternoon Gone", "Play one profile for 3 hours.",
     lambda p, a, e: p.playtime >= 10800, lambda p, a: (int(p.playtime // 60), 180)),
    ("Day and Night", "Play one profile for 25 hours.",
     lambda p, a, e: p.playtime >= 90000, lambda p, a: (int(p.playtime // 3600), 25)),
    ("Lifestyle", "Play one profile for 50 hours.",
     lambda p, a, e: p.playtime >= 180000, lambda p, a: (int(p.playtime // 3600), 50)),
    ("Third Time's the Charm", "Transcend 3 times.", *count("transcends", 3)),
    ("Frequent Flyer", "Transcend 5 times.", *count("transcends", 5)),
    ("Serial Transcender", "Transcend 25 times.", *count("transcends", 25)),
    ("Fifty Lives", "Transcend 50 times.", *count("transcends", 50)),
    ("Hundred Lives", "Transcend 100 times.", *count("transcends", 100)),
    ("Ten Points", "Earn 10 Transcendent Points in total.", *count("tp_lifetime", 10)),
    ("Ten Thousand Points", "Earn 10,000 Transcendent Points in total.", *count("tp_lifetime", 10_000)),
    ("A Million Points", "Earn 1 million Transcendent Points in total.", *count("tp_lifetime", 1_000_000)),
    ("A Billion Points", "Earn 1 billion Transcendent Points in total.", *count("tp_lifetime", 10 ** 9)),
    ("A Trillion Points", "Earn 1 trillion Transcendent Points in total.", *count("tp_lifetime", 10 ** 12)),
    ("Shattered Thrice", "Shatter 3 times.", *count("shatters", 3)),
    ("Glass Collector", "Shatter 5 times.", *count("shatters", 5)),
    ("Shopping Spree", "Buy 25 skill tree upgrades.", *count("buys", 25, "a")),
    ("Big Spender", "Buy 250 skill tree upgrades.", *count("buys", 250, "a")),
    ("Upgrade Addict", "Buy 1,000 skill tree upgrades.", *count("buys", 1000, "a")),
    ("Upgrade Legend", "Buy 5,000 skill tree upgrades.", *count("buys", 5000, "a")),
    ("Productive Run", "Buy 150 upgrades in one run.", *count("run_buys", 150, "a")),
    ("Everything at Once", "Buy 400 upgrades in one run.", *count("run_buys", 400, "a")),
    ("Ace Collector", "Pull 1,000 Aces.", *count("aces", 1000, "a")),
    ("Ace Hoarder", "Pull 10,000 Aces.", *count("aces", 10_000, "a")),
    ("Double Stacked", "Get a card with two modifiers.", *count("max_mods", 2, "a")),
    ("Four Layers Deep", "Get a card with four modifiers.", *count("max_mods", 4, "a")),
    ("Stack Overflow", "Get a card with six modifiers.", *count("max_mods", 6, "a")),
    ("Multiplier Party", "Get a card with three multiplying buffs.", *count("max_mult_buffs", 3, "a")),
    ("Thousandfold", "Reach a x1,000 multiplier on one card.", *mult(3)),
    ("Trillionfold", "Reach a x1 trillion multiplier on one card.", *mult(12)),
    ("Beyond Twenty", "Reach a x10^20 multiplier on one card.", *mult(20)),
    ("Big Payday", "Earn 1 million chips from one card.", *best(1e6)),
    ("Billion-Chip Card", "Earn 1 billion chips from one card.", *best(1e9)),
    ("Quintillion Card", "Earn 10^18 chips from one card.", *best(1e18)),
    ("Card of Legends", "Earn 10^30 chips from one card.", *best(1e30)),
    ("The One Card", "Earn 10^100 chips from one card.", *best(Big(1, 100))),
    ("A Full Suit", "Find 13 different cards for the Index.", *index_found(13)),
    ("Half the Deck", "Find 26 different cards for the Index.", *index_found(26)),
    ("Almost There", "Find 39 different cards for the Index.", *index_found(39)),
    ("The Complete Index", "Find all 52 cards for the Index.", *index_found(52)),
    ("New Look", "Unlock your first new deck.",
     lambda p, a, e: decks_owned(p) >= 1, lambda p, a: (decks_owned(p), 1)),
    ("Deck Collector", "Unlock all 10 decks.",
     lambda p, a, e: decks_owned(p) >= 10, lambda p, a: (decks_owned(p), 10)),
    ("Base Camp", "Max out the Base Value path.", *path_done(0)),
    ("Multiplied", "Max out the Chip Multiplier path.", *path_done(1)),
    ("Lucky Strikes", "Max out the Critical Hits path.", *path_done(4)),
    ("All Aces", "Max out the High Ranks path.", *path_done(5)),
    ("Streak Master", "Max out the Same-Rank Streak path.", *path_done(7)),
    ("Trophy Cabinet", "Unlock 150 achievements.", *ach_count(150)),
]
NORMAL = NORMAL + [s for s in SECRET if s[0] not in KEEP_SECRET] + EXTRA
SECRET = [s for s in SECRET if s[0] in KEEP_SECRET]
ALL = [(n, d, c, pr, False) for n, d, c, pr in NORMAL] + [(n, d, c, pr, True) for n, d, c, pr in SECRET]
assert len(NORMAL) == 171 and len(SECRET) == 20, (len(NORMAL), len(SECRET))
assert len({a[0] for a in ALL}) == len(ALL), "achievement names must be unique"
MULT_BUFFS = {b for b, v in BUFFS.items() if v[1] == "mult"} | {"Jackpot", "Lucky", "Banker", "Overflow", "Blood"}
RARE_MODS = {b for b, v in BUFFS.items() if v[0] <= 3.0} | {d for d, v in DEBUFFS.items() if v[0] <= 2.0}


# --- Tracking ---
def on_card(p, res, gained, eng, high_before, best_before):
    """Updates the achievement stats for one banked card."""
    a = p.ach
    card, _pay = res.card, res.payout
    if res.burned:
        return
    r = card.ranks[0]
    seen = set(a.get("ranks_seen", []))
    if r in RANKS:
        seen.add(r)
    a["ranks_seen"] = sorted(seen)
    face = card.is_face()
    ace = r.startswith("A")
    if face:
        a["face_seen"] = True
    a["face_run"] = a.get("face_run", 0) + 1 if face else 0
    a["face_run_max"] = max(a.get("face_run_max", 0), a["face_run"])
    if ace:
        a["aces"] = a.get("aces", 0) + 1
        a["run_aces"] = a.get("run_aces", 0) + 1
        a["run_aces_max"] = max(a.get("run_aces_max", 0), a["run_aces"])
        a["no_ace"] = 0
    else:
        a["no_ace"] = a.get("no_ace", 0) + 1
        a["no_ace_max"] = max(a.get("no_ace_max", 0), a["no_ace"])
    fair = ace and not eng.st.all_aces and any(x[0] != "A" for x in eng.deck)
    a["ace_run"] = a.get("ace_run", 0) + 1 if fair else 0
    a["ace_run_fair"] = max(a.get("ace_run_fair", 0), a["ace_run"])
    ri = RANKS.index(r) if r in RANKS else 13
    a["asc"] = a.get("asc", 1) + 1 if ri == a.get("last_ri", -5) + 1 else 1
    a["last_ri"] = ri
    a["asc_max"] = max(a.get("asc_max", 0), a["asc"])
    ident = (r, card.suit)
    a["ident"] = a.get("ident", 0) + 1 if a.get("last_ident") == list(ident) else 1
    a["last_ident"] = list(ident)
    a["ident_max"] = max(a.get("ident_max", 0), a["ident"])
    if card.rarity <= 1e-6:
        a["ultra"] = a.get("ultra", 0) + 1
        a["ultra_run"] = a.get("ultra_run", 0) + 1
    elif not card.dup:
        a["ultra_run"] = 0
    a["ultra_run_max"] = max(a.get("ultra_run_max", 0), a.get("ultra_run", 0))
    if card.rarity <= 1e-3 and p.cards <= 10:
        a["early_rare"] = True
    mods = len(card.buffs) + len(card.debuffs)
    a["max_mods"] = max(a.get("max_mods", 0), mods)
    a["max_debuffs"] = max(a.get("max_debuffs", 0), len(card.debuffs))
    a["max_mult_buffs"] = max(a.get("max_mult_buffs", 0), sum(1 for b in card.buffs if b in MULT_BUFFS))
    if card.buffs and card.debuffs:
        a["buff_and_debuff"] = True
    if card.debuffs:
        a["any_debuff"] = True
    if gained < 0:
        a["negative_pay"] = True
    if "AA" in card.ranks:
        a["aa"] = True
    if "AAA" in card.ranks:
        a["aaa"] = True
    run_mods = a.setdefault("run_rare", {})
    for m in card.buffs + card.debuffs:
        if m in RARE_MODS:
            run_mods[m] = run_mods.get(m, 0) + 1
            if run_mods[m] >= 3:
                a["rare_triple"] = True
    if gained > 0:
        base = max(1, card.base_value())
        a["max_log_mult"] = max(a.get("max_log_mult", 0), gained.log10() - Big(base).log10())
        a["run_best_log"] = max(a.get("run_best_log", 0), gained.log10() - Big(base).log10())
        if high_before > 0 and gained > high_before:
            a["beat_high"] = True
        if best_before > 0 and gained >= best_before * 100:
            a["record_x100"] = True
    if 0 <= float(gained) < 10 and p.lifetime >= 1e12:
        a["pocket"] = True
    a["perk_log_max"] = max(a.get("perk_log_max", 0), eng.perks.last_log_mult)
    if p.run_earned >= 1e6 and p.playtime - a.get("run_start", 0) <= 300:
        a["speedrun"] = True
    if p.playtime - a.get("run_start", 0) >= 86400:
        a["long_run"] = True
    if (p.transcends or p.shatters) and p.lifetime > 0 and p.run_earned >= p.lifetime * 0.99:
        a["rich_run"] = True


def new_run(p):
    a = p.ach
    a["run_start"] = p.playtime
    a["run_buys"] = 0
    a["run_aces"] = 0
    a["run_rare"] = {}
    a["run_mult"] = False
    a["run_speed"] = False
    a["run_best_log"] = 0.0


def check(p, eng):
    """Returns the achievements that just unlocked."""
    a = p.ach
    got = []
    for name, _desc, chk, _pr, secret in ALL:
        if name in p.achievements:
            continue
        try:
            ok = chk(p, a, eng)
        except (ValueError, OverflowError, KeyError):
            ok = False
        if ok:
            p.achievements.append(name)
            got.append(name)
            if secret and name != "You Weren't Supposed to See This":
                a["secret_any"] = True
    return got


SECRET_NAMES = {s[0] for s in SECRET}
FACE_RANKS = FACE


ICON_DIRS = ("Achievements 1", "Achievements 2")     # icons are split in two folders (GitHub uploads 100 at a time)
_ASSETS = Path(__file__).resolve().parent.parent


@functools.cache
def icon_name(name):
    """The file of an achievement's icon in assets\\Achievements 1 or 2 (made by _claude_tools\\infinideck_art.py)."""
    out = re.sub(r"[^a-z0-9]+", "_", name.lower().replace("²", "2")).strip("_") or "dots"
    for folder in ICON_DIRS:
        if (_ASSETS / folder / f"{out}.png").exists():
            return f"{folder}/{out}"
    return f"{ICON_DIRS[0]}/{out}"
