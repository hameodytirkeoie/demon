import pygame
import sys
import os

pygame.init()

# --- Screen ---
WIDTH, HEIGHT = 900, 500
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Big Boy Simulator")
clock = pygame.time.Clock()

# --- Colors ---
RED   = (255,   0,   0)
GREEN = (0,   255,   0)
WHITE = (255, 255, 255)
BLACK = (0,     0,   0)
YELLOW = (255, 255, 0)

SPRITE_W, SPRITE_H = 50, 80
GROUND_Y = HEIGHT - 40

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
assets_dir = os.path.join(BASE_DIR, "assets")
BASE_P1 = os.path.join(assets_dir, "player1")
BASE_P2 = os.path.join(assets_dir, "player2")

# ----------------------------------------------------------
# BACKGROUNDS
# ----------------------------------------------------------
bg = pygame.image.load(os.path.join(assets_dir, "background.png")).convert()
bg = pygame.transform.scale(bg, (WIDTH, HEIGHT))

menu_bg = pygame.image.load(os.path.join(assets_dir, "menu_bg.png")).convert()
menu_bg = pygame.transform.scale(menu_bg, (WIDTH, HEIGHT))


# ----------------------------------------------------------
# OPTIONAL UI IMAGES
# ----------------------------------------------------------
def load_ui_image(path, size):
    if not os.path.exists(path):
        return None
    img = pygame.image.load(path).convert_alpha()
    return pygame.transform.scale(img, size)

HUD_PANEL_IMG = load_ui_image(os.path.join(assets_dir, "hud_panel.png"), (334, 34))
TIMER_PANEL_IMG = load_ui_image(os.path.join(assets_dir, "timer_panel.png"), (140, 48))

# The HUD frames are sometimes authored at very large resolutions, which can
# cover the playfield when loaded raw. Scale them to a consistent size so the
# health bars and art stay within the top margin of the screen.
HUD_FRAME_SIZE = (360, 140)


def clean_hud_frame(frame):
    """Remove bright, flat backgrounds so HUD art blends with the scene."""
    frame = frame.convert_alpha()

    corner_color = frame.get_at((0, 0))
    avg = (corner_color.r + corner_color.g + corner_color.b) / 3

    # Most exported HUD art uses a flat white canvas. Treat that color as a
    # colorkey so the surrounding area becomes transparent when blitted.
    if corner_color.a == 255 and avg > 245:
        frame.set_colorkey((corner_color.r, corner_color.g, corner_color.b))

    return frame


def load_hud_frames(subfolder, scale_to=None):
    """Load HUD art for each player, falling back to their sprite folders.

    Some projects ship HUD frames inside assets/hud/<player>/ while others keep
    frame art alongside the fighter sprites (frame1.png, frame2.png, ...).
    This helper looks in both places so Player 2's HUD can reuse its authored
    frames and stay visually consistent with Player 1. If HUD art is split
    between the dedicated folder and the sprite folder, gather every frame_*.png
    (or jpg) across both locations.
    """

    hud_root = os.path.join(assets_dir, "hud", subfolder)
    alt_root = os.path.join(assets_dir, subfolder)

    sources = []
    if os.path.isdir(hud_root):
        sources.append(hud_root)
    if os.path.isdir(alt_root) and alt_root not in sources:
        sources.append(alt_root)

    if not sources:
        return []

    def normalize_frame_name(filename):
        base, _ = os.path.splitext(filename)
        lower = base.lower()
        if lower.startswith("frame"):
            return lower
        if lower.startswith("fram"):
            # Accept slightly misspelled exports like "fram2.png" so all HUD
            # frames get surfaced in-game.
            return "frame" + lower[4:]
        return lower

    def sort_key(filename):
        base = normalize_frame_name(filename)
        if base.startswith("frame"):
            suffix = base[5:]
            if suffix.isdigit():
                return (0, int(suffix))
        return (1, base)

    frames = []
    seen = set()

    for folder in sources:
        for filename in sorted(os.listdir(folder), key=sort_key):
            normalized = normalize_frame_name(filename)

            if normalized in seen:
                continue
            if not normalized.startswith("frame"):
                continue
            if not filename.lower().endswith((".png", ".jpg", ".jpeg")):
                continue

            seen.add(normalized)
            path = os.path.join(folder, filename)
            frame = pygame.image.load(path).convert_alpha()
            if scale_to:
                frame = pygame.transform.scale(frame, scale_to)

            frames.append(clean_hud_frame(frame))

    return frames

