import pygame
import sys
import os
import random

global_projectiles = []


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
        # How many rounds to win a match
        self.rounds_to_win = 3

        # AI tuning (your old system)
        self.ai_aggression = 1.0

        # NEW: Difficulty system ("normal", "hard", "sweaty")
        self.ai_difficulty = "normal"  # normal, sweaty, bigboy, doumi gang

        # REQUIRED BY play_round()
        self.round_time = 60          # Normal round length
        self.overtime_time = 20       # Overtime length


SETTINGS = GameSettings()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
assets_dir = os.path.join(BASE_DIR, "assets")
BASE_P1 = os.path.join(assets_dir, "player1")
BASE_P2 = os.path.join(assets_dir, "player2")
BASE_P3 = os.path.join(assets_dir, "player3")

CHARACTER_ROSTER = {
    "player1": {
        "label": "Player One",
        "folder": BASE_P1,
        "prefix": "p1",
        "card_color": (80, 180, 255),
    },
    "player2": {
        "label": "Player Two",
        "folder": BASE_P2,
        "prefix": "p2",
        "card_color": (255, 140, 180),
    },
    "player3": {
        "label": "Player Three",
        "folder": BASE_P3,
        "prefix": "p3",
        "card_color": (140, 220, 160),
    },
}

def filter_character_roster(roster):
    """Drop characters whose asset folders or idle sprites are missing.

    The menu builds previews from each fighter's `<prefix>_idle1.png` sprite. If
    the folder or base frame is missing, `load_sprite` exits the game and the
    menu never renders. Filtering the roster up front keeps the selection screen
    resilient to incomplete asset packs.
    """

    filtered = {}

    for key, data in roster.items():
        folder = data.get("folder")
        prefix = data.get("prefix")

        if not folder or not prefix:
            continue

        idle_path = os.path.join(folder, f"{prefix}_idle1.png")

        if not os.path.isdir(folder):
            print(f"[WARN] Skipping {key}: missing folder {folder}")
            continue

        if not os.path.exists(idle_path):
            print(f"[WARN] Skipping {key}: missing idle sprite {idle_path}")
            continue

        filtered[key] = data

    return filtered


CHARACTER_ROSTER = filter_character_roster(CHARACTER_ROSTER)
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


def remove_flat_background(surface, threshold=245):
    """Colorkey surfaces that ship with a bright, uniform backdrop.

    Many sprite exports (especially for Player 3) include an opaque white
    background. Sampling the top-left pixel is usually sufficient to detect
    that canvas color; when it is bright enough, treat it as a colorkey so the
    art can blend with the stage and HUD without a boxy outline.
    """

    surface = surface.convert_alpha()
    corner_color = surface.get_at((0, 0))
    avg = (corner_color.r + corner_color.g + corner_color.b) / 3

    if corner_color.a == 255 and avg >= threshold:
        surface = surface.copy()
        surface.set_colorkey((corner_color.r, corner_color.g, corner_color.b))

    return surface


def clean_hud_frame(frame):
    """Remove bright, flat backgrounds so HUD art blends with the scene."""

    return remove_flat_background(frame)

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

def upscale_frame(frame, scale):
    """Blow up a HUD frame while keeping the canvas size consistent."""

    src_w, src_h = frame.get_size()
    target_w = max(1, int(round(src_w * scale)))
    target_h = max(1, int(round(src_h * scale)))

    enlarged = pygame.transform.smoothscale(frame, (target_w, target_h))
    canvas = pygame.Surface((src_w, src_h), pygame.SRCALPHA)

    offset_x = (src_w - target_w) // 2
    offset_y = (src_h - target_h) // 2
    canvas.blit(enlarged, (offset_x, offset_y))
    return canvas


def build_character_hud_frames(character_key, mirror=False):
    data = CHARACTER_ROSTER.get(character_key)
    if not data:
        return []

    frames = load_hud_frames(character_key, HUD_FRAME_SIZE, mirror=mirror)

    if not frames:
        idle_path = os.path.join(data["folder"], f"{data['prefix']}_idle1.png")
        if os.path.exists(idle_path):
            frame = pygame.image.load(idle_path).convert_alpha()
            frame = normalize_hud_frame(frame, HUD_FRAME_SIZE, mirror=mirror)
            frames = [clean_hud_frame(frame)]

    if character_key == "player2" and len(frames) >= 2:
        frames[1] = upscale_frame(frames[1], 1.12)

    return frames


HUD_FRAMES_P1 = []
HUD_FRAMES_P2 = []

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
def load_sprite(folder, filename, flip=True):
    full = os.path.join(folder, filename)
    if not os.path.exists(full):
        # During headless tests we do not always ship the full art pack. Instead
        # of aborting, generate a simple placeholder surface so logic can
        # continue to run.
        print("MISSING:", full)
        img = pygame.Surface((SPRITE_W, SPRITE_H), pygame.SRCALPHA)
    else:
        img = pygame.image.load(full).convert_alpha()
        img = pygame.transform.scale(img, (SPRITE_W, SPRITE_H))

    if folder == BASE_P3:
        img = remove_flat_background(img, threshold=230)
    if flip:
        img = pygame.transform.flip(img, True, False)
    return img
# ----------------------------------------------------------
# PROJECTILES
# ----------------------------------------------------------
class Pencil:
    def __init__(self, x, y, direction, owner=None):
        self.rect = pygame.Rect(x, y, 20, 4)
        self.speed = 12 * direction
        self.direction = direction      # <── REQUIRED FOR AI
        self.active = True
        self.owner = owner

    def update(self):
        self.rect.x += self.speed
        if self.rect.right < 0 or self.rect.left > WIDTH:
            self.active = False

    def draw(self, surf):
        pygame.draw.rect(surf, YELLOW, self.rect)
        # pencil tip
        tip = pygame.Rect(self.rect.right - 3, self.rect.y, 3, 4)
        pygame.draw.rect(surf, (120, 80, 20), tip)

