import pygame
import sys
import os

pygame.init()
# --- Screen ---
WIDTH, HEIGHT = 900, 500
ROUNDS_TO_WIN = 2
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
AI_COMFORT_DISTANCE = 140  # pixels of spacing the bot tries to maintain


class GameSettings:
    def __init__(self):
        self.rounds_to_win = 2
        self.round_time = 60
        self.overtime_time = 15
        self.ai_aggression = 1.0  # 1.0 = default bot behavior, lower/raise to soften/harden the AI


SETTINGS = GameSettings()
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
# health bars and art stay within the top margin of the screen. This size
# leaves room for the timer panel and keeps both HUDs anchored in the top
# corners without overlapping gameplay.
HUD_FRAME_SIZE = (330, 220)


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


def normalize_hud_frame(frame, target_size, mirror=False):
    """Scale HUD art to fit the target canvas without stretching.

    Some HUD exports (notably Player 2's mid-health art) ship on canvases with
    different aspect ratios. Scale the art to fit within the expected HUD size
    while preserving aspect ratio, then center it on a transparent surface so
    each frame occupies the same footprint. Optionally mirror the art so
    Player 2 faces toward the center of the screen.
    """

    target_w, target_h = target_size
    src_w, src_h = frame.get_size()

    scale = min(target_w / src_w, target_h / src_h)
    scaled_w = max(1, int(round(src_w * scale)))
    scaled_h = max(1, int(round(src_h * scale)))

    frame = pygame.transform.smoothscale(frame, (scaled_w, scaled_h))
    if mirror:
        frame = pygame.transform.flip(frame, True, False)

    canvas = pygame.Surface((target_w, target_h), pygame.SRCALPHA)
    offset_x = (target_w - scaled_w) // 2
    offset_y = (target_h - scaled_h) // 2
    canvas.blit(frame, (offset_x, offset_y))
    return canvas


def load_hud_frames(subfolder, scale_to=None, mirror=False):
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

    raw_frames = []
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
            raw_frames.append(frame)

    if not raw_frames:
        return []

    if scale_to:
        target_size = scale_to
    else:
        target_w = max(frame.get_width() for frame in raw_frames)
        target_h = max(frame.get_height() for frame in raw_frames)
        target_size = (target_w, target_h)

    frames = []
    for frame in raw_frames:
        needs_normalize = scale_to or frame.get_size() != target_size or mirror
        if needs_normalize:
            frame = normalize_hud_frame(frame, target_size, mirror=mirror)
        frames.append(clean_hud_frame(frame))

    return frames

def load_font(font_names, size, bold=False, italic=False):
    """Attempt to load one of the preferred fonts, falling back gracefully."""

    # Try each requested font (respecting style flags) and return the first
    # match found on the system; if none resolve, fall back to pygame's default.

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
        self.active = True

    def update(self):
        self.rect.x += self.speed
        if self.rect.right < 0 or self.rect.left > WIDTH:
            self.active = False

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

        self.width, self.height = self.img.get_size()
        self.broken_width, self.broken_height = self.broken.get_size()
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
            if self.y + self.height >= GROUND_Y:
                self.hit = True
                self.shatter_timer = 15
                # Pin the bottle to the ground on impact so it doesn't sink
                # below the floor while the shatter animation plays.
                self.y = GROUND_Y - self.broken_height
                self.vx = 0
                self.vy = 0
                # Update the collision box to match the shattered sprite so the
                # rect aligns with the art during the lingering animation.
                self.width = self.broken_width
                self.height = self.broken_height
                 
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
        self.vel_x = 0


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
        self.idle_speed = 15

        self.rect = self.idle_frames[0].get_rect()
        self.rect.midbottom = (x, GROUND_Y)

        self.vel_y = 0
        self.vel_x = 0
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

        self.combo_step = 0
        self.last_hit_timer = 0


                     
        # Seed the initial sprite with the correct facing so countdown screens
        # render the fighter looking toward their opponent instead of turning
        # around on the first animation update.
        self.image = self.idle_frames_flipped[0] if self.facing_left else self.idle_frames[0]

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
        # movement
        self.vel_x = 0  # reset horizontal velocity each frame

        if keys[left]:
            self.rect.x -= self.velocity
            self.vel_x = -self.velocity
            moving = True

        if keys[right]:
            self.rect.x += self.velocity
            self.vel_x = self.velocity
            moving = True

        # keep fighters on screen
        self.rect.x = max(0, min(self.rect.x, WIDTH - self.rect.width))

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