def load_font(font_names, size, bold=False, italic=False):
    """Attempt to load one of the preferred fonts, falling back gracefully."""

    # HUD art can ship in assets/hud/<player>/ or reuse frame*.png from
    # assets/<player>/, so both locations remain valid for asset authors.

    if isinstance(font_names, str):
        font_names = [font_names]

    for name in font_names:
        path = pygame.font.match_font(name, bold=bold, italic=italic)
        if path:
            return pygame.font.Font(path, size)

    return pygame.font.Font(None, size)


def render_pixel_text(text, color, scale=3):
    pixel_base = load_font(["freesansbold", "arial"], 18, bold=True)
    surf = pixel_base.render(text, True, color)
    w, h = surf.get_size()
    return pygame.transform.scale(surf, (w * scale, h * scale))
# ----------------------------------------------------------
# UTIL: LOAD SPRITE
# ----------------------------------------------------------
def load_sprite(folder, filename, flip=False):
    full = os.path.join(folder, filename)
    if not os.path.exists(full):
        print("MISSING:", full)
        sys.exit()
    img = pygame.image.load(full).convert_alpha()
    img = pygame.transform.scale(img, (SPRITE_W, SPRITE_H))
    if flip:
        img = pygame.transform.flip(img, True, False)
    return img


# ----------------------------------------------------------
# PROJECTILES
# ----------------------------------------------------------
class Pencil:
    def __init__(self, x, y, direction):
        self.rect = pygame.Rect(x, y, 20, 4)
        self.speed = 12 * direction

    def update(self):
        self.rect.x += self.speed

    def draw(self, surf):
        pygame.draw.rect(surf, YELLOW, self.rect)
        tip = pygame.Rect(self.rect.right - 3, self.rect.y, 3, 4)
        pygame.draw.rect(surf, (120, 80, 20), tip)


class Bottle:
    def __init__(self, x, y, direction, power=1.0):
        self.x = x
        self.y = y
        speed_scale = power

        self.vx = 8 * speed_scale * direction
        self.vy = -8 - 4 * speed_scale
        self.gravity = 0.5

        img = pygame.image.load(os.path.join(BASE_P1, "p1_bottle1.png")).convert_alpha()
        self.img = pygame.transform.scale(img, (25, 40))

        broken = pygame.image.load(os.path.join(BASE_P1, "p1_bottle_broken.png")).convert_alpha()
        self.broken = pygame.transform.scale(broken, (30, 30))

        self.width = 25
        self.height = 40
        self.dead = False
        self.hit = False
        self.shatter_timer = 0

    @property
    def rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def update(self):
        if not self.hit:
            self.x += self.vx
            self.vy += self.gravity
            self.y += self.vy

            if self.y > GROUND_Y - 20:
                self.hit = True
                self.shatter_timer = 15

        elif self.shatter_timer > 0:
            self.shatter_timer -= 1
        else:
            self.dead = True

    def draw(self, surf):
        if self.hit:
            surf.blit(self.broken, (self.x, self.y))
        else:
            surf.blit(self.img, (self.x, self.y))


class InputState:
    """Lightweight mapping so AI can drive fighters using key constants."""

    def __init__(self, pressed=None):
        self.pressed = set(pressed or [])

    def __getitem__(self, key):
        return key in self.pressed