class Bottle:
    def __init__(self, x, y, direction, power=1.0, owner=None):

        self.x = x
        self.y = y

        self.direction = direction
        speed_scale = power

        # must be defined BEFORE using them
        self.vx = 8 * speed_scale * direction
        self.vy = -8 - 4 * speed_scale
        self.gravity = 0.5
        self.owner = owner


        # Sprites
        img = pygame.image.load(os.path.join(BASE_P1, "p1_bottle1.png")).convert_alpha()
        self.img = pygame.transform.scale(img, (25, 40))
        self.width, self.height = self.img.get_size()

        broken = pygame.image.load(os.path.join(BASE_P1, "p1_bottle_broken.png")).convert_alpha()
        self.broken = pygame.transform.scale(broken, (30, 30))
        self.broken_width, self.broken_height = self.broken.get_size()

        # State flags
        self.hit = False
        self.shatter_timer = 0
        self.dead = False
        self.active = True

    @property
    def rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def update(self):
        if not self.hit:
            # Movement
            self.x += self.vx
            self.vy += self.gravity
            self.y += self.vy

            # Hit ground
            if self.y >= GROUND_Y - self.height:
                self.hit = True
                self.shatter_timer = 15

                # Snap + switch sprite size
                self.y = GROUND_Y - self.broken_height
                self.width = self.broken_width
                self.height = self.broken_height
                self.vx = 0
                self.vy = 0

        elif self.shatter_timer > 0:
            self.shatter_timer -= 1
        else:
            self.dead = True

        if self.dead:
            self.active = False

        # Off-screen
        if self.x < -50 or self.x > WIDTH + 50:
            self.active = False

    def draw(self, surf):
        if self.hit:
            surf.blit(self.broken, (self.x, self.y))
        else:
            surf.blit(self.img, (self.x, self.y))


def apply_bottle_shatter_damage(bottle, targets):
    """Apply bottle shatter damage to any non-owner fighters it overlaps."""

    if not bottle.hit:
        return []

    hit_targets = []
    # Use the bottle's current footprint for collision instead of a hard-coded
    # rectangle so the shatter hitbox lines up with the sprite swap that occurs
    # when the bottle breaks. The original throw direction is preserved even
    # after velocities are zeroed on impact so knockback is applied consistently
    # to targets on either side of the thrower.
    hitbox = pygame.Rect(bottle.x, bottle.y, bottle.width, bottle.height)
    knock_dir = bottle.direction if getattr(bottle, "direction", 0) else (-1 if bottle.vx > 0 else 1)

    for target in targets:
        if target is bottle.owner:
            continue
        if hitbox.colliderect(target.rect):
            target.take_hit(15, knock_dir)
            hit_targets.append(target)

    return hit_targets


class KickWave:
    def __init__(self, x, y, direction, power=1.0, owner=None):

        base_speed = 9 + int(3 * power)
        self.speed = base_speed * direction
        self.direction = direction
        self.damage = 8 + int(4 * power)
        self.active = True
        self.owner = owner

        self.rect = pygame.Rect(x, y, 36, 22)
        self.trail = []

    def update(self):
        self.rect.x += self.speed
        self.trail.append(self.rect.copy())
        self.trail = self.trail[-6:]

        if self.rect.right < -20 or self.rect.left > WIDTH + 20:
            self.active = False

    def draw(self, surf):
        # Draw a faint trail so the kickwave feels energetic
        alpha_steps = [140, 110, 80, 60, 40, 30]
        for rect, alpha in zip(reversed(self.trail), alpha_steps):
            ghost = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(ghost, (120, 220, 160, alpha), ghost.get_rect(), border_radius=6)
            surf.blit(ghost, rect.topleft)

        pygame.draw.rect(surf, (80, 240, 160), self.rect, border_radius=8)


def build_bottle_throw(fighter, direction, power):
    return Bottle(fighter.rect.centerx, fighter.rect.y, direction, power=power, owner=fighter)


def build_pencil_throw(fighter, direction, power):
    start_x = fighter.rect.left if direction == -1 else fighter.rect.right - 20
    return Pencil(start_x, fighter.rect.centery, direction, owner=fighter)


def build_kickwave(fighter, direction, power):
    start_x = fighter.rect.centerx + direction * 18
    start_y = fighter.rect.centery - 8
    return KickWave(start_x, start_y, direction, power=power)

