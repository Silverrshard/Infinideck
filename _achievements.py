"""The 100 achievements (50 normal, 50 secret) and the stats that track them.
Each entry: name, description, check(p, a, eng), progress(p, a) -> (have, need) or None."""
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
    ("Infinideck", "Unlock all 99 other achievements.", lambda p, a, e: len(p.achievements) >= 99, None),
]
# Only these 20 stay secret; the other 30 from the design's secret list are normal achievements (asked for after
# a playtest: 50 hidden ones were too many).
KEEP_SECRET = {"...", "You Weren't Supposed to See This", "Wrong Place, Wrong Time", "The Forbidden Number",
               "It Was Supposed to Be Impossible", "Nothing to See Here", "We Don't Talk About That", "The End?",
               "The Beginning.", "Against All Odds", "Unreasonably Lucky", "The Deck Is Lying", "Mathematical Error",
               "What Comes After?", "Pocket Change", "The Collector's Curse", "Chaos Theory", "Rules Are Suggestions",
               "The Impossible Hand", "Infinideck"}
NORMAL = NORMAL + [s for s in SECRET if s[0] not in KEEP_SECRET]
SECRET = [s for s in SECRET if s[0] in KEEP_SECRET]
ALL = [(n, d, c, pr, False) for n, d, c, pr in NORMAL] + [(n, d, c, pr, True) for n, d, c, pr in SECRET]
assert len(NORMAL) == 80 and len(SECRET) == 20
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