# ----------------------------------------------------------
# FIGHTER CLASS
# ----------------------------------------------------------
class Fighter:
    def __init__(self, x, folder, idle, walk, attack, hit, win, flip=False,
                 melee_key=None, proj_key=None):

        self.x = x
        self.melee_key = melee_key
        self.proj_key = proj_key

        self.health = 100
        self.velocity = 5

        # Track desired facing, but keep both orientations available so fighters
        # always turn toward their opponent instead of staring off-screen.
        self.facing_left = flip
        self.folder = folder

        def load_frames(names):
            base_frames = [load_sprite(folder, f, False) for f in names]
            flipped_frames = [pygame.transform.flip(img, True, False) for img in base_frames]
            return base_frames, flipped_frames

        self.idle_frames, self.idle_frames_flipped       = load_frames(idle)
        self.walk_frames, self.walk_frames_flipped       = load_frames(walk)
        self.attack_frames, self.attack_frames_flipped   = load_frames(attack)
        self.hit_frames, self.hit_frames_flipped         = load_frames(hit)
        self.win_frames, self.win_frames_flipped         = load_frames(win)

        # Animation state
        self.state = "idle"
        self.frame = 0
        self.counter = 0
        self.idle_speed = 15  # slower idle

        self.rect = self.idle_frames[0].get_rect()
        self.rect.midbottom = (x, GROUND_Y)

        self.vel_y = 0
        self.gravity = 1.0
        self.on_ground = True

        self.attack_cool = 0
        self.proj_cool = 0
        self.just_shot = False
        self.just_shot_power = 1.0
        self.proj_charging = False
        self.proj_charge = 0
        self.max_proj_charge = 45
        self.hit_timer = 0
        self.win_timer = 0
        self.ai_charge_frames = 0
                     
        self.image = self.idle_frames[0]

    def set_hit(self):
        self.state = "hit"
        self.frame = 0
        self.hit_timer = 12

    def set_win(self):
        self.state = "win"
        self.frame = 0
        self.win_timer = 999

    def update(self, keys, left, right, jump, opponent):
        # Keep facing synced to the opponent even while stunned or celebrating
        # so the fighter never drifts into the wrong orientation mid-fight.
        if opponent:
            self.facing_left = opponent.rect.centerx < self.rect.centerx

        if self.win_timer > 0:
            self.animate(self.win_frames, self.win_frames_flipped, 12)
            return

        if self.hit_timer > 0:
            self.hit_timer -= 1
            self.animate(self.hit_frames, self.hit_frames_flipped, 6)
            return

        self.just_shot = False
        moving = False

        # movement
        if keys[left]:
            self.rect.x -= self.velocity
            moving = True
        if keys[right]:
            self.rect.x += self.velocity
            moving = True

        # jump
        if keys[jump] and self.on_ground:
            self.vel_y = -12
            self.on_ground = False

        self.vel_y += self.gravity
        self.rect.y += self.vel_y

        if self.rect.bottom >= GROUND_Y:
            self.rect.bottom = GROUND_Y
            self.vel_y = 0
            self.on_ground = True

        # Turn to face the opponent so sprites never look away from the action.
        if opponent:
            self.facing_left = opponent.rect.centerx < self.rect.centerx

        # attacks
        if self.attack_cool > 0:
            self.attack_cool = max(0, self.attack_cool - 1)
        if self.proj_cool > 0:
            self.proj_cool = max(0, self.proj_cool - 1)

        if keys[self.melee_key] and self.attack_cool == 0:
            self.attack_cool = 18
            self.state = "attack"
            if self.rect.colliderect(opponent.rect):
                opponent.health -= 10
                opponent.set_hit()

        elif self.proj_key and self.attack_cool == 0 and self.proj_cool == 0:
            if keys[self.proj_key]:
                if not self.proj_charging:
                    self.proj_charging = True
                    self.proj_charge = 0
                self.proj_charge = min(self.proj_charge + 1, self.max_proj_charge)
                self.state = "attack"
            elif self.proj_charging:
                charge_ratio = self.proj_charge / self.max_proj_charge
                self.just_shot_power = 0.5 + charge_ratio  # 0.5x on tap, up to 1.5x on full charge
                self.attack_cool = 20
                self.proj_cool = 60  # ~1 second cooldown at 60 FPS
                self.state = "attack"
                self.just_shot = True
                self.proj_charging = False
                self.proj_charge = 0
            else:
                self.state = "walk" if moving else "idle"
        else:
            if moving:
                self.state = "walk"
            else:
                self.state = "idle"
        # animations
        if self.state == "idle":
            self.animate(self.idle_frames, self.idle_frames_flipped, self.idle_speed)
        elif self.state == "walk":
            self.animate(self.walk_frames, self.walk_frames_flipped, 8)
        elif self.state == "attack":
            self.animate(self.attack_frames, self.attack_frames_flipped, 6)

    def animate(self, base_frames, flipped_frames, speed):
        frames = flipped_frames if self.facing_left else base_frames

        self.counter += 1
        if self.counter >= speed:
            self.counter = 0
            self.frame += 1
        if self.frame >= len(frames):
            self.frame = 0
            if self.state == "attack":
                self.state = "idle"
        self.image = frames[self.frame]
        
    def draw(self, surf):
        surf.blit(self.image, self.rect.topleft)