# ----------------------------------------------------------
# FIGHTER CLASS (FINAL, CLEAN, WORKING)
# ----------------------------------------------------------
class Fighter:
    def __init__(
        self,
        x,
        folder,
        idle,
        walk,
        run,
        attack,
        hit,
        win,
        flip=False,
        melee_key=None,
        proj_key=None,
        crouch_key=None,
        block_key=None,
        move_config=None,
        character_key=None,
    ):


        self.x = x
        self.melee_key = melee_key
        self.proj_key = proj_key

        move_config = move_config or {}

        self.character_key = character_key or "player1"
        self.health = 100
        self.velocity = move_config.get("speed", 5)

        self.melee_damage = move_config.get("melee_damage", 10)
        self.melee_cooldown = move_config.get("melee_cooldown", 18)
        self.kick_damage = move_config.get("kick_damage")
        self.kick_cooldown = move_config.get("kick_cooldown")
        self.projectile_cooldown = move_config.get("projectile_cooldown", 60)
        self.projectile_attack_cooldown = move_config.get("projectile_attack_cooldown", 20)
        self.max_proj_charge = move_config.get("max_proj_charge", 45)
        self.animation_speed_scale = move_config.get("animation_speed_scale", 1.0)

        self.projectile_factory = move_config.get("projectile_factory")

        # Movement
        self.vel_x = 0
        self.vel_y = 0
        self.gravity = 1.0
        self.on_ground = True

        # AI fields
        self.combo_step = 0
        self.last_hit_timer = 0
        self.input_buffer = set()
        self.buffer_timer = 0
        self.idle_frames_since_action = 0

        # Facing direction
        self.facing_left = flip
        self.folder = folder

        self.crouch_key = crouch_key
        self.block_key = block_key
        self.crouching = False
        self.blocking = False

        # -------------------------------
        # DASH SYSTEM
        # -------------------------------
        self.last_left_tap = 0
        self.last_right_tap = 0
        self.prev_left_down = False
        self.prev_right_down = False

        self.dash_time = 0
        self.dash_speed = 13
        self.dash_dir = 0
        self.double_tap_window = 200  # ms

        # -------------------------------
        # LOAD FRAMES
        # -------------------------------
        def load_frames(names):
            base = [load_sprite(folder, f, False) for f in names]
            flipd = [pygame.transform.flip(img, True, False) for img in base]
            return base, flipd

        self.idle_frames, self.idle_frames_flipped = load_frames(idle)
        self.walk_frames, self.walk_frames_flipped = load_frames(walk)
        self.attack_frames, self.attack_frames_flipped = load_frames(attack)
        self.run_frames, self.run_frames_flipped = load_frames(run or walk)
        self.hit_frames, self.hit_frames_flipped = load_frames(hit)
        self.win_frames, self.win_frames_flipped = load_frames(win)

        def build_crouch_frames(idle_frames):
            crouch_frames = []
            scale = 0.7

            for frame in idle_frames:
                w, h = frame.get_size()
                scaled_h = max(15, int(round(h * scale)))
                crouch_frames.append(pygame.transform.smoothscale(frame, (w, scaled_h)))

            flipped = [pygame.transform.flip(img, True, False) for img in crouch_frames]
            return crouch_frames, flipped

        self.crouch_frames, self.crouch_frames_flipped = build_crouch_frames(self.idle_frames)

        # Animation state
        self.state = "idle"
        self.frame = 0
        self.counter = 0
        self.idle_speed = 15

        # Position
        self.rect = self.idle_frames[0].get_rect()
        self.rect.midbottom = (x, GROUND_Y)

        # Cooldowns / attacks
        self.attack_cool = 0
        self.proj_cool = 0
        self.just_shot = False
        self.just_shot_power = 1.0
        self.proj_charging = False
        self.proj_charge = 0

        self.hit_timer = 0
        self.win_timer = 0

        # First image
        self.image = (
            self.idle_frames_flipped[0] if self.facing_left else self.idle_frames[0]
        )

    # ----------------------------------------------------------
    # DOUBLE TAP DASH CHECK
    # ----------------------------------------------------------
    def check_dash(self, keys, left, right):
        now = pygame.time.get_ticks()
        left_down = keys[left]
        right_down = keys[right]

        # Left double tap
        if left_down and not self.prev_left_down:
            if now - self.last_left_tap <= self.double_tap_window:
                self.dash_time = 10
                self.dash_dir = -1
            self.last_left_tap = now

        # Right double tap
        if right_down and not self.prev_right_down:
            if now - self.last_right_tap <= self.double_tap_window:
                self.dash_time = 10
                self.dash_dir = 1
            self.last_right_tap = now

        self.prev_left_down = left_down
        self.prev_right_down = right_down

    # ----------------------------------------------------------
    # SET HIT / WIN
    # ----------------------------------------------------------
    def set_hit(self):
        self.state = "hit"
        self.frame = 0
        self.hit_timer = 12

    def set_win(self):
        self.state = "win"
        self.frame = 0
        self.win_timer = 999

    def _perform_melee(self, damage, cooldown, opponent):
        self.attack_cool = cooldown
        self.state = "attack"

        if self.rect.colliderect(opponent.rect):
            attack_dir = -1 if self.facing_left else 1
            opponent.take_hit(damage, attack_dir)


    # ----------------------------------------------------------
    # UPDATE (MOVEMENT, JUMP, ATTACK)
    # ----------------------------------------------------------
    def update(self, keys, left, right, jump, crouch, block, opponent):

        # Face opponent
        if opponent:
            self.facing_left = opponent.rect.centerx < self.rect.centerx

        self.crouching = keys[crouch] and self.on_ground if crouch is not None else False
        self.blocking = keys[block] and self.on_ground if block is not None else False

        # Win animation
        if self.win_timer > 0:
            self.animate(self.win_frames, self.win_frames_flipped, 12)
            return

        # Hit animation
        if self.hit_timer > 0:
            self.hit_timer -= 1
            self.animate(self.hit_frames, self.hit_frames_flipped, 6)
            return

        moving = False
        self.just_shot = False

        # DASH
        self.check_dash(keys, left, right)
        dash_applied = False

        if not self.blocking and not self.crouching:
            if self.dash_time > 0:
                dash_vel = self.dash_speed
                self.dash_time -= 1

                if self.dash_dir == -1:
                    self.rect.x -= dash_vel
                    self.vel_x = -dash_vel
                    moving = True
                    dash_applied = True

                elif self.dash_dir == 1:
                    self.rect.x += dash_vel
                    self.vel_x = dash_vel
                    moving = True
                    dash_applied = True

            # NORMAL MOVE
            if not dash_applied:
                self.vel_x = 0
                if keys[left]:
                    self.rect.x -= self.velocity
                    self.vel_x = -self.velocity
                    moving = True
                if keys[right]:
                    self.rect.x += self.velocity
                    self.vel_x = self.velocity
                    moving = True

        # Screen bounds
        self.rect.x = max(0, min(self.rect.x, WIDTH - self.rect.width))

        # JUMP
        if keys[jump] and self.on_ground and not self.blocking:
            self.vel_y = -12
            self.on_ground = False

        self.vel_y += self.gravity
        self.rect.y += self.vel_y

        if self.rect.bottom >= GROUND_Y:
            self.rect.bottom = GROUND_Y
            self.vel_y = 0
            self.on_ground = True

        # ATTACK
        if self.attack_cool > 0: self.attack_cool -= 1
        if self.proj_cool > 0: self.proj_cool -= 1

        # MELEE (punch / kick)
        if keys[self.melee_key] and self.attack_cool == 0 and not self.blocking:
            if (
                self.character_key == "player3"
                and self.crouching
                and self.kick_damage is not None
            ):
                self._perform_melee(self.kick_damage, self.kick_cooldown or self.melee_cooldown, opponent)
            else:
                self._perform_melee(self.melee_damage, self.melee_cooldown, opponent)

        # PROJECTILE
        elif keys[self.proj_key] and self.attack_cool == 0 and self.proj_cool == 0 and not self.blocking:
            if not self.proj_charging:
                self.proj_charging = True
                self.proj_charge = 0

            self.proj_charge = min(self.proj_charge + 1, self.max_proj_charge)
            self.state = "attack"

        elif self.proj_charging:
            ratio = self.proj_charge / self.max_proj_charge
            self.just_shot_power = 0.5 + ratio
            self.attack_cool = self.projectile_attack_cooldown
            self.proj_cool = self.projectile_cooldown
            self.just_shot = True
            self.proj_charging = False
            self.proj_charge = 0
            self.state = "attack"

        else:
            self.state = "walk" if moving else "idle"

        if self.blocking:
            self.state = "block"
        elif self.crouching and self.on_ground:
            self.state = "crouch"
        elif self.state not in ["attack", "hit", "win"]:
            if dash_applied:
                self.state = "run"
            else:
                self.state = "walk" if moving else "idle"

        # ANIMATION
        if self.state == "idle":
            self.animate(self.idle_frames, self.idle_frames_flipped, self.idle_speed, adjust_hitbox=True)
        elif self.state == "walk":
            self.animate(self.walk_frames, self.walk_frames_flipped, 11, adjust_hitbox=True)
        elif self.state == "run":
            self.animate(self.run_frames, self.run_frames_flipped, 7, adjust_hitbox=True)
        elif self.state == "attack":
            self.animate(self.attack_frames, self.attack_frames_flipped, 9, adjust_hitbox=True)
        elif self.blocking:
            self.state = "block"
            self.animate(self.idle_frames, self.idle_frames_flipped, self.idle_speed, adjust_hitbox=True)
        elif self.crouching:
            self.state = "crouch"
            self.animate(self.crouch_frames, self.crouch_frames_flipped, self.idle_speed, adjust_hitbox=True)
        else:
            self.state = "walk" if moving else "idle"

    def spawn_projectile(self):
        if not self.just_shot or not self.projectile_factory:
            return None

        direction = -1 if self.facing_left else 1
        projectile = self.projectile_factory(self, direction, self.just_shot_power)

        # ``just_shot`` stays True until we explicitly clear it, which caused a
        # new projectile to spawn every frame after releasing the attack button.
        # Reset the flags as soon as the projectile is built so a single release
        # produces a single projectile as intended.
        self.just_shot = False
        self.just_shot_power = 1.0

        return projectile

    # ----------------------------------------------------------
    # ANIMATION HANDLER (ONLY ONE!)
    # ----------------------------------------------------------
    def animate(self, frames, frames_flipped, speed, adjust_hitbox=False):
        frame_list = frames_flipped if self.facing_left else frames

        scaled_speed = max(1, int(round(speed * self.animation_speed_scale)))

        self.counter += 1
        if self.counter >= scaled_speed:
            self.counter = 0
            self.frame += 1

        if self.frame >= len(frame_list):
            self.frame = 0
            if self.state == "attack":
                self.state = "idle"

        self.image = frame_list[self.frame]

        if adjust_hitbox:
            prev_midbottom = self.rect.midbottom
            self.rect = self.image.get_rect()
            self.rect.midbottom = prev_midbottom

    # ----------------------------------------------------------
    # DRAW (ONLY ONE!)
    # ----------------------------------------------------------
    def draw(self, surf):
        surf.blit(self.image, self.rect.topleft)

    def take_hit(self, damage, attack_dir=0):
        if self.blocking and self.on_ground:
            reduced = max(1, int(damage * 0.25))
            self.health -= reduced
            self.state = "block"
            self.frame = 0
            return

        self.health -= damage
        self.set_hit()
