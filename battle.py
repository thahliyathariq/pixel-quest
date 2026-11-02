"""
battle.py  -  the strategy rules of the game (no graphics!).

Run it to play a text version in the terminal:
    python battle.py

Later, the pygame battle screen will use the same Battle class,
so the rules only exist in ONE place.
"""
import random

from data import load_monsters

# ---------------------------------------------------------------
#  TWEAK THESE NUMBERS TO BALANCE THE GAME
# ---------------------------------------------------------------
SPECIAL_MULT = 1.8      # special move hits 1.8x harder...
SPECIAL_COOLDOWN = 3    # ...but needs 3 of the unit's turns to recharge
TYPE_BONUS = 1.3        # extra damage when the attacker's type beats the target's
TEAM_SIZE = 3

# who is strong against whom (edit freely; unknown types just get no bonus)
TYPE_BEATS = {
    "dragon": ["humanoid", "beast", "giant"],
    "undead": ["humanoid", "beast", "celestial"],
    "fiend": ["celestial", "humanoid", "fey"],
    "celestial": ["fiend", "undead", "aberration"],
    "humanoid": ["monstrosity", "beast", "ooze"],
    "beast": ["plant", "ooze", "fey"],
    "giant": ["humanoid", "construct", "beast"],
    "elemental": ["plant", "construct", "beast"],
    "aberration": ["humanoid", "giant", "beast"],
    "monstrosity": ["beast", "plant", "fey"],
    "construct": ["fey", "ooze", "plant"],
    "fey": ["giant", "dragon", "humanoid"],
    "plant": ["ooze", "construct", "humanoid"],
    "ooze": ["plant", "beast", "construct"],
}


def player_budget(level):
    """Points the player can spend on their team at this level."""
    return 7 + level * 3


def enemy_budget(level):
    """Points the enemy team is built from (3 fewer than yours)."""
    return 4 + level * 3


# ---------------------------------------------------------------
#  UNIT: one monster in a fight
# ---------------------------------------------------------------
def game_hp(monster):
    """D&D hit points go from 1 to 600+, so we squash them into a fair range."""
    return 20 + round(monster["hp"] ** 0.75)


class Unit:
    def __init__(self, monster, side):
        self.monster = monster    # the original data row (the screen needs it for drawing)
        self.name = monster["name"]
        self.type = monster["type"]
        self.max_hp = game_hp(monster)
        self.hp = self.max_hp
        self.attack = monster["attack"]
        self.defense = monster["defense"]
        self.speed = monster["speed"]
        self.side = side          # "player" or "enemy"
        self.defending = False
        self.cooldown = 0

    @property
    def alive(self):
        return self.hp > 0

    @property
    def can_special(self):
        return self.cooldown == 0


# ---------------------------------------------------------------
#  BATTLE
# ---------------------------------------------------------------
class Battle:
    def __init__(self, player_monsters, enemy_monsters):
        self.player = [Unit(m, "player") for m in player_monsters]
        self.enemy = [Unit(m, "enemy") for m in enemy_monsters]
        self.round = 0
        self.queue = []       # units still waiting for their turn this round
        self.active = None    # the unit whose turn it is right now
        self.log = []         # every message, so the screen can show them later
        self.next_turn()

    # ---- helpers ----
    def say(self, text):
        self.log.append(text)

    def foes_of(self, unit):
        team = self.enemy if unit.side == "player" else self.player
        return [u for u in team if u.alive]

    def winner(self):
        if not any(u.alive for u in self.enemy):
            return "player"
        if not any(u.alive for u in self.player):
            return "enemy"
        return None

    # ---- turn order: fastest unit goes first ----
    def next_turn(self):
        if self.winner():
            self.active = None
            return
        while True:
            while self.queue:
                unit = self.queue.pop(0)
                if unit.alive:
                    self.active = unit
                    unit.defending = False      # last turn's guard ends now
                    if unit.cooldown > 0:
                        unit.cooldown -= 1
                    return
            self.round += 1
            living = [u for u in self.player + self.enemy if u.alive]
            living.sort(key=lambda u: (-u.speed, random.random()))
            self.queue = living
            self.say(f"--- Round {self.round} ---")

    # ---- damage ----
    def calc_damage(self, attacker, target, special):
        base = attacker.attack * 0.6 + random.randint(0, 4) - target.defense * 0.25
        if special:
            base *= SPECIAL_MULT
        effective = target.type in TYPE_BEATS.get(attacker.type, [])
        if effective:
            base *= TYPE_BONUS
        if target.defending:
            base *= 0.5
        return max(2, round(base)), effective

    # ---- the three actions: "attack", "defend", "special" ----
    def perform(self, action, target=None):
        unit = self.active
        if unit is None:
            return

        if action == "defend":
            unit.defending = True
            self.say(f"{unit.name} braces for impact!")
        else:
            special = action == "special"
            if special and not unit.can_special:
                raise ValueError("Special is still recharging.")
            if target is None or not target.alive or target.side == unit.side:
                raise ValueError("Pick a living enemy as the target.")

            damage, effective = self.calc_damage(unit, target, special)
            target.hp = max(0, target.hp - damage)
            move = "uses a SPECIAL move on" if special else "attacks"
            guard = " (guarding!)" if target.defending else ""
            self.say(f"{unit.name} {move} {target.name} for {damage} damage{guard}.")
            if effective:
                self.say("  It's super effective!")
            if not target.alive:
                self.say(f"  {target.name} is defeated!")
            if special:
                unit.cooldown = SPECIAL_COOLDOWN

        self.next_turn()

    # ---- simple enemy brain ----
    def enemy_choose(self):
        unit = self.active
        target = min(self.foes_of(unit), key=lambda f: f.hp)   # go for the weakest
        if unit.hp < unit.max_hp * 0.3 and random.random() < 0.3:
            return "defend", None
        if unit.can_special and random.random() < 0.6:
            return "special", target
        return "attack", target