# ----------------------------------------------------------
# CREATE PLAYERS
# ----------------------------------------------------------
def create_players():
    p1_idle   = ["p1_idle1.png", "p1_idle2.png"]
    p1_walk   = ["p1_walk1.png"]
    p1_attack = ["p1_attack1.png", "p1_attack2.png"]
    p1_hit    = ["p1_hit1.png", "p1_hit2.png"]
    p1_win    = ["p1_win1.png"]

    p2_idle   = ["p2_idle1.png", "p2_idle2.png"]
    p2_walk   = ["p2_walk1.png"]
    p2_attack = ["p2_attack1.png", "p2_attack2.png"]
    p2_hit    = ["p2_hit1.png", "p2_hit2.png"]
    p2_win    = ["p2_win1.png"]

    p1 = Fighter(
        150, BASE_P1,
        p1_idle, p1_walk, p1_attack, p1_hit, p1_win,
        flip=False,
        melee_key=pygame.K_SPACE,
        proj_key=pygame.K_q
    )

    p2 = Fighter(
        770, BASE_P2,
        p2_idle, p2_walk, p2_attack, p2_hit, p2_win,
        flip=True,
        melee_key=pygame.K_RETURN,
        proj_key=pygame.K_p
    )

    return p1, p2

def build_ai_inputs(fighter, opponent, left_key, right_key, jump_key):
    """Generate simple AI controls so solo players can battle a bot."""

    pressed = set()
    dx = opponent.rect.centerx - fighter.rect.centerx
    distance = abs(dx)

    # Face and advance toward the opponent unless already in striking range.
    fighter.facing_left = opponent.rect.centerx < fighter.rect.centerx

    # Approach or back up to stay in a comfortable range.
    preferred = 110
    if distance > preferred + 15:
        pressed.add(right_key if dx > 0 else left_key)
    elif distance < preferred - 30:
        pressed.add(left_key if dx > 0 else right_key)

    # Hop when the opponent is above the fighter so elevated foes can be reached.
    if fighter.on_ground and distance < 140 and opponent.rect.bottom <= fighter.rect.bottom - 20:
        pressed.add(jump_key)

    # Attack decisions
    if distance < 100 and fighter.attack_cool == 0:
        pressed.add(fighter.melee_key)
        fighter.ai_charge_frames = 0
    elif fighter.proj_key:
        if fighter.proj_cool == 0 and fighter.attack_cool == 0 and distance > 150:
            fighter.ai_charge_frames = min(fighter.ai_charge_frames + 1, fighter.max_proj_charge)
            if fighter.ai_charge_frames <= 18:
                # Hold to build a little power before releasing.
                pressed.add(fighter.proj_key)
            else:
                fighter.ai_charge_frames = 0
        else:
            fighter.ai_charge_frames = 0

    return InputState(pressed)