# ----------------------------------------------------------
# CREATE PLAYERS
# ----------------------------------------------------------
def create_players(p1_choice="player1", p2_choice="player2"):
    def build_move_config(character_key):
        if character_key == "player1":
            return {
                "melee_damage": 10,
                "melee_cooldown": 18,
                "projectile_cooldown": 60,
                "projectile_attack_cooldown": 22,
                "projectile_factory": build_bottle_throw,
                "max_proj_charge": 45,
                "speed": 5,
            }

        if character_key == "player2":
            return {
                "melee_damage": 9,
                "melee_cooldown": 16,
                "projectile_cooldown": 45,
                "projectile_attack_cooldown": 18,
                "projectile_factory": build_pencil_throw,
                "max_proj_charge": 38,
                "speed": 5,
            }

        # Player 3 specializes in aggressive kicks and a custom kickwave projectile.
        return {
            "melee_damage": 10,
            "melee_cooldown": 13,
            "kick_damage": 16,
            "kick_cooldown": 22,
            "projectile_cooldown": 52,
            "projectile_attack_cooldown": 18,
            "projectile_factory": build_kickwave,
            "max_proj_charge": 32,
            "speed": 6,
            "animation_speed_scale": 1.35,
        }
    def build_sprite_sets(character_key, prefix):
        if character_key == "player3":
            idle = [f"{prefix}_idle{i}.png" for i in range(1, 5)]
            walk = [f"{prefix}_walk{i}.png" for i in range(1, 5)]
            run = [f"{prefix}_run{i}.png" for i in range(1, 4)]
        else:
            idle = [f"{prefix}_idle1.png", f"{prefix}_idle2.png"]
            walk = [f"{prefix}_walk1.png", f"{prefix}_walk2.png"]
            run = walk

        attack = [f"{prefix}_attack1.png", f"{prefix}_attack2.png"]
        hit = [f"{prefix}_hit1.png", f"{prefix}_hit2.png"]
        win = [f"{prefix}_win1.png"]
        return idle, walk, run, attack, hit, win

    def build_fighter(character_key, x, flip, melee_key, proj_key, crouch_key, block_key):
        data = CHARACTER_ROSTER.get(character_key, CHARACTER_ROSTER["player1"])
        idle, walk, run, attack, hit, win = build_sprite_sets(
            character_key, data["prefix"]
        )
        move_config = build_move_config(character_key)

        return Fighter(
            x,
            data["folder"],
            idle,
            walk,
            run,
            attack,
            hit,
            win,
            flip=flip,
            melee_key=melee_key,
            proj_key=proj_key,
            crouch_key=crouch_key,
            block_key=block_key,
            move_config=move_config,
            character_key=character_key,
        )

    p1 = build_fighter(
        p1_choice,
        150,
        False,
        pygame.K_SPACE,
        pygame.K_q,
        pygame.K_s,
        pygame.K_LSHIFT,
    )

    p2 = build_fighter(
        p2_choice,
        770,
        True,
        pygame.K_RETURN,
        pygame.K_p,
        pygame.K_DOWN,
        pygame.K_RSHIFT,
    )

    return p1, p2
# ----------------------------------------------------------
# INPUT STATE (REQUIRED FOR AI)
# ----------------------------------------------------------
class InputState:
    """Lightweight key-state wrapper so AI can output key presses."""

    def __init__(self, pressed=None):
        self.pressed = set(pressed or [])

    def __getitem__(self, key):
        return key in self.pressed