def build_ai_inputs(
    fighter, opponent, left_key, right_key, jump_key, aggression=1.0
):
    pressed = set()
    dx = opponent.rect.centerx - fighter.rect.centerx
    distance = abs(dx)
    move_right = dx > 0

    # Always face opponent
    fighter.facing_left = opponent.rect.centerx < fighter.rect.centerx

    # ---------------------------
    # RANGE DEFINITIONS
    # ---------------------------
    CLOSE_RANGE = 85          # punch range
    MID_RANGE = 230           # projectile poke range
    FAR_RANGE = 350           # chase range
    TOO_CLOSE = 55            # used for retreat logic

    # ---------------------------
    # RETREAT / AGGRESSION LOGIC
    # ---------------------------
    # If AI HP is very low → plays defensive
    if fighter.health < 25 and distance < TOO_CLOSE:
        # pull back
        pressed.add(left_key if move_right else right_key)

    # If enemy HP is low → play aggressive to secure kill
    if opponent.health < 30 and distance < FAR_RANGE:
        aggression = 1.4

    # ---------------------------
    # PREDICTIVE MOVEMENT ("Smart chase")
    # ---------------------------
    if distance > MID_RANGE:
        # Predict where enemy will be in 10 frames
        predicted_dx = dx + (opponent.vel_x * 10)

        if predicted_dx > 0:
            pressed.add(right_key)
        else:
            pressed.add(left_key)

    # Maintain pressure at close range
    elif CLOSE_RANGE < distance < MID_RANGE:
        if distance > (CLOSE_RANGE + 10):
            pressed.add(right_key if move_right else left_key)

    # ---------------------------
    # WALL SAFETY
    # ---------------------------
    if fighter.rect.left <= 0 and left_key in pressed:
        pressed.remove(left_key)
    if fighter.rect.right >= WIDTH and right_key in pressed:
        pressed.remove(right_key)

    # ---------------------------
    # DODGE PROJECTILES / JUMP LOGIC
    # ---------------------------
    # SIMPLE DODGE:
    if hasattr(opponent, "projectiles"):
        for proj in opponent.projectiles:
            # Projectile approaching fighter horizontally
            if abs(proj.rect.centery - fighter.rect.centery) < 60:
                if proj.rect.centerx < fighter.rect.centerx:
                    # bullet coming from left
                    pressed.add(right_key)
                else:
                    pressed.add(left_key)

            # Jump over ground-level projectile
            if proj.rect.centery > fighter.rect.centery + 10 and distance < MID_RANGE:
                if fighter.on_ground:
                    pressed.add(jump_key)

    # Jump if opponent is above
    if fighter.on_ground and opponent.rect.bottom < fighter.rect.bottom - 40:
        pressed.add(jump_key)

    # ---------------------------
    # COMBAT LOGIC (smart attacks)
    # ---------------------------

    # CLOSE RANGE → COMBO PUNCH SYSTEM
    if distance < CLOSE_RANGE and fighter.attack_cool == 0:
        # 3-stage combo decision
        if fighter.combo_step == 0:
            pressed.add(fighter.melee_key)
            fighter.combo_step = 1
        elif fighter.combo_step == 1 and fighter.last_hit_timer < 20:
            pressed.add(fighter.melee_key)
            fighter.combo_step = 2
        elif fighter.combo_step == 2 and fighter.last_hit_timer < 28:
            pressed.add(fighter.melee_key)
            fighter.combo_step = 0
        else:
            # reset combo if failed
            fighter.combo_step = 0

    # MID RANGE → PROJECTILE POKES
    elif CLOSE_RANGE < distance < MID_RANGE:
        if fighter.proj_cool == 0:
            pressed.add(fighter.proj_key)

    # FAR RANGE → CHARGED PROJECTILES
    elif distance >= MID_RANGE:
        if fighter.proj_key:
            if not fighter.proj_charging:
                pressed.add(fighter.proj_key)
                fighter.ai_charge_frames = 0
            else:
                fighter.ai_charge_frames += 1
                # Charge longer if enemy HP is high
                hold = 18 if opponent.health < 50 else 34
                if fighter.ai_charge_frames < hold:
                    pressed.add(fighter.proj_key)

    # ---------------------------
    # RETURN FINAL INPUTS
    # ---------------------------
    return InputState(pressed)