# ----------------------------------------------------------
# DRAW UI (HEALTH + TIMER)
# ----------------------------------------------------------
def draw_ui(p1, p2, time_left, countdown_text=None):
    def draw_hud(bg, x, y, ratio):
        ratio = max(0, min(1, ratio))
        track_rect = pygame.Rect(x + 120, y + 78, 200, 14)

        screen.blit(bg, (x, y))

        fill_color = (60, 190, 90)
        fill_rect = pygame.Rect(track_rect.x, track_rect.y, int(track_rect.w * ratio), track_rect.h)
        pygame.draw.rect(screen, fill_color, fill_rect, border_radius=4)
        highlight = pygame.Rect(fill_rect.x + 3, fill_rect.y + 3, max(0, fill_rect.w - 6), 4)
        pygame.draw.rect(screen, (200, 255, 200), highlight, border_radius=3)

    def pick_frame(frames, health):
        if not frames:
            return None

        if len(frames) >= 3:
            if health <= 30:
                return frames[2]
            if health <= 60:
                return frames[1]
            return frames[0]

        if len(frames) == 2:
            if health <= 30:
                return frames[1]
            return frames[0]

        return frames[0]

    if HUD_FRAMES_P1 and HUD_FRAMES_P2:
        p1_frame = pick_frame(HUD_FRAMES_P1, p1.health)
        p2_frame = pick_frame(HUD_FRAMES_P2, p2.health)

        draw_hud(p1_frame, 10, 10, p1.health / 100)
        draw_hud(p2_frame, WIDTH - p2_frame.get_width() - 10, 10, p2.health / 100)
    else:
        bar_w = 320
        bar_h = 22

        def draw_bar(x, y, ratio):
            ratio = max(0, min(1, ratio))
            base_rect = pygame.Rect(x, y, bar_w, bar_h)
            panel_rect = base_rect.inflate(14, 12)

            shadow = panel_rect.move(3, 3)
            pygame.draw.rect(screen, (0, 0, 0), shadow, border_radius=10)

            if HUD_PANEL_IMG:
                screen.blit(HUD_PANEL_IMG, panel_rect.topleft)
            else:
                pygame.draw.rect(screen, (26, 26, 40), panel_rect, border_radius=10)
                pygame.draw.rect(screen, (90, 90, 120), panel_rect, width=2, border_radius=10)

            track_rect = base_rect.inflate(8, 6)
            pygame.draw.rect(screen, (40, 40, 60), track_rect, border_radius=8)

            # Health color transitions from red -> amber -> green
            if ratio > 0.6:
                fill_color = (40, 200, 120)
            elif ratio > 0.3:
                fill_color = (240, 170, 60)
            else:
                fill_color = (210, 60, 60)

            fill_rect = pygame.Rect(base_rect.x, base_rect.y, int(bar_w * ratio), bar_h)
            pygame.draw.rect(screen, fill_color, fill_rect, border_radius=6)
            highlight = pygame.Rect(fill_rect.x + 4, fill_rect.y + 3, max(0, fill_rect.w - 8), 6)
            pygame.draw.rect(screen, (255, 255, 255), highlight, border_radius=4)

        draw_bar(18, 18, p1.health / 100)
        draw_bar(WIDTH - bar_w - 18, 18, p2.health / 100)
        
    # Timer panel
    timer_rect = pygame.Rect(WIDTH // 2 - 70, 12, 140, 48)

    timer_label = countdown_text if countdown_text is not None else str(time_left)
    timer_surface = render_pixel_text(timer_label.rjust(2, " "), WHITE, 3)
    text_pos = timer_surface.get_rect(center=(timer_rect.centerx, timer_rect.y + timer_rect.h - 20))
    screen.blit(timer_surface, text_pos)

# ----------------------------------------------------------
# MAIN MENU
# ----------------------------------------------------------
# Pre-render menu text once to keep consistent sizing and avoid rebuilding
# surfaces inside the loop.
menu_font = load_font(["freesansbold", "arialblack", "impact"], 80, bold=True)
timer_font = load_font(["dejavusansmono", "consolas", "freesansbold"], 60)
controls_font = load_font(["dejavusans", "arial", "freesansbold"], 32, bold=True)
ui_font = load_font(["dejavusansmono", "consolas", "freesansbold"], 28)
button_font = load_font(["freesansbold", "arialblack", "impact"], 50, bold=True)

# HUD art loaded from sprite folders so the visuals can be authored externally.
# Expected layout:
# assets/
#   hud/
#     player1/
#       frame1.png
#       frame2.png
#     player2/
#       frame1.png
#       ...
HUD_FRAMES_P1 = load_hud_frames("player1", HUD_FRAME_SIZE)
HUD_FRAMES_P2 = load_hud_frames("player2", HUD_FRAME_SIZE)


menu_title = menu_font.render("Big Boy Simulator", True, WHITE)
start_prompt = timer_font.render("Press ENTER or NUMPAD ENTER for 2-Player", True, WHITE)
single_p1_prompt = controls_font.render("Press 1 to play as Player 1 (Player 2 uses AI)", True, WHITE)
single_p2_prompt = controls_font.render("Press 2 to play as Player 2 (Player 1 uses AI)", True, WHITE)
p1_controls = [
    controls_font.render("Player 1: Move A/D, Jump W", True, WHITE),
    controls_font.render("Melee: SPACE  |  Throw: Q", True, WHITE),
]   
p2_controls = [
    controls_font.render("Player 2: Move ←/→, Jump ↑", True, WHITE),
    controls_font.render("Melee: ENTER  |  Throw: P", True, WHITE)
]

title_pos = menu_title.get_rect(center=(WIDTH // 2, 80))
prompt_pos = start_prompt.get_rect(center=(WIDTH // 2, 260))
single_p1_pos = single_p1_prompt.get_rect(midtop=(WIDTH // 2, prompt_pos.bottom + 30))
single_p2_pos = single_p2_prompt.get_rect(midtop=(WIDTH // 2, single_p1_pos.bottom + 10))

left_x = 60
right_x = WIDTH - 60
top_y = 150
spacing = 40

p1_control_positions = [
    (left_x, top_y + i * spacing)
    for i in range(len(p1_controls))
]
p2_control_positions = [
    (right_x - ctrl.get_width(), top_y + i * spacing)
    for i, ctrl in enumerate(p2_controls)
]

def main_menu():
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return "versus"
                if e.key == pygame.K_1:
                    return "p1"
                if e.key == pygame.K_2:
                    return "p2"
                    screen.blit(menu_bg, (0, 0))
                    
        screen.blit(menu_title, title_pos)
        screen.blit(start_prompt, prompt_pos)
        screen.blit(single_p1_prompt, single_p1_pos)
        screen.blit(single_p2_prompt, single_p2_pos)
        for line, pos in zip(p1_controls, p1_control_positions):
            screen.blit(line, pos)
        for line, pos in zip(p2_controls, p2_control_positions):
            screen.blit(line, pos)

        pygame.display.flip()
        clock.tick(60)


def post_game_menu(champion_label):
    replay_surf = button_font.render("Replay", True, WHITE)
    exit_surf = button_font.render("Exit", True, WHITE)

    button_w = 220
    button_h = 70
    spacing = 30

    center_x = WIDTH // 2
    base_y = HEIGHT // 2 + 40

    replay_rect = pygame.Rect(0, 0, button_w, button_h)
    replay_rect.center = (center_x, base_y)

    exit_rect = pygame.Rect(0, 0, button_w, button_h)
    exit_rect.center = (center_x, base_y + button_h + spacing)

    champion_text = menu_font.render(champion_label, True, WHITE)
    champion_rect = champion_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 70))

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if replay_rect.collidepoint(e.pos):
                    return "replay"
                if exit_rect.collidepoint(e.pos):
                    return "exit"

        screen.blit(menu_bg, (0, 0))

        pygame.draw.rect(screen, (10, 10, 20), replay_rect, border_radius=10)
        pygame.draw.rect(screen, (80, 180, 255), replay_rect, width=4, border_radius=10)
        screen.blit(replay_surf, replay_surf.get_rect(center=replay_rect.center))

        pygame.draw.rect(screen, (10, 10, 20), exit_rect, border_radius=10)
        pygame.draw.rect(screen, (255, 120, 120), exit_rect, width=4, border_radius=10)
        screen.blit(exit_surf, exit_surf.get_rect(center=exit_rect.center))

        screen.blit(champion_text, champion_rect)

        pygame.display.flip()
        clock.tick(60)

# ----------------------------------------------------------
# ROUND COUNTDOWN
# ----------------------------------------------------------
def draw_countdown_frame(p1, p2, label, starting_time):
    screen.blit(bg, (0, 0))
    p1.draw(screen)
    p2.draw(screen)
    # Show the full round timer value while overlaying the countdown text.
    draw_ui(p1, p2, starting_time, countdown_text=label)

    overlay = render_pixel_text(label, WHITE, 5)
    outline = overlay.copy()
    outline.fill((0, 0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    outline_rect = overlay.get_rect(center=(WIDTH // 2, HEIGHT // 2))
    shadow = outline_rect.move(4, 4)
    screen.blit(outline, shadow)
    screen.blit(overlay, outline_rect)

    pygame.display.flip()


def run_round_countdown(p1, p2, starting_time):
    steps = ["3", "2", "1", "GO"]
    for label in steps:
        target_ms = 800 if label == "GO" else 1000
        elapsed = 0
        while elapsed < target_ms:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    sys.exit()
                if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return

            draw_countdown_frame(p1, p2, label, starting_time)
            elapsed += clock.tick(60)


# ----------------------------------------------------------
# ROUND MESSAGES
# ----------------------------------------------------------
def show_round_message(title, subtitle=None, duration_ms=1400):
    """Overlay a simple, centered message for a short duration."""

    title_surf = render_pixel_text(title, WHITE, 4)
    title_rect = title_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 10))

    elapsed = 0
    while elapsed < duration_ms:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                sys.exit()

        screen.blit(bg, (0, 0))

        outline = title_surf.copy()
        outline.fill((0, 0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        outline_rect = title_rect.move(4, 4)

        screen.blit(outline, outline_rect)
        screen.blit(title_surf, title_rect)

        if subtitle:
            sub_surf = ui_font.render(subtitle, True, WHITE)
            sub_rect = sub_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 30))
            screen.blit(sub_surf, sub_rect)

        pygame.display.flip()
        elapsed += clock.tick(60)

# ----------------------------------------------------------
# SINGLE ROUND
# ----------------------------------------------------------
def play_round(p1, p2, p1_ai=False, p2_ai=False):
    time_left = 60
    timer_label = str(time_left)
    tick = 0
    projectiles = []
    bottles = []
    overtime = False
    sudden_death = False

    run_round_countdown(p1, p2, time_left)

    while True:
        screen.blit(bg, (0, 0))
        keys = pygame.key.get_pressed()

        for e in pygame.event.get():
            if e.type == pygame.QUIT: sys.exit()

        p1_inputs = keys if not p1_ai else build_ai_inputs(p1, p2, pygame.K_a, pygame.K_d, pygame.K_w)
        p2_inputs = keys if not p2_ai else build_ai_inputs(p2, p1, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP)

        # update
        p1.update(p1_inputs, pygame.K_a, pygame.K_d, pygame.K_w, p2)
        p2.update(p2_inputs, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, p1)
        if p1.just_shot:
            bottles.append(Bottle(p1.rect.centerx, p1.rect.y, 1, power=p1.just_shot_power))

        if p2.just_shot:
            projectiles.append(Pencil(p2.rect.left, p2.rect.centery, -1))

        # update projectiles
        for p in projectiles[:]:
            p.update()
            if p.rect.colliderect(p1.rect):
                p1.health -= 5
                p1.set_hit()
                projectiles.remove(p)
            elif p.rect.right < 0:
                projectiles.remove(p)

        for b in bottles[:]:
            prev_hit = b.hit
            b.update()
            if not prev_hit and b.hit:
                # bottle shatter hitbox
                hitbox = pygame.Rect(b.x, b.y, 40, 40)
                if hitbox.colliderect(p2.rect):
                    p2.health -= 15
                    p2.set_hit()
            if b.dead:
                bottles.remove(b)
            elif b.x > WIDTH + 40 or b.x < -40:
                bottles.remove(b)

        # draw
        for p in projectiles: p.draw(screen)
        for b in bottles:    b.draw(screen)

        p1.draw(screen)
        p2.draw(screen)

        draw_ui(p1, p2, timer_label)

        pygame.display.flip()
        clock.tick(60)

        if not sudden_death:
            tick += 1
            if tick >= 60:
                tick = 0
                time_left -= 1
                timer_label = str(max(time_left, 0))

        # end conditions
        if not sudden_death and time_left <= 0:
            if p1.health > p2.health:
                return 1
            if p2.health > p1.health:
                return 2

            if not overtime:
                show_round_message("TIME!", "Overtime begins")
                overtime = True
                time_left = 15
                timer_label = str(time_left)
                tick = 0
                continue

            show_round_message("OVERTIME TIE!", "Sudden death!")
            sudden_death = True
            timer_label = "SD"
            tick = 0
            continue

        if p1.health <= 0:
            return 2
        if p2.health <= 0:
            return 1

        if sudden_death and p1.health != p2.health:
            return 1 if p1.health > p2.health else 2


# ----------------------------------------------------------
# GAME LOOP (BEST OF 3)
# ----------------------------------------------------------
def game_loop():
    playing = True

    while playing:
        selection = main_menu()

        p1_ai = selection == "p2"
        p2_ai = selection == "p1"

        p1_score = 0
        p2_score = 0

        while p1_score < 2 and p2_score < 2:
            p1, p2 = create_players()
            winner = play_round(p1, p2, p1_ai=p1_ai, p2_ai=p2_ai)

            round_winner_text = "PLAYER 1 WINS!" if winner == 1 else "PLAYER 2 WINS!"
            if winner == 1:
                p1_score += 1
                p1.set_win()
            else:
                p2_score += 1
                p2.set_win()

            show_round_message(round_winner_text, "you win big boy negative aura")

        champion_label = "PLAYER 1 WINS!" if p1_score > p2_score else "PLAYER 2 WINS!"

        choice = post_game_menu(champion_label)
        if choice == "exit":
            playing = False
# ----------------------------------------------------------
# START GAME
# ----------------------------------------------------------
if __name__ == "__main__":
    game_loop()
    pygame.quit()
    sys.exit()


