# ----------------------------------------------------------
# CLEAN + FINAL AI SYSTEM  
# ----------------------------------------------------------
def build_ai_inputs(fighter, opponent, left_key, right_key, jump_key, aggression=1.0):
    # Carry over buffered inputs so the AI holds buttons for a few frames,
    # mimicking how a human commits to a jump or attack instead of frame-perfect
    # tap dancing.
    pressed = set(getattr(fighter, "input_buffer", set())) if getattr(fighter, "buffer_timer", 0) > 0 else set()
    if getattr(fighter, "buffer_timer", 0) > 0:
        fighter.buffer_timer -= 1

    # ----------------------------------------
    # BASE INFO
    # ----------------------------------------
    dx = opponent.rect.centerx - fighter.rect.centerx
    distance = abs(dx)
    moving_right = dx > 0


    fighter.facing_left = opponent.rect.centerx < fighter.rect.centerx

    diff = SETTINGS.ai_difficulty

    # ----------------------------------------
    # DIFFICULTY PRESETS
    # ----------------------------------------
    if diff == "normal":
        MELEE_BASE = 0.40
        COMBO_BASE = 0.30
        THROW_BASE = 0.25
        DODGE_BASE = 0.45
        SHUFFLE = 0.05
        PREDICT_FR = 4
        CORNER_TRAP = False
        WHIFF_PUNISH = False
        ANTI_AIR = 0.20
        FAKEOUT = 0.02

    elif diff == "sweaty":
        MELEE_BASE = 0.65
        COMBO_BASE = 0.55
        THROW_BASE = 0.45
        DODGE_BASE = 0.70
        SHUFFLE = 0.12
        PREDICT_FR = 8
        CORNER_TRAP = False
        WHIFF_PUNISH = True
        ANTI_AIR = 0.45
        FAKEOUT = 0.03

    elif diff == "bigboy":
        MELEE_BASE = 0.90
        COMBO_BASE = 0.85
        THROW_BASE = 0.70
        DODGE_BASE = 0.85
        SHUFFLE = 0.20
        PREDICT_FR = 12
        CORNER_TRAP = True
        WHIFF_PUNISH = True
        ANTI_AIR = 0.75
        FAKEOUT = 0.01

    else:  # doumi gang
        MELEE_BASE = 0.98
        COMBO_BASE = 0.96
        THROW_BASE = 0.85
        DODGE_BASE = 0.95
        SHUFFLE = 0.30
        PREDICT_FR = 16
        CORNER_TRAP = True
        WHIFF_PUNISH = True
        ANTI_AIR = 0.92
        FAKEOUT = 0.00

    SPACING_LO = 80
    SPACING_HI = 170

    # Character-specific tuning to keep the mirror match AI from feeling lopsided.
    # Player 2 has a faster projectile and snappier melee cooldowns, so bias the
    # bot toward maintaining pressure and peppering in more throws to leverage
    # those advantages when controlled by the AI.
    if fighter.character_key == "player2":
        MELEE_BASE = min(1.0, MELEE_BASE + 0.08)
        COMBO_BASE = min(1.0, COMBO_BASE + 0.06)
        THROW_BASE = min(1.0, THROW_BASE + 0.10)
        SHUFFLE += 0.04
        SPACING_LO = 70
        SPACING_HI = 150

    # ----------------------------------------
    # AGGRESSION SCALING
    # ----------------------------------------
    health_delta = opponent.health - fighter.health
    clutch_bonus = 0.12 if opponent.health < 35 else 0.0
    survival_penalty = 0.12 if fighter.health < 25 and opponent.health > fighter.health else 0.0

    MELEE = min(1.0, MELEE_BASE * aggression + clutch_bonus - survival_penalty)
    COMBO = min(1.0, COMBO_BASE * aggression + clutch_bonus * 0.7 - survival_penalty * 0.5)
    THROW = min(1.0, THROW_BASE * aggression + max(0, -health_delta) * 0.002)
    DODGE = min(1.0, DODGE_BASE * aggression)

    danger_left = danger_right = danger_jump = False

    for proj in global_projectiles:
        if not getattr(proj, "active", True):
            continue

        direction = getattr(proj, "direction", 1)
        future_x = proj.rect.centerx + direction * PREDICT_FR * 6

        pdx = future_x - fighter.rect.centerx
        pdy = proj.rect.centery - fighter.rect.centery

        if abs(pdx) < 140 and abs(pdy) < 70:
            if direction > 0:
                danger_right = True
            else:
                danger_left = True

            if fighter.on_ground and random.random() < DODGE:
                danger_jump = True

    if danger_jump and fighter.on_ground:
        pressed.add(jump_key)
    if danger_left:
        pressed.add(right_key)
    if danger_right:
        pressed.add(left_key)

    dodging = danger_left or danger_right

    # ----------------------------------------
    # FAKEOUT (AI pauses)
    # ----------------------------------------
    if random.random() < FAKEOUT and not dodging:
        return InputState(set())

    # ----------------------------------------
    # CORNER ESCAPE / PRESSURE
    # ----------------------------------------
    left_corner = fighter.rect.left < 25
    right_corner = fighter.rect.right > WIDTH - 25
    opp_left_corner = opponent.rect.left < 35
    opp_right_corner = opponent.rect.right > WIDTH - 35
    opp_cornered = opp_left_corner or opp_right_corner

    # Escape if WE are cornered
    if not dodging:
        if left_corner:
            pressed.add(right_key)
            if fighter.on_ground and random.random() < 0.65:
                pressed.add(jump_key)
        elif right_corner:
            pressed.add(left_key)
            if fighter.on_ground and random.random() < 0.65:
                pressed.add(jump_key)

        # Pressure if OPPONENT is cornered
        elif opp_cornered:
            preferred = right_key if moving_right else left_key
            escape = left_key if moving_right else right_key

            if distance > 90:
                pressed.add(preferred)
            elif distance < 65:
                pressed.add(escape)

            # Even on lower difficulties, add a gentle forward bias so the AI
            # will actually contest players hiding in the corners instead of
            # pacing back and forth out of range.
            if random.random() < 0.25:
                pressed.add(preferred)
        else:
            # Normal spacing
            if distance > SPACING_HI:
                pressed.add(right_key if moving_right else left_key)
            elif distance < SPACING_LO:
                pressed.add(left_key if moving_right else right_key)
            else:
                if random.random() < SHUFFLE:
                    pressed.add(right_key if moving_right else left_key)
                elif random.random() < SHUFFLE:
                    pressed.add(left_key if moving_right else right_key)

    # ----------------------------------------
    # IMPOSSIBLE CORNER MODE
    # ----------------------------------------
    if diff in ["bigboy", "doumi gang"] and opp_cornered:
        pressed.add(right_key if moving_right else left_key)

        if random.random() < 0.35:
            pressed.add(right_key if moving_right else left_key)

        if opponent.vel_y < -3 and fighter.attack_cool == 0:
            pressed.add(fighter.melee_key)

        if opponent.state == "attack" and fighter.attack_cool == 0:
            pressed.add(fighter.melee_key)

        if fighter.attack_cool == 0:
            if random.random() < 0.70:
                pressed.add(fighter.melee_key)
            if fighter.proj_cool == 0 and random.random() < 0.20:
                pressed.add(fighter.proj_key)

        if random.random() < 0.30 and fighter.on_ground:
            pressed.add(jump_key)

        return InputState(pressed)

    # ----------------------------------------
    # ANTI AIR
    # ----------------------------------------
    if opponent.vel_y < -4 and distance < 140 and fighter.attack_cool == 0:
        if random.random() < ANTI_AIR:
            pressed.add(fighter.melee_key)

    # ----------------------------------------
    # WHIFF PUNISH
    # ----------------------------------------
    if WHIFF_PUNISH and opponent.state == "attack":
        if not fighter.rect.colliderect(opponent.rect):
            if distance < 130 and fighter.attack_cool == 0:
                pressed.add(fighter.melee_key)

    # Prevent the AI from walking off-screen. When a fighter is already flush
    # with a boundary, drop inputs that would push them further out of bounds
    # so spacing logic does not force constant left/right walking at the edges.
    # Preserve forward pressure when chasing an opponent in the corner so the
    # bot doesn't give up just before reaching melee range.
    if fighter.rect.left <= 0 and not moving_right:
        pressed.discard(left_key)
    if fighter.rect.right >= WIDTH and not moving_right:
        pressed.discard(right_key)

    # ----------------------------------------
    # COMBO SYSTEM
    # ----------------------------------------
    in_melee = distance < 85

    if in_melee and fighter.attack_cool == 0:
        roll = random.random()

        if fighter.combo_step == 0:
            if roll < MELEE:
                pressed.add(fighter.melee_key)
                fighter.combo_step = 1

        elif fighter.combo_step == 1:
            if roll < COMBO:
                pressed.add(fighter.melee_key)
                fighter.combo_step = 2
            else:
                fighter.combo_step = 0

        else:
            if roll < COMBO:
                pressed.add(fighter.melee_key)
            fighter.combo_step = 0

    if distance > 120:
        fighter.combo_step = 0

    # ----------------------------------------
    # BREAK OUT OF PASSIVITY
    # ----------------------------------------
    if pressed:
        fighter.idle_frames_since_action = 0
    else:
        fighter.idle_frames_since_action = min(240, fighter.idle_frames_since_action + 1)

    if not dodging and fighter.idle_frames_since_action > 12:
        pressed.add(right_key if moving_right else left_key)

    if not dodging and fighter.idle_frames_since_action > 24 and fighter.attack_cool == 0:
        if in_melee:
            pressed.add(fighter.melee_key)
        elif distance < 200 and fighter.proj_cool == 0:
            pressed.add(fighter.proj_key)

    # ----------------------------------------
    # RAW MELEE
    # ----------------------------------------
    if in_melee and fighter.attack_cool == 0:
        if random.random() < MELEE:
            pressed.add(fighter.melee_key)

    # PLAYER 3 KICK VARIANT (crouch + attack)
    if (
        fighter.character_key == "player3"
        and fighter.attack_cool == 0
        and fighter.crouch_key is not None
        and in_melee
    ):
        if random.random() < 0.35:
            pressed.add(fighter.crouch_key)
            pressed.add(fighter.melee_key)
    # ----------------------------------------
    # PROJECTILES
    # ----------------------------------------
    if fighter.proj_cool == 0 and fighter.attack_cool == 0 and not dodging:
        if distance > 140:
            if random.random() < THROW:
                pressed.add(fighter.proj_key)

        if CORNER_TRAP and opp_cornered and 130 < distance < 260:
            if random.random() < THROW * 0.8:
                pressed.add(fighter.proj_key)

        # Player 2's pencil cooldown is short; when piloted by the AI, keep
        # mid-range pressure up so human opponents can't idle on the far side of
        # the screen waiting for melee. This layer only applies when the AI is
        # actually controlling Player 2 to avoid skewing the other characters.
        if fighter.character_key == "player2" and 120 < distance < 210 and not opp_cornered:
            if random.random() < THROW * 0.75:
                pressed.add(fighter.proj_key)

    # ----------------------------------------
    # BERSERK BACKSTOP (never idle)
    # ----------------------------------------
    # The AI should always be closing distance or throwing hands. If no other
    # logic produced an input (common when both fighters are airborne or reset
    # to opposite corners), force a forward push and pick the most aggressive
    # attack available.
    if not pressed:
        preferred = right_key if moving_right else left_key
        pressed.add(preferred)

        if fighter.attack_cool == 0:
            if distance < 190 or fighter.proj_cool > 0:
                pressed.add(fighter.melee_key)
            elif fighter.proj_cool == 0:
                pressed.add(fighter.proj_key)
        elif fighter.proj_cool == 0 and distance > 160:
            pressed.add(fighter.proj_key)

        if not fighter.on_ground and random.random() < 0.35:
            pressed.add(jump_key)

    # ----------------------------------------------------------
    # ADVANCED DASH MIXUPS (bigboy + doumi gang only)
    # ----------------------------------------------------------
    sweaty_mode = diff in ["bigboy", "doumi gang"]
    can_dash = hasattr(fighter, "dash_time") and fighter.dash_time == 0

    if sweaty_mode:

        # -------------------------
        # 1. DASH FEINT
        # -------------------------
        if can_dash and 90 < distance < 240:
            if random.random() < 0.18:
                fighter.dash_dir = 1 if moving_right else -1
                fighter.dash_time = 3  # tiny microdash feint

        # -------------------------
        # 2. SHIMMY MIXUP 
        # dash in -> dash back -> punish
        # -------------------------
        if can_dash and distance < 120 and opponent.state != "attack":
            if random.random() < 0.14:
                # dash in
                fighter.dash_dir = 1 if moving_right else -1
                fighter.dash_time = 5

                # dash back
                if random.random() < 0.7:
                    fighter.dash_dir = -1 if moving_right else 1
                    fighter.dash_time = 5

        # -------------------------
        # 3. WAVEDASH (Tekken-style)
        # -------------------------
        if can_dash and fighter.on_ground:
            if random.random() < 0.10:
                # dash forward repeatedly
                for _ in range(random.randint(2, 4)):
                    fighter.dash_dir = 1 if moving_right else -1
                    fighter.dash_time = 5

        # -------------------------
        # 4. DASH → THROW MIXUP
        # -------------------------
        if can_dash and distance < 85:
            if random.random() < 0.25:
                fighter.dash_dir = 1 if moving_right else -1
                fighter.dash_time = 6

                if fighter.attack_cool == 0:
                    pressed.add(fighter.melee_key)  # throw in your game

        # -------------------------
        # 5. CROSS-UNDER DASH 
        # (under your jump arc)
        # -------------------------
        if can_dash and opponent.vel_y < -3 and distance < 110:
            if random.random() < 0.20:
                fighter.dash_dir = 1 if not moving_right else -1
                fighter.dash_time = 8

        # -------------------------
        # 6. MICRODASH → JUMP-IN
        # -------------------------
        if can_dash and distance < 160:
            if random.random() < 0.22:
                fighter.dash_dir = 1 if moving_right else -1
                fighter.dash_time = 4
                pressed.add(jump_key)

        # -------------------------
        # 7. BACKDASH → WHIFF PUNISH
        # -------------------------
        if can_dash and opponent.state == "attack":
            if random.random() < 0.28:
                fighter.dash_dir = -1 if moving_right else 1
                fighter.dash_time = 6

            if random.random() < 0.40:
                pressed.add(fighter.melee_key)

    committed_action = any(
        key in pressed
        for key in (
            fighter.melee_key,
            fighter.proj_key,
            jump_key,
        )
    ) or getattr(fighter, "dash_time", 0) > 0

    if committed_action:
        fighter.input_buffer = set(pressed)
        fighter.buffer_timer = random.randint(2, 4)
    else:
        fighter.input_buffer = set(pressed)
        fighter.buffer_timer = 0

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
character_card_font = load_font(["freesansbold", "arial"], 34, bold=True)
character_sub_font = load_font(["dejavusans", "arial"], 24)