# ----------------------------------------------------------
# DRAW UI (HEALTH + TIMER)
# ----------------------------------------------------------
# ----------------------------------------------------------
# DRAW UI (HEALTH + TIMER)
# ----------------------------------------------------------
def draw_ui(p1, p2, time_left, countdown_text=None, round_score=None, target_wins=None):
    if target_wins is None:
        target_wins = SETTINGS.rounds_to_win

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

    # ------------------------------------------------------
    # CUSTOM HUD PORTRAIT RENDERING
    # ------------------------------------------------------
    if HUD_FRAMES_P1 and HUD_FRAMES_P2:
        p1_frame = pick_frame(HUD_FRAMES_P1, p1.health)
        p2_frame = pick_frame(HUD_FRAMES_P2, p2.health)

        # Draw Player 1 HUD Portrait
        if p1_frame:
            screen.blit(p1_frame, (10, 10))

        # Draw Player 2 HUD Portrait
        if p2_frame:
            screen.blit(p2_frame, (WIDTH - p2_frame.get_width() - 10, 10))

    # ------------------------------------------------------
    # FALLBACK: HEALTH BARS
    # ------------------------------------------------------
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

            # Health color transitions from green → yellow → red
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

    # ------------------------------------------------------
    # TIMER RENDERING
    # ------------------------------------------------------
    timer_rect = pygame.Rect(WIDTH // 2 - 70, 12, 140, 48)
    timer_label = countdown_text if countdown_text is not None else str(time_left)
    timer_surface = render_pixel_text(timer_label.rjust(2, " "), WHITE, 3)
    text_pos = timer_surface.get_rect(center=(timer_rect.centerx, timer_rect.y + timer_rect.h - 20))
    screen.blit(timer_surface, text_pos)

    # ------------------------------------------------------
    # ROUND SCORE
    # ------------------------------------------------------
    if round_score is not None:
        p1_score, p2_score = round_score
        score_text = f"Rounds  P1: {p1_score}/{target_wins}  |  P2: {p2_score}/{target_wins}"
        score_surface = ui_font.render(score_text, True, WHITE)
        score_rect = score_surface.get_rect(center=(WIDTH // 2, timer_rect.bottom + 20))

        score_shadow = score_surface.copy()
        score_shadow.fill((0, 0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        screen.blit(score_shadow, score_rect.move(2, 2))
        screen.blit(score_surface, score_rect)

    # Timer panel
    timer_rect = pygame.Rect(WIDTH // 2 - 70, 12, 140, 48)
    timer_label = countdown_text if countdown_text is not None else str(time_left)
    timer_surface = render_pixel_text(timer_label.rjust(2, " "), WHITE, 3)
    text_pos = timer_surface.get_rect(center=(timer_rect.centerx, timer_rect.y + timer_rect.h - 20))
    screen.blit(timer_surface, text_pos)

    if round_score is not None:
        p1_score, p2_score = round_score
        score_text = f"Rounds  P1: {p1_score}/{target_wins}  |  P2: {p2_score}/{target_wins}"
        score_surface = ui_font.render(score_text, True, WHITE)
        score_rect = score_surface.get_rect(center=(WIDTH // 2, timer_rect.bottom + 20))
        score_shadow = score_surface.copy()
        score_shadow.fill((0, 0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        screen.blit(score_shadow, score_rect.move(2, 2))
        screen.blit(score_surface, score_rect)
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

# ----------------------------------------------------------
# HUD FRAME LOADER  <-- INSERTED HERE
# ----------------------------------------------------------
def load_hud_frames(folder, size):
    frames = []
    base = os.path.join(assets_dir, "hud", folder)

    if not os.path.isdir(base):
        return frames

    for fname in sorted(os.listdir(base)):
        if fname.lower().endswith((".png", ".webp")):
            img = pygame.image.load(os.path.join(base, fname)).convert_alpha()
            img = pygame.transform.scale(img, size)
            frames.append(img)

    return frames

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

def upscale_frame(frame, scale):
    """Blow up a HUD frame while keeping the canvas size consistent."""

    src_w, src_h = frame.get_size()
    target_w = max(1, int(round(src_w * scale)))
    target_h = max(1, int(round(src_h * scale)))

    enlarged = pygame.transform.smoothscale(frame, (target_w, target_h))
    canvas = pygame.Surface((src_w, src_h), pygame.SRCALPHA)

    # Center the enlarged art; if it overflows, blitting will crop the edges so
    # the outer dimensions stay the same and the HUD anchors remain stable.
    offset_x = (src_w - target_w) // 2
    offset_y = (src_h - target_h) // 2
    canvas.blit(enlarged, (offset_x, offset_y))
    return canvas


if len(HUD_FRAMES_P2) >= 2:
    HUD_FRAMES_P2[1] = upscale_frame(HUD_FRAMES_P2[1], 1.12)


menu_title = menu_font.render("Big Boy Simulator", True, WHITE)
start_prompt = timer_font.render(
    "Press ENTER or NUMPAD ENTER for two players", True, WHITE
)
single_p1_prompt = controls_font.render("Press 1 to play as Player 1 (Player 2 uses AI)", True, WHITE)
single_p2_prompt = controls_font.render("Press 2 to play as Player 2 (Player 1 uses AI)", True, WHITE)
options_prompt = controls_font.render("Press O to tweak rounds, timer, and AI", True, WHITE)
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
options_pos = options_prompt.get_rect(midtop=(WIDTH // 2, single_p2_pos.bottom + 16))

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
                if e.key == pygame.K_o:
                    options_menu()

        screen.blit(menu_bg, (0, 0))

        screen.blit(menu_title, title_pos)
        screen.blit(start_prompt, prompt_pos)
        screen.blit(single_p1_prompt, single_p1_pos)
        screen.blit(single_p2_prompt, single_p2_pos)
        screen.blit(options_prompt, options_pos)
        for line, pos in zip(p1_controls, p1_control_positions):
            screen.blit(line, pos)
        for line, pos in zip(p2_controls, p2_control_positions):
            screen.blit(line, pos)

        pygame.display.flip()
        clock.tick(60)


def options_menu():
    selection = 0
    header = menu_font.render("Options", True, WHITE)
    header_rect = header.get_rect(center=(WIDTH // 2, 90))

    def clamp(val, lo, hi):
        return max(lo, min(hi, val))

    def option_value_text():
        return [
            f"{SETTINGS.rounds_to_win} (best of {SETTINGS.rounds_to_win * 2 - 1})",
            f"{SETTINGS.round_time} seconds",
            f"{SETTINGS.overtime_time} seconds",
            f"{SETTINGS.ai_aggression:.1f}x",
        ]

    instructions = [
        ui_font.render("UP/DOWN: select", True, WHITE),
        ui_font.render("LEFT/RIGHT: change", True, WHITE),
        ui_font.render("ENTER/ESC: back to menu", True, WHITE),
    ]

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_BACKSPACE):
                    return
                if e.key in (pygame.K_UP, pygame.K_w):
                    selection = (selection - 1) % 4
                if e.key in (pygame.K_DOWN, pygame.K_s):
                    selection = (selection + 1) % 4
                if e.key in (pygame.K_LEFT, pygame.K_a):
                    if selection == 0:
                        SETTINGS.rounds_to_win = clamp(SETTINGS.rounds_to_win - 1, 1, 5)
                    elif selection == 1:
                        SETTINGS.round_time = clamp(SETTINGS.round_time - 15, 30, 120)
                    elif selection == 2:
                        SETTINGS.overtime_time = clamp(SETTINGS.overtime_time - 5, 10, 45)
                    elif selection == 3:
                        SETTINGS.ai_aggression = round(clamp(SETTINGS.ai_aggression - 0.1, 0.5, 1.6), 1)
                if e.key in (pygame.K_RIGHT, pygame.K_d):
                    if selection == 0:
                        SETTINGS.rounds_to_win = clamp(SETTINGS.rounds_to_win + 1, 1, 5)
                    elif selection == 1:
                        SETTINGS.round_time = clamp(SETTINGS.round_time + 15, 30, 120)
                    elif selection == 2:
                        SETTINGS.overtime_time = clamp(SETTINGS.overtime_time + 5, 10, 45)
                    elif selection == 3:
                        SETTINGS.ai_aggression = round(clamp(SETTINGS.ai_aggression + 0.1, 0.5, 1.6), 1)

        values = option_value_text()

        screen.blit(menu_bg, (0, 0))
        screen.blit(header, header_rect)

        entries = [
            "Rounds to win",
            "Round timer",
            "Overtime timer",
            "AI aggression",
        ]

        start_y = 200
        spacing = 60
        for i, label in enumerate(entries):
            color = WHITE if i == selection else (200, 200, 200)
            label_surf = controls_font.render(label, True, color)
            value_surf = ui_font.render(values[i], True, color)

            label_pos = label_surf.get_rect(midleft=(WIDTH // 2 - 200, start_y + i * spacing))
            value_pos = value_surf.get_rect(midright=(WIDTH // 2 + 220, start_y + i * spacing))

            screen.blit(label_surf, label_pos)
            screen.blit(value_surf, value_pos)

        for i, line in enumerate(instructions):
            pos = line.get_rect(center=(WIDTH // 2, HEIGHT - 120 + i * 26))
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
def draw_countdown_frame(p1, p2, label, starting_time, round_score=None, target_wins=None):
    if target_wins is None:
        target_wins = SETTINGS.rounds_to_win
    screen.blit(bg, (0, 0))
    p1.draw(screen)
    p2.draw(screen)
    # Show the full round timer value while overlaying the countdown text.
    draw_ui(p1, p2, starting_time, countdown_text=label, round_score=round_score, target_wins=target_wins)

    overlay = render_pixel_text(label, WHITE, 5)
    outline = overlay.copy()
    outline.fill((0, 0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    outline_rect = overlay.get_rect(center=(WIDTH // 2, HEIGHT // 2))
    shadow = outline_rect.move(4, 4)
    screen.blit(outline, shadow)
    screen.blit(overlay, outline_rect)

    pygame.display.flip()

def run_round_countdown(p1, p2, starting_time, round_score=None, target_wins=None):
    if target_wins is None:
        target_wins = SETTINGS.rounds_to_win
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

            draw_countdown_frame(p1, p2, label, starting_time, round_score=round_score, target_wins=target_wins)
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


def draw_pause_overlay(p1, p2, timer_label, round_score, target_wins):
    shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 170))
    screen.blit(shade, (0, 0))

    title = render_pixel_text("PAUSED", WHITE, 4)
    title_rect = title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40))

    screen.blit(title, title_rect)

    instructions = [
        ui_font.render("Enter/Esc: Resume", True, WHITE),
        ui_font.render("R: Restart round", True, WHITE),
        ui_font.render("Q: Quit to main menu", True, WHITE),
    ]

    for i, line in enumerate(instructions):
        pos = line.get_rect(center=(WIDTH // 2, HEIGHT // 2 + i * 26))
        screen.blit(line, pos)

    draw_ui(p1, p2, timer_label, countdown_text="PAUSED", round_score=round_score, target_wins=target_wins)

# ----------------------------------------------------------
# SINGLE ROUND
# ----------------------------------------------------------
def play_round(p1, p2, p1_ai=False, p2_ai=False, round_score=None, target_wins=None, settings=None):
    settings = settings or SETTINGS
    if target_wins is None:
        target_wins = settings.rounds_to_win

    time_left = settings.round_time
    timer_label = str(time_left)
    tick = 0
    projectiles = []
    bottles = []
    overtime = False
    sudden_death = False
    paused = False

    run_round_countdown(p1, p2, time_left, round_score=round_score, target_wins=target_wins)

    while True:
        keys = pygame.key.get_pressed()

        for e in pygame.event.get():
            if e.type == pygame.QUIT: sys.exit()
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    paused = not paused
                elif paused:
                    if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        paused = False
                    elif e.key == pygame.K_r:
                        return "restart"
                    elif e.key == pygame.K_q:
                        return "menu"

        if paused:
            screen.blit(bg, (0, 0))
            for p in projectiles: p.draw(screen)
            for b in bottles:    b.draw(screen)
            p1.draw(screen)
            p2.draw(screen)
            draw_pause_overlay(p1, p2, timer_label, round_score, target_wins)
            pygame.display.flip()
            clock.tick(30)
            continue

        screen.blit(bg, (0, 0))

        p1_inputs = keys if not p1_ai else build_ai_inputs(p1, p2, pygame.K_a, pygame.K_d, pygame.K_w, aggression=settings.ai_aggression)
        p2_inputs = keys if not p2_ai else build_ai_inputs(p2, p1, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, aggression=settings.ai_aggression)

        # update
        p1.update(p1_inputs, pygame.K_a, pygame.K_d, pygame.K_w, p2)
        p2.update(p2_inputs, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, p1)
        if p1.just_shot:
            direction = -1 if p1.facing_left else 1
            bottles.append(Bottle(p1.rect.centerx, p1.rect.y, direction, power=p1.just_shot_power))

        if p2.just_shot:
            direction = -1 if p2.facing_left else 1
            start_x = p2.rect.left if direction == -1 else p2.rect.right - 20
            projectiles.append(Pencil(start_x, p2.rect.centery, direction))

        # update projectiles
        for p in projectiles[:]:
            p.update()
            if p.rect.colliderect(p1.rect):
                p1.health -= 5
                p1.set_hit()
                projectiles.remove(p)
            elif not p.active:
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

        draw_ui(p1, p2, timer_label, round_score=round_score, target_wins=target_wins)
        
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
                time_left = settings.overtime_time
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

        target_wins = SETTINGS.rounds_to_win
        match_aborted = False

        while p1_score < target_wins and p2_score < target_wins:
            p1, p2 = create_players()
            winner = play_round(
                p1,
                p2,
                p1_ai=p1_ai,
                p2_ai=p2_ai,
                round_score=(p1_score, p2_score),
                target_wins=target_wins,
                settings=SETTINGS,
            )

            if winner == "restart":
                continue
            if winner == "menu":
                match_aborted = True
                break

            round_winner_text = "PLAYER 1 WINS!" if winner == 1 else "PLAYER 2 WINS!"
            if winner == 1:
                p1_score += 1
                p1.set_win()
            else:
                p2_score += 1
                p2.set_win()

            show_round_message(round_winner_text, "you win big boy negative aura")

        if match_aborted:
            continue

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













