# ---------------------------------------------------------------
#  BUILD AN ENEMY TEAM FOR A LEVEL (used by the real game too)
# ---------------------------------------------------------------
def make_enemy_team(monsters, level, size=TEAM_SIZE):
    budget = enemy_budget(level)
    cheapest = min(m["cost"] for m in monsters)
    team = []
    for slot in range(size):
        slots_left = size - slot - 1
        limit = budget - sum(m["cost"] for m in team) - slots_left * cheapest
        options = [m for m in monsters if m["cost"] <= limit]
        if not options:
            options = [min(monsters, key=lambda m: m["cost"])]
        options = [m for m in options if m not in team] or options   # no duplicates
        options.sort(key=lambda m: m["cost"], reverse=True)
        team.append(random.choice(options[:5]))   # spend the budget on strong picks
    return team


# ---------------------------------------------------------------
#  TERMINAL TEST GAME  (python battle.py)
# ---------------------------------------------------------------
def show_teams(battle):
    print()
    for label, team in (("YOUR TEAM", battle.player), ("ENEMY TEAM", battle.enemy)):
        print(label)
        for i, u in enumerate(team, 1):
            status = "DEFEATED" if not u.alive else f"HP {u.hp}/{u.max_hp}"
            print(f"  {i}. {u.name:22} ({u.type:11}) {status}")
    print()


def choose_team(monsters, level):
    budget = player_budget(level)
    pool = random.sample(monsters, min(15, len(monsters)))
    pool.sort(key=lambda m: (m["cost"], m["name"]))
    print(f"\nLEVEL {level}  -  choose up to {TEAM_SIZE} monsters. Budget: {budget} points\n")
    for i, m in enumerate(pool, 1):
        print(f"  {i:2}. {m['name']:22} {m['type']:11} cost {m['cost']:2}  "
              f"HP {m['hp']:4}  ATK {m['attack']:2}  DEF {m['defense']:2}  SPD {m['speed']:2}")
    while True:
        raw = input(f"\nType up to {TEAM_SIZE} numbers separated by spaces: ").split()
        try:
            picks = [pool[int(n) - 1] for n in raw]
        except (ValueError, IndexError):
            print("Please type valid numbers from the list.")
            continue
        if not picks or len(set(map(id, picks))) != len(picks) or len(picks) > TEAM_SIZE:
            print(f"Pick 1 to {TEAM_SIZE} different monsters.")
        elif sum(m["cost"] for m in picks) > budget:
            print("That team costs too much!")
        else:
            return picks


def ask_player(battle):
    unit = battle.active
    foes = battle.foes_of(unit)
    ready = "ready" if unit.can_special else f"recharging ({unit.cooldown})"
    print(f"\n>>> {unit.name}'s turn.  [a]ttack  [d]efend  [s]pecial ({ready})")
    while True:
        choice = input("Your move: ").strip().lower()[:1]
        if choice == "d":
            return "defend", None
        if choice in ("a", "s"):
            if choice == "s" and not unit.can_special:
                print("Special is still recharging.")
                continue
            if len(foes) == 1:
                return ("attack" if choice == "a" else "special"), foes[0]
            for i, f in enumerate(foes, 1):
                print(f"   {i}. {f.name} (HP {f.hp}/{f.max_hp})")
            try:
                target = foes[int(input("Target number: ")) - 1]
            except (ValueError, IndexError):
                print("Not a valid target.")
                continue
            return ("attack" if choice == "a" else "special"), target
        print("Type a, d or s.")


def terminal_game():
    monsters, _ = load_monsters()
    if len(monsters) < 5:
        print("Not enough monsters loaded. Run  python data.py  to check your data.")
        return
    level = 1
    picks = choose_team(monsters, level)
    battle = Battle(picks, make_enemy_team(monsters, level))
    shown = 0
    while not battle.winner():
        if battle.active.side == "player":
            show_teams(battle)
            action, target = ask_player(battle)
        else:
            action, target = battle.enemy_choose()
        try:
            battle.perform(action, target)
        except ValueError as error:
            print(error)
            continue
        for line in battle.log[shown:]:
            print(line)
        shown = len(battle.log)

    show_teams(battle)
    print("YOU WIN!" if battle.winner() == "player" else "YOU LOSE...")


if __name__ == "__main__":
    terminal_game()


           