CHARACTER_KEYS = list(CHARACTER_ROSTER.keys())
CARD_SIZE = (220, 260)
CARD_GAP = 30


def build_character_cards():
    cards = {}
    count = len(CHARACTER_KEYS)

    total_width = count * CARD_SIZE[0] + (count - 1) * CARD_GAP
    start_x = WIDTH // 2 - total_width // 2

    for i, key in enumerate(CHARACTER_KEYS):
        info = CHARACTER_ROSTER[key]
        rect = pygame.Rect(0, 0, *CARD_SIZE)
        rect.centerx = start_x + i * (CARD_SIZE[0] + CARD_GAP) + CARD_SIZE[0] // 2
        rect.centery = HEIGHT // 2 + 40

        preview = load_sprite(info["folder"], f"{info['prefix']}_idle1.png", flip=False)
        preview = pygame.transform.smoothscale(preview, (int(SPRITE_W * 1.6), int(SPRITE_H * 1.6)))

        cards[key] = {
            "rect": rect,
            "preview": preview,
            "label": info["label"],
            "color": info["card_color"],
        }

    return cards


CHARACTER_CARDS = build_character_cards()


def draw_assignment_badge(label, pos, color):
    badge = ui_font.render(label, True, BLACK)
    badge_rect = badge.get_rect(center=pos)
    pygame.draw.rect(screen, color, badge_rect.inflate(14, 10), border_radius=8)
    screen.blit(badge, badge_rect)


