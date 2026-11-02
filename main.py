import math
import random
import sys

import pygame

from battle import Battle, make_enemy_team, player_budget, game_hp, TEAM_SIZE
from data import load_monsters

# ---------------------------------------------------------------
#  LOAD THE DATASET FIRST (so any problem shows up as a clear message)
# ---------------------------------------------------------------
try:
    MONSTERS, _columns = load_monsters()
except Exception as error:
    print("Could not load the monsters:", error)
    print("Run  python data.py  to see what is wrong.")
    sys.exit()
if len(MONSTERS) < 10:
    print("Only", len(MONSTERS), "monsters loaded - that is too few. Run  python data.py  to check.")
    sys.exit()

# ---------------------------------------------------------------
#  SETUP
#  We draw everything on a SMALL canvas (200 x 150 pixels) and then
#  scale it up 4x. That is what gives the big, chunky pixel look.
# ---------------------------------------------------------------
pygame.init()
W, H = 200, 150
SCALE = 4
window = pygame.display.set_mode((W * SCALE, H * SCALE))
pygame.display.set_caption("Pixel Quest")
canvas = pygame.Surface((W, H))
clock = pygame.time.Clock()

# Text is drawn on the full-size window (not the tiny canvas), so it stays sharp.
# These sizes are in real screen pixels. Make them bigger or smaller to taste.
FONT_BIG = pygame.font.Font(None, 44)
FONT_SMALL = pygame.font.Font(None, 38)
FONT_TINY = pygame.font.Font(None, 34)

# ---------------------------------------------------------------
#  COLOURS (night palette: black, dark blue, blue, light blue)
# ---------------------------------------------------------------
BLACK = (4, 6, 16)
NAVY = (10, 20, 60)
DARK = (18, 38, 96)
BLUE = (34, 84, 170)
LIGHT = (110, 170, 232)
FOAM = (205, 232, 255)
WHITE = (235, 244, 255)
GREY = (60, 70, 100)
KEY = (255, 0, 255)  # "see-through" colour used for the rocks layer

# ---------------------------------------------------------------
#  WITCH SPRITE
#  Each letter is one pixel. '.' means empty.
# ---------------------------------------------------------------
WITCH = [
    ".......HH.......",
    "......HHHH......",
    "......HHHH......",
    ".....HHHHHH.....",
    ".....HHHHHH.....",
    "....HHHHHHHH....",
    "....HYYYYYYH....",
    "...HHHHHHHHHH...",
    ".HHHHHHHHHHHHHH.",
    "....SSSSSSSS....",
    "....SEESSEES....",
    "....SSSSSSSS....",
    "....SSSMMSSS....",
    ".....SSSSSS.....",
    "....RRRRRRRR....",
    "...RRRRRRRRRR...",
    "..SRRRRrRRRRRS..",
    "..RRRRRrRRRRRR..",
    "..RRRRRRRRRRRR..",
    ".RRRRRRRRRRRRRR.",
    ".RRRRRRRRRRRRRR.",
    "..BB........BB..",
]
WITCH_COLOURS = {
    "H": (46, 24, 84),
    "Y": (240, 200, 60),
    "S": (110, 190, 120),
    "E": (255, 240, 120),
    "M": (30, 50, 40),
    "R": (96, 44, 150),
    "r": (140, 90, 200),
    "B": (14, 10, 26),
}


def draw_sprite(surf, rows, colours, x, y):
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch != ".":
                surf.set_at((x + i, y + j), colours[ch])


# ---------------------------------------------------------------
#  MONSTER SPRITES (drawn by the computer from each monster's name + type)
#  Same name = same monster look every time. Colour comes from the type.
# ---------------------------------------------------------------
TYPE_COLOURS = {
    "dragon": (210, 70, 70), "undead": (150, 150, 200), "fiend": (200, 50, 100),
    "beast": (180, 125, 65), "humanoid": (95, 175, 115), "aberration": (145, 85, 205),
    "giant": (205, 155, 75), "ooze": (80, 205, 165), "celestial": (240, 230, 145),
    "elemental": (240, 145, 55), "construct": (150, 165, 175), "fey": (230, 135, 225),
    "plant": (75, 175, 65), "monstrosity": (205, 115, 45),
}
DEFAULT_COLOUR = (150, 175, 205)
SPRITE_CACHE = {}


