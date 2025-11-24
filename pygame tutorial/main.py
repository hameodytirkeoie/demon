import pygame
import sys
import os

pygame.init()

# --- Screen ---
WIDTH, HEIGHT = 800, 400
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
PIXEL_TIMER_BG = load_ui_image(os.path.join(assets_dir, "timer_bg.png"), (140, 48))


def render_pixel_text(text, color, scale=3):
    pixel_base = pygame.font.Font(None, 18)
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
    def __init__(self, x, y, direction):
        self.x = x
        self.y = y
        self.vx = 8 * direction
        self.vy = -10
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

# ----------------------------------------------------------
# FIGHTER CLASS
# ----------------------------------------------------------
class Fighter:
    def __init__(self, x, folder, idle, walk, attack, hit, win, flip=False,
                 melee_key=None, proj_key=None):

        self.x = x
        self.melee_key = melee_key
        self.proj = proj_key

        self.health = 100
        self.velocity = 5

        self.flip = flip
        self.folder = folder

        # Animations
        self.idle_frames   = [load_sprite(folder, f, flip) for f in idle]
        self.walk_frames   = [load_sprite(folder, f, flip) for f in walk]
        self.attack_frames = [load_sprite(folder, f, flip) for f in attack]
        self.hit_frames    = [load_sprite(folder, f, flip) for f in hit]
        self.win_frames    = [load_sprite(folder, f, flip) for f in win]

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
        self.hit_timer = 0
        self.win_timer = 0

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
        if self.win_timer > 0:
            self.animate(self.win_frames, 12)
            return

        if self.hit_timer > 0:
            self.hit_timer -= 1
            self.animate(self.hit_frames, 6)
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

        # attacks
        if self.attack_cool > 0:
            self.attack_cool -= 1
        if self.proj_cool > 0:
            self.proj_cool -= 1

        if keys[self.melee_key] and self.attack_cool == 0:
            self.attack_cool = 18
            self.state = "attack"
            if self.rect.colliderect(opponent.rect):
                opponent.health -= 10
                opponent.set_hit()

        elif self.proj and keys[self.proj] and self.attack_cool == 0 and self.proj_cool == 0:
            self.attack_cool = 20
            self.proj_cool = 60  # ~1 second cooldown at 60 FPS
            self.state = "attack"
            self.just_shot = True
        else:
            if moving:
                self.state = "walk"
            else:
                self.state = "idle"

        # animations
        if self.state == "idle":
            self.animate(self.idle_frames, self.idle_speed)
        elif self.state == "walk":
            self.animate(self.walk_frames, 8)
        elif self.state == "attack":
            self.animate(self.attack_frames, 6)

    def animate(self, frames, speed):
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
        650, BASE_P2,
        p2_idle, p2_walk, p2_attack, p2_hit, p2_win,
        flip=False,
        melee_key=pygame.K_RETURN,
        proj_key=pygame.K_p
    )

    return p1, p2