def character_select():
    active_slot = 1
    p1_choice = "player1"
    p2_choice = "player2"

    number_bindings = {getattr(pygame, f"K_{i+1}"): i for i in range(len(CHARACTER_KEYS))}

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    return None

                if e.key in (pygame.K_TAB, pygame.K_SPACE):
                    active_slot = 2 if active_slot == 1 else 1

                if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return p1_choice, p2_choice

                if e.key in number_bindings:
                    idx = number_bindings[e.key]
                    if idx < len(CHARACTER_KEYS):
                        selection = CHARACTER_KEYS[idx]
                        if active_slot == 1:
                            p1_choice = selection
                            active_slot = 2
                        else:
                            p2_choice = selection

            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for key, card in CHARACTER_CARDS.items():
                    if card["rect"].collidepoint(e.pos):
                        if active_slot == 1:
                            p1_choice = key
                            active_slot = 2
                        else:
                            p2_choice = key

        screen.blit(menu_bg, (0, 0))

        title = menu_font.render("Choose Your Fighters", True, WHITE)
        screen.blit(title, title.get_rect(center=(WIDTH // 2, 80)))

        subtitle = ui_font.render(
            "Click a card or press 1/2/3. TAB swaps who you're assigning.", True, WHITE
        )
        screen.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, 140)))

        confirm = controls_font.render(
            "ENTER: lock choices    ESC: back to menu", True, WHITE
        )
        screen.blit(confirm, confirm.get_rect(center=(WIDTH // 2, HEIGHT - 40)))

        active_note = button_font.render(f"Assigning Player {active_slot}", True, WHITE)
        screen.blit(active_note, active_note.get_rect(center=(WIDTH // 2, 200)))

        for key, card in CHARACTER_CARDS.items():
            rect = card["rect"]
            base = pygame.Color(*card["color"])
            pygame.draw.rect(screen, base, rect, border_radius=12)

            is_active_choice = (active_slot == 1 and key == p1_choice) or (
                active_slot == 2 and key == p2_choice
            )
            border_color = (255, 255, 255) if is_active_choice else (30, 30, 40)
            pygame.draw.rect(screen, border_color, rect, width=4, border_radius=12)

            preview_rect = card["preview"].get_rect(midtop=(rect.centerx, rect.y + 26))
            screen.blit(card["preview"], preview_rect)

            label = character_card_font.render(card["label"], True, BLACK)
            screen.blit(label, label.get_rect(center=(rect.centerx, rect.bottom - 70)))

            slot_hint = character_sub_font.render("Press {}".format(CHARACTER_KEYS.index(key) + 1), True, BLACK)
            screen.blit(slot_hint, slot_hint.get_rect(center=(rect.centerx, rect.bottom - 38)))

            badge_offset = 36
            if key == p1_choice:
                draw_assignment_badge("P1", (rect.centerx - badge_offset, rect.bottom - 16), (250, 250, 250))
            if key == p2_choice:
                draw_assignment_badge("P2", (rect.centerx + badge_offset, rect.bottom - 16), (250, 220, 120))

        pygame.display.flip()
        clock.tick(60)

menu_title = menu_font.render("Big Boy Simulator", True, WHITE)
start_prompt = timer_font.render(
    "Press ENTER or NUMPAD ENTER for two players", True, WHITE
)
single_p1_prompt = controls_font.render("Press 1 to play as Player 1 (Player 2 uses AI)", True, WHITE)
single_p2_prompt = controls_font.render("Press 2 to play as Player 2 (Player 1 uses AI)", True, WHITE)
options_prompt = controls_font.render("Press O to tweak rounds, timer, and AI", True, WHITE)
p1_controls = [
    controls_font.render("Player 1: Move A/D, Jump W, Crouch S", True, WHITE),
    controls_font.render("Melee: SPACE  |  Throw: Q  |  Block: Left Shift", True, WHITE),
] 
p2_controls = [
    controls_font.render("Player 2: Move ←/→, Jump ↑, Crouch ↓", True, WHITE),
    controls_font.render("Melee: ENTER  |  Throw: P  |  Block: Right Shift", True, WHITE)
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

            # DEBUG (Optional: remove later)
            if e.type == pygame.KEYDOWN:
                print("KEY PRESSED:", e.key)

            # -----------------------------------------
            # QUICK START: Press "6" or NUMPAD6
            # -----------------------------------------
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_6, pygame.K_KP6):
                    print("DOUMI GANG SHORTCUT ACTIVATED")
                    SETTINGS.ai_difficulty = "doumi gang"
                    return "p1"  # P1 vs AI

                # -----------------------------------------
                # NORMAL MENU OPTIONS
                # -----------------------------------------

                # Start 2-player match
                if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    return "versus"

                # P1 vs AI
                if e.key == pygame.K_1:
                    return "p1"

                # P2 vs AI
                if e.key == pygame.K_2:
                    return "p2"

                # Options menu
                if e.key == pygame.K_o:
                    options_menu()

        # -----------------------------------------
        # DRAW MENU
        # -----------------------------------------
        screen.blit(menu_bg, (0, 0))

        screen.blit(menu_title, title_pos)
        screen.blit(start_prompt, prompt_pos)
        screen.blit(single_p1_prompt, single_p1_pos)
        screen.blit(single_p2_prompt, single_p2_pos)
        screen.blit(options_prompt, options_pos)

        quick_text = controls_font.render(
            "Press 6 for P1 vs DOUMI GANG AI", True, WHITE
        )
        quick_pos = quick_text.get_rect(
            midtop=(WIDTH // 2, options_pos.bottom + 20)
        )
        screen.blit(quick_text, quick_pos)

        for line, pos in zip(p1_controls, p1_control_positions):
            screen.blit(line, pos)

        for line, pos in zip(p2_controls, p2_control_positions):
            screen.blit(line, pos)

        pygame.display.flip()
        clock.tick(60)

        # ---- DRAW MENU ----
        screen.blit(menu_bg, (0, 0))
        screen.blit(menu_title, title_pos)
        screen.blit(start_prompt, prompt_pos)
        screen.blit(single_p1_prompt, single_p1_pos)
        screen.blit(single_p2_prompt, single_p2_pos)
        screen.blit(options_prompt, options_pos)

        # Shortcut hint
        quick_text = controls_font.render(
            "Press 6 for P1 vs DOUMI GANG AI", True, WHITE
        )
        quick_pos = quick_text.get_rect(midtop=(WIDTH // 2, options_pos.bottom + 20))
        screen.blit(quick_text, quick_pos)

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
def show_round_message(title, subtitle=None, duration_ms=1400, fighters=None):
    """Overlay a simple, centered message for a short duration.

    When fighters are provided, keep drawing them (and advancing their win
    animations) underneath the banner so the victory pose is the last thing on
    screen before the game transitions to the next state.
    """

    fighters = fighters or []

    title_surf = render_pixel_text(title, WHITE, 4)
    title_rect = title_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 10))

    elapsed = 0
    while elapsed < duration_ms:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                sys.exit()

        screen.blit(bg, (0, 0))

        for fighter in fighters:
            if fighter.state == "win":
                fighter.animate(fighter.win_frames, fighter.win_frames_flipped, 12)
            fighter.draw(screen)

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

    # Ensure both fighters start a round facing each other (prevents intro pose bugs)
    p1.facing_left = p2.rect.centerx < p1.rect.centerx
    p2.facing_left = p1.rect.centerx < p2.rect.centerx

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
        p1.update(p1_inputs, pygame.K_a, pygame.K_d, pygame.K_w, pygame.K_s, pygame.K_LSHIFT, p2)
        p2.update(p2_inputs, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN, pygame.K_RSHIFT, p1)
        for fighter in (p1, p2):
            proj = fighter.spawn_projectile()
            if not proj:
                continue

            if isinstance(proj, Bottle):
                bottles.append(proj)
            else:
                projectiles.append(proj)

        # ---- UPDATE PROJECTILES ----
        def apply_projectile_damage(target, proj):
            damage = getattr(proj, "damage", 5)
            knock_dir = -1 if getattr(proj, "direction", 1) > 0 else 1
            target.take_hit(damage, knock_dir)

        for p in projectiles[:]:
            p.update()

            hit_target = None
            if p.rect.colliderect(p1.rect) and getattr(p, "owner", None) is not p1:
                hit_target = p1
            elif p.rect.colliderect(p2.rect) and getattr(p, "owner", None) is not p2:
                hit_target = p2

            if hit_target:
                apply_projectile_damage(hit_target, p)
                if hasattr(p, "on_hit"):
                    p.on_hit()
                if not getattr(p, "persist_on_hit", False):
                    projectiles.remove(p)
                continue

            if not getattr(p, "active", True):
                projectiles.remove(p)
        # ---- UPDATE BOTTLES ----
        for b in bottles[:]:
            prev_hit = b.hit
            b.update()

            # bottle shatter hit detection
            if not prev_hit and b.hit:
                apply_bottle_shatter_damage(b, (p1, p2))

            # remove bottle
            if b.dead:
                bottles.remove(b)
            elif b.x > WIDTH + 40 or b.x < -40:
                bottles.remove(b)

        # ---- GLOBAL PROJECTILE LIST (for AI dodge) ----
        global global_projectiles
        global_projectiles = projectiles + bottles
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

        choices = character_select()
        if choices is None:
            continue

        p1_choice, p2_choice = choices

        global HUD_FRAMES_P1, HUD_FRAMES_P2
        HUD_FRAMES_P1 = build_character_hud_frames(p1_choice, mirror=False)
        HUD_FRAMES_P2 = build_character_hud_frames(p2_choice, mirror=False)

        p1_ai = selection == "p2"
        p2_ai = selection == "p1"

        p1_score = 0
        p2_score = 0

        target_wins = SETTINGS.rounds_to_win
        match_aborted = False

        while p1_score < target_wins and p2_score < target_wins:
            p1, p2 = create_players(p1_choice, p2_choice)
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

            p1_label = CHARACTER_ROSTER.get(p1_choice, {}).get("label", "Player 1")
            p2_label = CHARACTER_ROSTER.get(p2_choice, {}).get("label", "Player 2")

            round_winner_text = (
                f"{p1_label.upper()} WINS!" if winner == 1 else f"{p2_label.upper()} WINS!"
            )
            if winner == 1:
                p1_score += 1
                p1.set_win()
            else:
                p2_score += 1
                p2.set_win()

            show_round_message(
                round_winner_text,
                "you win big boy negative aura",
                fighters=(p1, p2),
            )

        if match_aborted:
            continue

        champion_label = p1_label if p1_score > p2_score else p2_label
        champion_label = f"{champion_label.upper()} WINS!"

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












































