"""
data.py  -  loads the D&D monsters CSV and turns each row into a game unit.

Run this file on its own to check that your dataset was understood:
    python data.py
"""
import math
import random
import re

import pandas as pd

# >>> Change this if your CSV lives somewhere else <<<
CSV_PATH = "data/Dd5e_monsters.csv"


# ---------------------------------------------------------------
#  SMALL HELPERS
# ---------------------------------------------------------------
def first_number(value):
    """Pull the first number out of messy text.
    '135 (18d10+36)' -> 135.0     '17 (natural armor)' -> 17.0     'abc' -> nan"""
    match = re.search(r"\d+(?:\.\d+)?", str(value))
    return float(match.group()) if match else math.nan


def challenge_value(value):
    """Challenge rating can be '1/2', '1/4' or '5 (1,800 XP)'."""
    text = str(value).strip()
    fraction = re.match(r"(\d+)\s*/\s*(\d+)", text)
    if fraction:
        return int(fraction.group(1)) / int(fraction.group(2))
    return first_number(text)


SIZES = ("tiny", "small", "medium", "large", "huge", "gargantuan")
SIZE_BONUS = {"tiny": -1, "small": 0, "medium": 1, "large": 2, "huge": 3, "gargantuan": 4}


def clean_type(value):
    """'Large dragon, lawful evil' -> 'dragon'.  Used later to colour the sprites."""
    text = str(value).split(",")[0].lower()
    text = re.sub(r"\(.*?\)", "", text)
    words = [w for w in re.findall(r"[a-z]+", text) if w not in SIZES]
    return words[-1] if words else "monster"


def find_column(df, candidates):
    """Find a column even if it is spelled a bit differently in your file."""
    cols = {c: c.lower().strip() for c in df.columns}
    for cand in candidates:  # 1) exact match
        for c, low in cols.items():
            if low == cand:
                return c
    for cand in candidates:  # 2) whole-word match
        for c, low in cols.items():
            if cand in re.findall(r"[a-z]+", low):
                return c
    for cand in candidates:  # 3) partial match (long words only)
        if len(cand) >= 4:
            for c, low in cols.items():
                if cand in low:
                    return c
    return None


# ---------------------------------------------------------------
#  MAIN FUNCTION
# ---------------------------------------------------------------
def load_monsters(path=CSV_PATH):
    """Returns (monsters, columns_used).
    monsters is a list of dicts: name, type, hp, attack, defense, speed, cr, cost"""
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]

    cols = {
        "name": find_column(df, ["name"]) or df.columns[0],
        "hp": find_column(df, ["hp", "hitpoints", "hit"]),
        "armor": find_column(df, ["armor", "armour", "ac"]),
        "cr": find_column(df, ["challenge", "cr", "rating"]),
        "type": find_column(df, ["type", "race"]),
        "size": find_column(df, ["size"]),
        "speed": find_column(df, ["speed"]),
        # optional: only some datasets have ability scores
        "str": find_column(df, ["str", "strength"]),
        "dex": find_column(df, ["dex", "dexterity"]),
    }

    missing = [k for k in ("hp", "armor", "cr") if cols[k] is None]
    if missing:
        raise ValueError(
            f"Could not find columns for: {missing}.\n"
            f"The columns in your file are: {list(df.columns)}"
        )

    monsters = []
    seen = set()
    for _, row in df.iterrows():
        name = str(row[cols["name"]]).strip()
        if not name or name.lower() == "nan" or name in seen:
            continue

        hp = first_number(row[cols["hp"]])
        armor = first_number(row[cols["armor"]])
        cr = challenge_value(row[cols["cr"]])
        if any(pd.isna(v) for v in (hp, armor, cr)):
            continue  # skip rows with missing numbers

        # ---- attack ----
        rng = random.Random(name)   # same monster always gets the same little variation
        if cols["str"] and cols["dex"]:
            strength = first_number(row[cols["str"]])
            dex = first_number(row[cols["dex"]])
        else:
            strength = dex = math.nan
        if not pd.isna(strength) and not pd.isna(dex):
            attack = 0.5 * max(strength, dex) + 0.5 * (8 + 0.8 * cr)
        else:
            # no ability scores in this file: build attack from challenge rating + size
            size_text = str(row[cols["size"]]).strip().lower() if cols["size"] else ""
            attack = 8 + 0.9 * cr + SIZE_BONUS.get(size_text, 1) + rng.randint(-2, 2)

        # ---- speed (feet per turn in D&D -> small game number) ----
        feet = first_number(row[cols["speed"]]) if cols["speed"] else math.nan
        if pd.isna(feet) and cols["dex"]:
            feet = first_number(row[cols["dex"]]) * 3
        speed = 6 if pd.isna(feet) else max(1, int(round(feet / 5)))

        seen.add(name)
        monsters.append({
            "name": name,
            "type": clean_type(row[cols["type"]]) if cols["type"] else "monster",
            "hp": int(hp),
            "attack": max(3, int(round(attack))),
            "defense": int(armor),
            "speed": speed,
            "cr": cr,
            "cost": int(round(cr)) + 1,   # stronger monsters cost more points
        })

    monsters.sort(key=lambda m: (m["cost"], m["name"]))
    return monsters, cols


# ---------------------------------------------------------------
#  CHECK REPORT  (runs only when you do:  python data.py)
# ---------------------------------------------------------------
if __name__ == "__main__":
    try:
        monsters, cols = load_monsters()
    except Exception as error:
        print("PROBLEM:", error)
        raise SystemExit

    print("Columns I matched in your file:")
    for key, col in cols.items():
        print(f"  {key:6} -> {col}")
    print()
    print(f"Monsters ready for the game: {len(monsters)}")
    print()
    print("Weakest 3:")
    for m in monsters[:3]:
        print("  ", m)
    print("Strongest 3:")
    for m in monsters[-3:]:
        print("  ", m)