def sprite_scale(monster):
    """Big monsters are drawn bigger."""
    return 3 if monster["hp"] >= 200 else 2


def monster_sprite(monster, scale, faded=False):
    key = (monster["name"], scale, faded)
    if key in SPRITE_CACHE:
        return SPRITE_CACHE[key]

    rng = random.Random(monster["name"])
    body = TYPE_COLOURS.get(monster["type"], DEFAULT_COLOUR)
    edge = tuple(c // 2 for c in body)

    # build the left half of an 8x8 grid, then mirror it for the right half
    half = [[False] * 4 for _ in range(8)]
    for r in range(8):
        for c in range(4):
            chance = 0.75 if 1 <= r <= 6 else 0.4
            if c == 3 and 1 <= r <= 6:
                chance = 1.0          # solid middle keeps it in one piece
            half[r][c] = rng.random() < chance
    half[3][2] = True                 # make sure the eyes have a face to sit on
    grid = [half[r] + half[r][::-1] for r in range(8)]

    surf = pygame.Surface((8 * scale, 8 * scale), pygame.SRCALPHA)
    for r in range(8):
        for c in range(8):
            if not grid[r][c]:
                continue
            border = False
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                rr, cc = r + dr, c + dc
                if not (0 <= rr < 8 and 0 <= cc < 8) or not grid[rr][cc]:
                    border = True
            colour = edge if border else body
            pygame.draw.rect(surf, colour, (c * scale, r * scale, scale, scale))
    for c in (2, 5):                  # eyes
        pygame.draw.rect(surf, (255, 240, 120), (c * scale, 3 * scale, scale, scale))

    if faded:
        surf.set_alpha(70)
    SPRITE_CACHE[key] = surf
    return surf


def blit_monster(monster, box_x, box_y, box=24, faded=False, scale=None):
    """Draw a monster centred inside a square box."""
    sprite = monster_sprite(monster, scale or sprite_scale(monster), faded)
    canvas.blit(sprite, (box_x + (box - sprite.get_width()) // 2,
                         box_y + (box - sprite.get_height()) // 2))


# ---------------------------------------------------------------
#  TEXT + DRAWING HELPERS
# ---------------------------------------------------------------
TEXT_QUEUE = []   # text waits here until the pixel art has been scaled up


def draw_text(surf, s, cx, cy, colour, font):
    """Centered text. Position is in canvas pixels (same as everything else)."""
    TEXT_QUEUE.append((s, cx, cy, colour, font, "center"))


def draw_text_left(surf, s, x, cy, colour, font):
    TEXT_QUEUE.append((s, x, cy, colour, font, "left"))


def draw_text_right(surf, s, right_x, cy, colour, font):
    TEXT_QUEUE.append((s, right_x, cy, colour, font, "right"))


def flush_text():
    """Draw all queued text on the big window, crisp and on top of the pixel art."""
    for s, x, cy, colour, font, align in TEXT_QUEUE:
        if not s:
            continue
        img = font.render(s, True, colour)
        shadow = font.render(s, True, BLACK)
        px = x * SCALE
        if align == "center":
            px -= img.get_width() // 2
        elif align == "right":
            px -= img.get_width()
        py = cy * SCALE - img.get_height() // 2
        window.blit(shadow, (px + 2, py + 2))
        window.blit(img, (px, py))
    TEXT_QUEUE.clear()


def fit_text(font, s, max_w):
    """Shorten text with '..' if it is too wide (max_w is in canvas pixels)."""
    limit = max_w * SCALE
    if font.size(s)[0] <= limit:
        return s
    while len(s) > 1 and font.size(s + "..")[0] > limit:
        s = s[:-1]
    return s + ".."


def wrap_text(font, s, max_w):
    """Split text into lines that fit a width (max_w is in canvas pixels)."""
    limit = max_w * SCALE
    lines, current = [], ""
    for word in s.split():
        test = (current + " " + word).strip()
        if font.size(test)[0] <= limit:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_panel(x, y, w, h):
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    panel.fill((4, 8, 24, 220))
    canvas.blit(panel, (x, y))
    pygame.draw.rect(canvas, LIGHT, (x, y, w, h), 1)


def draw_pine(surf, x, base, height):
    for i in range(height):
        half = 1 + i // 2
        pygame.draw.line(surf, (3, 7, 18), (x - half, base - height + i), (x + half, base - height + i))
    pygame.draw.rect(surf, (3, 7, 18), (x - 1, base, 2, 3))


# ---------------------------------------------------------------
#  STATIC BACKGROUND PIECES (drawn once, reused every frame)
# ---------------------------------------------------------------
random.seed(7)

sky = pygame.Surface((W, H))
for y in range(H):
    band = (y // 10) / (H // 10)
    colour = (int(4 + 12 * band), int(6 + 30 * band), int(20 + 60 * band))
    pygame.draw.line(sky, colour, (0, y), (W, y))
pygame.draw.polygon(sky, (8, 16, 46),
                    [(0, 60), (25, 38), (45, 52), (70, 30), (95, 55), (125, 34),
                     (150, 54), (175, 36), (200, 50), (200, 100), (0, 100)])
pygame.draw.circle(sky, (225, 235, 255), (165, 22), 8)
pygame.draw.circle(sky, (8, 16, 46), (169, 19), 7)
pygame.draw.circle(sky, (60, 90, 150), (165, 22), 11, 1)

stars = [(random.randint(2, W - 3), random.randint(2, 40), random.randint(0, 3)) for _ in range(30)]

rocks = pygame.Surface((W, H))
rocks.fill(KEY)
rocks.set_colorkey(KEY)
LEFT_STEPS = [(0, 20, 26), (20, 40, 32), (40, 56, 37), (56, 72, 41)]
RIGHT_STEPS = [(128, 144, 41), (144, 162, 36), (162, 180, 30), (180, 200, 24)]
for x0, x1, top in LEFT_STEPS + RIGHT_STEPS:
    pygame.draw.rect(rocks, (12, 18, 42), (x0, top, x1 - x0, 118 - top))
    pygame.draw.line(rocks, (40, 66, 120), (x0, top), (x1 - 1, top))
for _ in range(260):
    sx, sy = random.randint(0, W - 1), random.randint(24, 117)
    if tuple(rocks.get_at((sx, sy)))[:3] != KEY:
        rocks.set_at((sx, sy), random.choice([(22, 32, 70), (8, 12, 30), (28, 44, 90)]))
draw_pine(rocks, 30, 32, 14)
draw_pine(rocks, 48, 37, 11)
draw_pine(rocks, 152, 36, 13)
draw_pine(rocks, 190, 24, 12)

FALL_X0, FALL_X1 = 72, 128
FALL_Y0, FALL_Y1 = 38, 118
col_phase = {x: random.randint(0, 15) for x in range(FALL_X0, FALL_X1)}
col_speed = {x: random.choice([2, 3, 3, 4]) for x in range(FALL_X0, FALL_X1)}

# overlays that darken the background so text is easy to read
dim = pygame.Surface((W, H))
dim.fill((0, 0, 10))
dim.set_alpha(110)
dim_dark = pygame.Surface((W, H))
dim_dark.fill((0, 0, 10))
dim_dark.set_alpha(165)


def draw_background(t):
    canvas.blit(sky, (0, 0))

    for sx, sy, ph in stars:
        c = FOAM if (t // 20 + ph) % 4 else BLUE
        canvas.set_at((sx, sy), c)

    canvas.blit(rocks, (0, 0))

    for x in range(FALL_X0, FALL_X1):
        edge = x < FALL_X0 + 2 or x > FALL_X1 - 3
        for y in range(FALL_Y0, FALL_Y1):
            if y < 42:
                c = BLUE if (x + y + t // 12) % 7 else LIGHT
            else:
                v = (y * 2 - (t * col_speed[x]) // 2 + col_phase[x]) % 16
                if v < 3:
                    c = FOAM
                elif v < 8:
                    c = LIGHT
                elif v < 12:
                    c = BLUE
                else:
                    c = DARK
                if edge:
                    c = DARK if v < 8 else NAVY
            canvas.set_at((x, y), c)

    pygame.draw.rect(canvas, DARK, (0, 118, W, H - 118))
    pygame.draw.rect(canvas, BLUE, (0, 118, W, 3))
    for i in range(16):
        ry = 122 + (i * 7) % 26
        rx = (i * 53 + t // (2 + i % 3)) % (W + 20) - 10
        length = 6 + i % 5
        colour = LIGHT if i % 2 else (60, 110, 190)
        pygame.draw.line(canvas, colour, (rx, ry), (rx + length, ry))
    for k in range(5):
        w = 8 - k
        colour = (150, 195, 235) if (t // 10 + k) % 2 else (80, 130, 205)
        pygame.draw.line(canvas, colour, (165 - w, 122 + k * 5), (165 + w, 122 + k * 5))

    for i in range(20):
        mx = int(100 + math.sin(t * 0.04 + i * 1.7) * 32)
        my = int(117 + math.cos(t * 0.06 + i * 2.3) * 3)
        pygame.draw.circle(canvas, FOAM if i % 2 else LIGHT, (mx, my), 2)


# ---------------------------------------------------------------
#  BUTTON
# ---------------------------------------------------------------
class Button:
    def __init__(self, label, x, y, w, h, font=None):
        self.label = label
        self.rect = pygame.Rect(x, y, w, h)
        self.font = font or FONT_BIG

    def hovered(self, mx, my):
        return self.rect.collidepoint(mx, my)

    def draw(self, surf, mx, my, enabled=True):
        hover = enabled and self.hovered(mx, my)
        if enabled:
            border = FOAM if hover else LIGHT
            fill = BLUE if hover else DARK
            text_colour = WHITE if hover else FOAM
        else:
            border, fill, text_colour = GREY, (20, 26, 48), GREY
        pygame.draw.rect(surf, border, self.rect)
        pygame.draw.rect(surf, fill, self.rect.inflate(-2, -2))
        draw_text(surf, self.label, self.rect.centerx, self.rect.centery, text_colour, self.font)


# ---------------------------------------------------------------
#  SCREEN: MAIN MENU
# ---------------------------------------------------------------
menu_buttons = {
    "yes": Button("YES", 72, 56, 56, 14),
    "no": Button("NO", 72, 74, 56, 14),
    "exit": Button("EXIT", 72, 92, 56, 14),
}


def draw_menu(t, mx, my, title):
    draw_background(t)
    bob = int(math.sin(t * 0.08) * 1)
    draw_sprite(canvas, WITCH, WITCH_COLOURS, 2, 4 + bob)

    panel = pygame.Surface((84, 84), pygame.SRCALPHA)
    panel.fill((4, 8, 24, 215))
    canvas.blit(panel, (58, 32))
    pygame.draw.rect(canvas, LIGHT, (58, 32, 84, 84), 1)
    pygame.draw.rect(canvas, BLUE, (60, 34, 80, 80), 1)

    draw_text(canvas, title, 100, 45, FOAM, FONT_BIG)
    for b in menu_buttons.values():
        b.draw(canvas, mx, my)


# ---------------------------------------------------------------
#  SCREEN: LEVEL MAP
# ---------------------------------------------------------------
NODES = [(62, 126), (98, 118), (82, 92), (68, 66), (96, 46), (130, 56), (166, 50)]
NODE_R = 7


def node_at(mx, my):
    for i, (x, y) in enumerate(NODES):
        if (mx - x) ** 2 + (my - y) ** 2 <= NODE_R ** 2:
            return i
    return None


def draw_map(t, mx, my, unlocked):
    draw_background(t)
    canvas.blit(dim, (0, 0))

    for i in range(len(NODES) - 1):
        colour = LIGHT if i + 1 < unlocked else GREY
        pygame.draw.line(canvas, colour, NODES[i], NODES[i + 1], 2)

    hover = node_at(mx, my)
    for i, (x, y) in enumerate(NODES):
        is_open = i < unlocked
        if is_open:
            fill = BLUE if hover == i else DARK
            border = FOAM if hover == i else LIGHT
            text_colour = WHITE
        else:
            fill, border, text_colour = (20, 26, 48), GREY, GREY
        pygame.draw.circle(canvas, border, (x, y), NODE_R)
        pygame.draw.circle(canvas, fill, (x, y), NODE_R - 1)
        draw_text(canvas, str(i + 1), x, y, text_colour, FONT_SMALL)
    draw_text(canvas, "END", NODES[-1][0] + 2, NODES[-1][1] + 14, FOAM, FONT_SMALL)

    bob = int(math.sin(t * 0.08) * 1)
    draw_sprite(canvas, WITCH, WITCH_COLOURS, 8, 104 + bob)
    pygame.draw.rect(canvas, BLACK, (3, 62, 50, 25))
    pygame.draw.rect(canvas, WHITE, (4, 63, 48, 23))
    pygame.draw.polygon(canvas, WHITE, [(16, 86), (24, 86), (16, 96)])
    draw_text(canvas, "ARE YOU", 28, 70, BLACK, FONT_SMALL)
    draw_text(canvas, "READY?", 28, 80, BLACK, FONT_SMALL)


# ---------------------------------------------------------------
#  SCREEN: TEAM SELECT
# ---------------------------------------------------------------
ROWS_PER_PAGE = 8
ROW_H = 11
page_prev = Button("<", 4, 108, 20, 12, FONT_SMALL)
page_next = Button(">", 28, 108, 20, 12, FONT_SMALL)
team_back = Button("BACK", 4, 132, 44, 14, FONT_SMALL)
team_fight = Button("FIGHT!", 120, 132, 76, 14)


def team_row_rect(i):
    return pygame.Rect(4, 16 + i * ROW_H, 108, ROW_H - 1)


def roster_sorted(roster):
    return sorted(roster, key=lambda m: (m["cost"], m["name"]))


def draw_team(t, mx, my, roster, selected, level, page, flash_text):
    draw_background(t)
    canvas.blit(dim_dark, (0, 0))

    budget = player_budget(level)
    spent = sum(m["cost"] for m in selected)
    draw_text_left(canvas, f"LEVEL {level} - YOUR TEAM", 4, 7, FOAM, FONT_TINY)
    draw_text_right(canvas, f"PTS {spent}/{budget}", 196, 7, LIGHT, FONT_SMALL)

    draw_panel(2, 14, 112, 108)
    draw_panel(116, 14, 82, 108)

    ordered = roster_sorted(roster)
    pages = max(1, math.ceil(len(ordered) / ROWS_PER_PAGE))
    visible = ordered[page * ROWS_PER_PAGE:(page + 1) * ROWS_PER_PAGE]

    hovered_monster = None
    for i, m in enumerate(visible):
        rect = team_row_rect(i)
        hovered = rect.collidepoint(mx, my)
        chosen = m in selected
        if hovered:
            hovered_monster = m
        if chosen:
            pygame.draw.rect(canvas, BLUE, rect)
        elif hovered:
            pygame.draw.rect(canvas, DARK, rect)
        name = fit_text(FONT_TINY, m["name"], 84)
        draw_text_left(canvas, name, 7, rect.centery, WHITE if chosen else FOAM, FONT_TINY)
        draw_text_right(canvas, f"{m['cost']}", 109, rect.centery, LIGHT, FONT_TINY)

    page_prev.draw(canvas, mx, my, enabled=page > 0)
    page_next.draw(canvas, mx, my, enabled=page < pages - 1)
    draw_text_left(canvas, f"PAGE {page + 1}/{pages}", 54, 114, LIGHT, FONT_TINY)

    # details of the monster under the mouse (or the last one picked)
    detail = hovered_monster or (selected[-1] if selected else None)
    if detail:
        blit_monster(detail, 120, 17, box=24, scale=3)
        draw_text_left(canvas, f"COST {detail['cost']}", 148, 24, LIGHT, FONT_SMALL)
        draw_text_left(canvas, fit_text(FONT_TINY, detail["type"].upper(), 46), 148, 34, GREY, FONT_TINY)
        draw_text_left(canvas, fit_text(FONT_TINY, detail["name"], 76), 120, 47, WHITE, FONT_TINY)
        draw_text_left(canvas, f"HP   {game_hp(detail)}", 120, 58, FOAM, FONT_TINY)
        draw_text_left(canvas, f"ATK  {detail['attack']}", 120, 67, FOAM, FONT_TINY)
        draw_text_left(canvas, f"DEF  {detail['defense']}", 120, 76, FOAM, FONT_TINY)
        draw_text_left(canvas, f"SPD  {detail['speed']}", 120, 85, FOAM, FONT_TINY)
    else:
        draw_text_left(canvas, "CLICK A", 120, 40, LIGHT, FONT_TINY)
        draw_text_left(canvas, "MONSTER TO", 120, 50, LIGHT, FONT_TINY)
        draw_text_left(canvas, "ADD IT", 120, 60, LIGHT, FONT_TINY)

    draw_text_left(canvas, "YOUR TEAM", 120, 96, LIGHT, FONT_TINY)
    for i in range(TEAM_SIZE):
        label = fit_text(FONT_TINY, selected[i]["name"], 74) if i < len(selected) else "-"
        draw_text_left(canvas, label, 120, 105 + i * 8, WHITE if i < len(selected) else GREY, FONT_TINY)

    if flash_text:
        draw_text(canvas, flash_text, 100, 126, FOAM, FONT_SMALL)
    team_back.draw(canvas, mx, my)
    team_fight.draw(canvas, mx, my, enabled=len(selected) > 0)


# ---------------------------------------------------------------
#  SCREEN: BATTLE
# ---------------------------------------------------------------
btn_attack = Button("ATTACK", 124, 96, 72, 14, FONT_SMALL)
btn_defend = Button("DEFEND", 124, 112, 72, 14, FONT_SMALL)
btn_special = Button("SPECIAL", 124, 128, 72, 14, FONT_SMALL)
btn_cancel = Button("CANCEL", 124, 112, 72, 14, FONT_SMALL)


def unit_rect(side, i):
    x = 2 if side == "player" else 106
    return pygame.Rect(x, 4 + 30 * i, 92, 28)


def draw_unit_row(u, rect, left, is_active, targetable, mx, my, t):
    pygame.draw.rect(canvas, (6, 10, 28), rect)
    if is_active:
        border = FOAM if (t // 8) % 2 else LIGHT
    elif targetable:
        border = FOAM if rect.collidepoint(mx, my) else BLUE
    else:
        border = DARK
    pygame.draw.rect(canvas, border, rect, 1)

    box_x = rect.x + 2 if left else rect.right - 26
    blit_monster(u.monster, box_x, rect.y + 2, box=24, faded=not u.alive)

    tx = rect.x + 30 if left else rect.x + 5
    name_colour = FOAM if u.alive else GREY
    draw_text_left(canvas, fit_text(FONT_TINY, u.name, 56), tx, rect.y + 7, name_colour, FONT_TINY)

    pygame.draw.rect(canvas, (30, 10, 20), (tx, rect.y + 13, 56, 4))
    if u.alive:
        ratio = u.hp / u.max_hp
        bar_colour = (80, 200, 110) if ratio > 0.5 else (230, 200, 70) if ratio > 0.25 else (220, 70, 70)
        pygame.draw.rect(canvas, bar_colour, (tx, rect.y + 13, max(1, int(56 * ratio)), 4))
    text = f"{u.hp}/{u.max_hp}" + ("  G" if u.defending else "")
    draw_text_left(canvas, text, tx, rect.y + 22, LIGHT if u.alive else GREY, FONT_TINY)


def draw_battle(t, mx, my, battle, target_mode, can_act):
    draw_background(t)
    canvas.blit(dim_dark, (0, 0))

    targetable = target_mode
    for i, u in enumerate(battle.player):
        draw_unit_row(u, unit_rect("player", i), True, u is battle.active, False, mx, my, t)
    for i, u in enumerate(battle.enemy):
        draw_unit_row(u, unit_rect("enemy", i), False, u is battle.active,
                      targetable and u.alive, mx, my, t)
    draw_text(canvas, "VS", 100, 46, LIGHT, FONT_SMALL)

    # message box
    draw_panel(2, 94, 118, 54)
    winner = battle.winner()
    if winner == "player":
        header = "VICTORY!"
    elif winner == "enemy":
        header = "DEFEATED..."
    elif target_mode:
        header = "PICK A TARGET"
    elif battle.active.side == "player":
        header = fit_text(FONT_SMALL, f"YOUR TURN: {battle.active.name}", 112)
    else:
        header = "ENEMY TURN..."
    draw_text_left(canvas, header, 6, 101, FOAM, FONT_SMALL)

    lines = []
    for entry in battle.log[-8:]:
        lines.extend(wrap_text(FONT_TINY, entry, 110))
    for i, line in enumerate(lines[-4:]):
        draw_text_left(canvas, line, 6, 112 + i * 10, WHITE, FONT_TINY)

    # action buttons
    if target_mode:
        btn_cancel.draw(canvas, mx, my)
    else:
        ready = battle.active is not None and battle.active.can_special
        btn_special.label = "SPECIAL" if (battle.active is None or ready) else f"SPECIAL ({battle.active.cooldown})"
        btn_attack.draw(canvas, mx, my, enabled=can_act)
        btn_defend.draw(canvas, mx, my, enabled=can_act)
        btn_special.draw(canvas, mx, my, enabled=can_act and ready)


# ---------------------------------------------------------------
#  SCREEN: RESULT (after a battle)
# ---------------------------------------------------------------
btn_result_main = Button("CONTINUE", 66, 108, 68, 14, FONT_SMALL)
btn_result_map = Button("MAP", 66, 124, 68, 14, FONT_SMALL)


def draw_result(t, mx, my, victory, lines, final_win):
    draw_background(t)
    canvas.blit(dim_dark, (0, 0))
    draw_panel(30, 24, 140, 120)

    if final_win:
        title, colour = "YOU WIN!", FOAM
    elif victory:
        title, colour = "VICTORY!", FOAM
    else:
        title, colour = "DEFEAT", (230, 110, 110)
    draw_text(canvas, title, 100, 38, colour, FONT_BIG)

    y = 56
    for line in lines:
        for wrapped in wrap_text(FONT_TINY, line, 126):
            draw_text(canvas, wrapped, 100, y, WHITE, FONT_TINY)
            y += 10
        y += 3

    if final_win:
        btn_result_main.label = "MENU"
        btn_result_main.draw(canvas, mx, my)
    elif victory:
        btn_result_main.label = "CONTINUE"
        btn_result_main.draw(canvas, mx, my)
    else:
        btn_result_main.label = "TRY AGAIN"
        btn_result_main.draw(canvas, mx, my)
        btn_result_map.draw(canvas, mx, my)


# ---------------------------------------------------------------
#  GAME STATE
# ---------------------------------------------------------------
state = "menu"           # menu, map, team, battle, result
title = "START GAME!"
unlocked = 1             # how many map blocks the player can click
current_level = 1
t = 0

# your collection of monsters (grows after every win)
def make_starter_roster():
    """3 solid monsters (so you can use your whole point budget) + 5 cheaper ones."""
    solid = [m for m in MONSTERS if 3 <= m["cost"] <= 4]
    if len(solid) < 3:                                   # unusual dataset: use the strongest cheap ones
        solid = [m for m in MONSTERS if m["cost"] <= 4][-6:]
    team = random.sample(solid, min(3, len(solid)))
    others = [m for m in MONSTERS if m["cost"] <= 3 and m not in team]
    if len(others) < 5:
        others = [m for m in MONSTERS if m not in team][:12]
    return team + random.sample(others, min(5, len(others)))


roster = make_starter_roster()
selected = []
page = 0
flash_text = ""
flash_timer = 0

battle = None
battle_wait = 0          # little pauses so you can read what happened
end_delay = None
target_mode = False
pending_action = None

result_victory = False
result_lines = []
result_final = False


def flash(text):
    global flash_text, flash_timer
    flash_text, flash_timer = text, 60


def start_team_select(level):
    global state, current_level, selected, page
    current_level = level
    selected = []
    page = 0
    state = "team"


def toggle_monster(m):
    if m in selected:
        selected.remove(m)
    elif len(selected) >= TEAM_SIZE:
        flash("TEAM FULL")
    elif sum(x["cost"] for x in selected) + m["cost"] > player_budget(current_level):
        flash("NOT ENOUGH POINTS")
    else:
        selected.append(m)


def start_battle():
    global state, battle, battle_wait, end_delay, target_mode, pending_action
    battle = Battle(list(selected), make_enemy_team(MONSTERS, current_level))
    battle_wait = 20
    end_delay = None
    target_mode = False
    pending_action = None
    state = "battle"


def add_rewards(level):
    owned = {m["name"] for m in roster}
    options = [m for m in MONSTERS if m["name"] not in owned and m["cost"] <= level * 2 + 3]
    random.shuffle(options)
    new = options[:3]
    roster.extend(new)
    return [m["name"] for m in new]


def finish_battle():
    global state, unlocked, result_victory, result_lines, result_final
    result_victory = battle.winner() == "player"
    result_final = False
    if result_victory:
        unlocked = max(unlocked, min(current_level + 1, len(NODES)))
        names = add_rewards(current_level)
        if current_level >= len(NODES):
            result_final = True
            result_lines = ["YOU REACHED THE END!", "THANKS FOR PLAYING"]
        else:
            result_lines = [f"LEVEL {current_level + 1} UNLOCKED"]
            if names:
                result_lines.append("NEW MONSTERS: " + ", ".join(names))
    else:
        result_lines = ["YOUR TEAM WAS DEFEATED", "PICK A NEW TEAM AND TRY AGAIN"]
    state = "result"


def player_can_act():
    return (battle is not None and battle.winner() is None and battle.active is not None
            and battle.active.side == "player" and battle_wait == 0)


def begin_action(action):
    global target_mode, pending_action, battle_wait
    foes = battle.foes_of(battle.active)
    if len(foes) == 1:                       # only one enemy left: no need to pick
        battle.perform(action, foes[0])
        battle_wait = 25
    else:
        target_mode = True
        pending_action = action


# ---------------------------------------------------------------
#  MAIN LOOP
# ---------------------------------------------------------------
while True:
    mx, my = pygame.mouse.get_pos()
    mx //= SCALE
    my //= SCALE

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if state == "team":
                state = "map"
            elif state == "map":
                state = "menu"
            elif state == "battle" and target_mode:
                target_mode = False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if state == "menu":
                if menu_buttons["yes"].hovered(mx, my):
                    state = "map"
                elif menu_buttons["no"].hovered(mx, my):
                    title = "OKAY, BYE!"
                elif menu_buttons["exit"].hovered(mx, my):
                    pygame.quit()
                    sys.exit()

            elif state == "map":
                clicked = node_at(mx, my)
                if clicked is not None and clicked < unlocked:
                    start_team_select(clicked + 1)

            elif state == "team":
                ordered = roster_sorted(roster)
                pages = max(1, math.ceil(len(ordered) / ROWS_PER_PAGE))
                visible = ordered[page * ROWS_PER_PAGE:(page + 1) * ROWS_PER_PAGE]
                for i, m in enumerate(visible):
                    if team_row_rect(i).collidepoint(mx, my):
                        toggle_monster(m)
                if page_prev.hovered(mx, my) and page > 0:
                    page -= 1
                elif page_next.hovered(mx, my) and page < pages - 1:
                    page += 1
                elif team_back.hovered(mx, my):
                    state = "map"
                elif team_fight.hovered(mx, my) and selected:
                    start_battle()

            elif state == "battle":
                if target_mode:
                    if btn_cancel.hovered(mx, my):
                        target_mode = False
                    else:
                        for i, u in enumerate(battle.enemy):
                            if u.alive and unit_rect("enemy", i).collidepoint(mx, my):
                                battle.perform(pending_action, u)
                                battle_wait = 25
                                target_mode = False
                                break
                elif player_can_act():
                    if btn_attack.hovered(mx, my):
                        begin_action("attack")
                    elif btn_defend.hovered(mx, my):
                        battle.perform("defend")
                        battle_wait = 25
                    elif btn_special.hovered(mx, my) and battle.active.can_special:
                        begin_action("special")

            elif state == "result":
                if btn_result_main.hovered(mx, my):
                    if result_final:
                        state = "menu"
                    elif result_victory:
                        state = "map"
                    else:
                        start_team_select(current_level)
                elif not result_victory and btn_result_map.hovered(mx, my):
                    state = "map"

    # ---- things that happen on their own every frame ----
    if flash_timer > 0:
        flash_timer -= 1
        if flash_timer == 0:
            flash_text = ""

    if state == "battle":
        if battle_wait > 0:
            battle_wait -= 1
        if battle.winner():
            if end_delay is None:
                end_delay = 50
            else:
                end_delay -= 1
                if end_delay <= 0:
                    finish_battle()
        elif battle.active.side == "enemy" and battle_wait == 0:
            action, target = battle.enemy_choose()
            battle.perform(action, target)
            battle_wait = 25

    # ---- draw the current screen ----
    if state == "menu":
        draw_menu(t, mx, my, title)
    elif state == "map":
        draw_map(t, mx, my, unlocked)
    elif state == "team":
        draw_team(t, mx, my, roster, selected, current_level, page, flash_text)
    elif state == "battle":
        draw_battle(t, mx, my, battle, target_mode, player_can_act())
    else:
        draw_result(t, mx, my, result_victory, result_lines, result_final)

    pygame.transform.scale(canvas, window.get_size(), window)
    flush_text()
    pygame.display.flip()
    clock.tick(30)
    t += 1