# ----------------------------------------------------------
# DRAW UI (HEALTH + TIMER)
# ----------------------------------------------------------
def draw_ui(p1, p2, time_left, countdown_text=None):
    bar_w = 320
    bar_h = 22

    def draw_bar(x, y, ratio, label):
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

        label_surface = ui_font.render(label, True, WHITE)
        label_pos = label_surface.get_rect(midleft=(panel_rect.x + 10, panel_rect.centery))
        screen.blit(label_surface, label_pos)

    draw_bar(18, 18, p1.health / 100, f"P1 {p1.health:03d}")
    draw_bar(WIDTH - bar_w - 18, 18, p2.health / 100, f"P2 {p2.health:03d}")

    # Timer panel
    timer_rect = pygame.Rect(WIDTH // 2 - 70, 12, 140, 48)
    timer_shadow = timer_rect.move(3, 3)
    pygame.draw.rect(screen, (0, 0, 0), timer_shadow, border_radius=10)

    if TIMER_PANEL_IMG:
        screen.blit(TIMER_PANEL_IMG, timer_rect.topleft)
    else:
        pygame.draw.rect(screen, (24, 32, 60), timer_rect, border_radius=10)
        pygame.draw.rect(screen, (110, 140, 200), timer_rect, width=2, border_radius=10)

    if PIXEL_TIMER_BG:
        screen.blit(PIXEL_TIMER_BG, timer_rect.topleft)

    label = ui_font.render("TIME", True, WHITE)
    label_pos = label.get_rect(midtop=(timer_rect.centerx, timer_rect.y + 4))
    screen.blit(label, label_pos)

    timer_label = countdown_text if countdown_text is not None else str(time_left)
    timer_surface = render_pixel_text(timer_label.rjust(2, " "), WHITE, 3)
    text_pos = timer_surface.get_rect(center=(timer_rect.centerx, timer_rect.y + timer_rect.h - 20))
    screen.blit(timer_surface, text_pos)

# ----------------------------------------------------------
# MAIN MENU
# ----------------------------------------------------------
# Pre-render menu text once to keep consistent sizing and avoid rebuilding
# surfaces inside the loop.
menu_font = pygame.font.Font(None, 80)
timer_font = pygame.font.Font(None, 60)
controls_font = pygame.font.Font(None, 36)
ui_font = pygame.font.Font(None, 28)

menu_title = menu_font.render("Big Boy Simulator", True, WHITE)
start_prompt = timer_font.render("Press ENTER to start", True, WHITE)
p1_controls = [
    controls_font.render("Player 1: Move A/D, Jump W", True, WHITE),
    controls_font.render("Melee: SPACE  |  Throw: Q", True, WHITE)
]
p2_controls = [
    controls_font.render("Player 2: Move ←/→, Jump ↑", True, WHITE),
    controls_font.render("Melee: ENTER  |  Throw: P", True, WHITE)
]

title_pos = menu_title.get_rect(center=(WIDTH // 2, 80))
prompt_pos = start_prompt.get_rect(center=(WIDTH // 2, 260))

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

            if e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN:
                return

        screen.blit(menu_bg, (0, 0))

        screen.blit(menu_title, title_pos)
        screen.blit(start_prompt, prompt_pos)
        for line, pos in zip(p1_controls, p1_control_positions):
            screen.blit(line, pos)

        for line, pos in zip(p2_controls, p2_control_positions):
            screen.blit(line, pos)

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
    draw_ui(p1, p2, starting_time, countdown_text=None)

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


def show_round_message(title, subtitle=None, duration_ms=1400):
    """Overlay a simple, centered message for a short duration."""
def play_round(p1, p2):
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
def play_round(p1, p2):
    time_left = 60
    tick = 0
    projectiles = []
    bottles = []

    run_round_countdown(p1, p2, time_left)

    while True:
        screen.blit(bg, (0, 0))
        keys = pygame.key.get_pressed()

        for e in pygame.event.get():
            if e.type == pygame.QUIT: sys.exit()

        # update
        p1.update(keys, pygame.K_a, pygame.K_d, pygame.K_w, p2)
        p2.update(keys, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, p1)

        if p1.just_shot:
            bottles.append(Bottle(p1.rect.centerx, p1.rect.y, 1))

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
    main_menu()

    p1_score = 0
    p2_score = 0

    while p1_score < 2 and p2_score < 2:
        p1, p2 = create_players()
        winner = play_round(p1, p2)

        if winner == 1:
            p1_score += 1
            p1.set_win()
        else:
            p2_score += 1
            p2.set_win()

        pygame.time.delay(1500)

    # FINAL SCREEN
    screen.fill(BLACK)
    txt = menu_font.render(
        "PLAYER 1 WINS!" if p1_score > p2_score else "PLAYER 2 WINS!",
        True, WHITE
    )
    screen.blit(txt, (WIDTH//2 - txt.get_width()//2, HEIGHT//2 - 50))
    pygame.display.flip()
    pygame.time.delay(3000)


# ----------------------------------------------------------
# START GAME
# ----------------------------------------------------------
if __name__ == "__main__":
    game_loop()
    pygame.quit()
    sys.exit()











