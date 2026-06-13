"""
FURY ROAD: BOSS RUSH
Mad Max-Inspired Post-Apocalyptic Top-Down Shooter
Built with Python Arcade 3.x

You are {player_name} — lone survivor on the Fury Road.
Defeat the War Boys and their chrome-worshipping warlords!
"""

import arcade
import math
import random
import time
import numpy as np
import wave
import io
import tempfile
import os
import json

# ── Sound Engine ───────────────────────────────────────────────────────────
_sound_cache = {}
_tmp_files   = []
SR = 22050   # sample rate

def _make_wav_bytes(samples: np.ndarray) -> bytes:
    samples = np.clip(samples, -1.0, 1.0)
    pcm = (samples * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()

def _write_tmp(data: bytes) -> str:
    f = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    f.write(data); f.close()
    _tmp_files.append(f.name)
    return f.name

def _env(t, attack=0.005, decay=0.05, sustain=0.6, release=0.1):
    n = len(t); dur = t[-1]
    env = np.ones(n)
    a  = int(attack  / dur * n)
    d  = int(decay   / dur * n)
    r  = int(release / dur * n)
    if a: env[:a]        = np.linspace(0, 1, a)
    if d: env[a:a+d]     = np.linspace(1, sustain, d)
    if r: env[max(0,n-r):] = np.linspace(sustain, 0, min(r, n))
    return env

def _synth_shoot(vol=0.35):
    dur = 0.18; t = np.linspace(0, dur, int(SR*dur))
    freq = np.linspace(900, 300, len(t))
    s  = np.sign(np.sin(2*np.pi * np.cumsum(freq)/SR))  # square wave chirp
    s += np.random.uniform(-0.15, 0.15, len(t))          # grit
    return s * _env(t, .002, .04, .3, .12) * vol

def _synth_hit(vol=0.5):
    dur = 0.14; t = np.linspace(0, dur, int(SR*dur))
    noise = np.random.uniform(-1, 1, len(t))
    tone  = np.sin(2*np.pi*180*t) * 0.5
    s = (noise * 0.7 + tone * 0.3)
    return s * _env(t, .001, .03, .2, .08) * vol

def _synth_explosion(vol=0.7):
    dur = 0.55; t = np.linspace(0, dur, int(SR*dur))
    noise = np.random.uniform(-1, 1, len(t))
    rumble = np.sin(2*np.pi*55*t) + np.sin(2*np.pi*80*t)*0.5
    s = noise * 0.6 + rumble * 0.4
    return s * _env(t, .001, .08, .4, .35) * vol

def _synth_dodge(vol=0.4):
    dur = 0.15; t = np.linspace(0, dur, int(SR*dur))
    freq = np.linspace(300, 1200, len(t))
    s  = np.sin(2*np.pi * np.cumsum(freq)/SR)
    s += np.random.uniform(-0.1, 0.1, len(t))
    return s * _env(t, .005, .05, .5, .08) * vol

def _synth_player_hurt(vol=0.55):
    dur = 0.28; t = np.linspace(0, dur, int(SR*dur))
    freq = np.linspace(220, 100, len(t))
    s  = np.sign(np.sin(2*np.pi * np.cumsum(freq)/SR)) * 0.6
    s += np.random.uniform(-0.3, 0.3, len(t)) * 0.4
    return s * _env(t, .001, .06, .5, .18) * vol

def _synth_boss_phase2(vol=0.8):
    dur = 0.7; t = np.linspace(0, dur, int(SR*dur))
    s  = np.sin(2*np.pi*110*t) + np.sin(2*np.pi*165*t)*0.5
    s += np.random.uniform(-0.2, 0.2, len(t))
    freq2 = np.linspace(60, 200, len(t))
    s += np.sin(2*np.pi * np.cumsum(freq2)/SR) * 0.4
    return s * _env(t, .01, .1, .6, .3) * vol

def _synth_boss_die(vol=0.9):
    dur = 1.1; t = np.linspace(0, dur, int(SR*dur))
    noise = np.random.uniform(-1, 1, len(t))
    rumble = (np.sin(2*np.pi*40*t) + np.sin(2*np.pi*70*t)*0.6
              + np.sin(2*np.pi*110*t)*0.3)
    s = noise * 0.5 + rumble * 0.5
    return s * _env(t, .001, .15, .6, .45) * vol

def _synth_menu_drone(vol=0.18):
    dur = 2.0; t = np.linspace(0, dur, int(SR*dur))
    s  = np.sin(2*np.pi*55*t)
    s += np.sin(2*np.pi*82*t) * 0.5
    s += np.sin(2*np.pi*110*t) * 0.25
    s += np.random.uniform(-0.05, 0.05, len(t))
    return s * vol

def _synth_shotgun(vol=0.55):
    dur = 0.22; t = np.linspace(0, dur, int(SR*dur))
    noise = np.random.uniform(-1, 1, len(t))
    body  = np.sin(2*np.pi*120*t) * 0.4
    s = noise * 0.7 + body * 0.3
    return s * _env(t, .001, .04, .2, .15) * vol

def _synth_flame(vol=0.3):
    dur = 0.12; t = np.linspace(0, dur, int(SR*dur))
    noise = np.random.uniform(-1, 1, len(t))
    crackle = np.sin(2*np.pi*200*t + np.random.uniform(0,1,len(t))*8) * 0.3
    s = noise * 0.6 + crackle
    return s * _env(t, .001, .02, .5, .06) * vol

def _synth_sniper(vol=0.7):
    dur = 0.28; t = np.linspace(0, dur, int(SR*dur))
    crack = np.sign(np.sin(2*np.pi * np.linspace(1200, 200, len(t)) * t)) * 0.5
    noise = np.random.uniform(-0.3, 0.3, len(t))
    s = crack * 0.7 + noise * 0.3
    return s * _env(t, .001, .02, .15, .2) * vol


    if name not in _sound_cache:
        try:
            data = _make_wav_bytes(synth_fn())
            path = _write_tmp(data)
            _sound_cache[name] = arcade.load_sound(path)
        except Exception:
            _sound_cache[name] = None
    return _sound_cache[name]

def _load(name, synth_fn):
    if name not in _sound_cache:
        try:
            data = _make_wav_bytes(synth_fn())
            path = _write_tmp(data)
            _sound_cache[name] = arcade.load_sound(path)
        except Exception:
            _sound_cache[name] = None
    return _sound_cache[name]

def play_sfx(name, synth_fn, volume=1.0):
    snd = _load(name, synth_fn)
    if snd:
        try: arcade.play_sound(snd, volume=volume)
        except Exception: pass

def cleanup_sounds():
    for p in _tmp_files:
        try: os.unlink(p)
        except Exception: pass


SCREEN_W, SCREEN_H = 1000, 700
TITLE = "FURY ROAD: BOSS RUSH"
FPS   = 60

# Mad Max color palette — sand, rust, chrome, blood orange
C_BG         = (22, 16, 8)
C_SAND       = (180, 148, 90)
C_SAND_DARK  = (120, 95, 55)
C_RUST       = (160, 70, 25)
C_CHROME     = (200, 200, 195)
C_BLOOD      = (190, 40, 25)
C_FIRE       = (240, 130, 20)
C_FIRE2      = (255, 200, 50)
C_OIL        = (30, 25, 18)
C_SKY        = (200, 160, 80)   # dust-storm sky
C_DARK       = (18, 14, 8)
C_SMOKE      = (90, 80, 65)
C_TOXIC      = (100, 170, 40)
C_WHITE      = (235, 225, 200)

PLAYER_SPEED  = 230
BULLET_SPEED  = 540
PLAYER_MAX_HP = 100
FIRE_COOLDOWN = 0.16

# ── Weapon Definitions ─────────────────────────────────────────────────────
WEAPONS = [
    {
        'name':    'REVOLVER',
        'key':     '1',
        'color':   C_FIRE,
        'trail':   None,   # filled below after C_FIRE2 defined
        'damage':  10,
        'speed':   540,
        'cd':      0.16,
        'size':    5,
        'count':   1,
        'spread':  0,
        'range':   9999,
        'icon':    '🔫',
        'sfx':     'shoot',
    },
    {
        'name':    'SHOTGUN',
        'key':     '2',
        'color':   None,   # C_SAND filled below
        'trail':   None,
        'damage':  6,
        'speed':   400,
        'cd':      0.55,
        'size':    4,
        'count':   5,
        'spread':  18,
        'range':   9999,
        'icon':    '💥',
        'sfx':     'shotgun',
    },
    {
        'name':    'FLAMETHROWER',
        'key':     '3',
        'color':   None,   # C_FIRE filled below
        'trail':   None,
        'damage':  4,
        'speed':   260,
        'cd':      0.06,
        'size':    7,
        'count':   1,
        'spread':  12,
        'range':   300,
        'icon':    '🔥',
        'sfx':     'flame',
    },
    {
        'name':    'SNIPER',
        'key':     '4',
        'color':   None,   # C_CHROME filled below
        'trail':   None,
        'damage':  45,
        'speed':   900,
        'cd':      1.0,
        'size':    3,
        'count':   1,
        'spread':  0,
        'range':   9999,
        'pierce':  True,
        'icon':    '🎯',
        'sfx':     'sniper',
    },
]

def _init_weapon_colors():
    WEAPONS[0]['trail']  = C_FIRE2
    WEAPONS[1]['color']  = C_SAND
    WEAPONS[1]['trail']  = C_SAND_DARK
    WEAPONS[2]['color']  = C_FIRE
    WEAPONS[2]['trail']  = C_RUST
    WEAPONS[3]['color']  = C_CHROME
    WEAPONS[3]['trail']  = (160, 220, 255)


def angle_to(x1, y1, x2, y2):
    return math.degrees(math.atan2(y2 - y1, x2 - x1))

def dist(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)

def lerp(a, b, t):
    return a + (b - a) * t

# ── Particle ───────────────────────────────────────────────────────────────
class Particle:
    def __init__(self, x, y, vx, vy, color, life=0.6, size=4):
        self.x, self.y   = x, y
        self.vx, self.vy = vx, vy
        self.color       = color
        self.life        = life
        self.max_life    = life
        self.size        = size

    def update(self, dt):
        self.x  += self.vx * dt
        self.y  += self.vy * dt
        self.vx *= 0.90
        self.vy *= 0.90
        self.life -= dt
        return self.life > 0

    def draw(self):
        a = self.life / self.max_life
        s = max(1, self.size * a)
        r, g, b = self.color
        arcade.draw_circle_filled(self.x, self.y, s,
                                  (int(r), int(g), int(b), int(210 * a)))

def spawn_particles(particles, x, y, color, count=12,
                    speed=150, size=5, life=0.6):
    for _ in range(count):
        ang = random.uniform(0, 2 * math.pi)
        spd = random.uniform(30, speed)
        particles.append(Particle(x, y,
                                  math.cos(ang) * spd,
                                  math.sin(ang) * spd,
                                  color,
                                  life + random.uniform(-0.1, 0.1),
                                  size))

def spawn_fire(particles, x, y, count=8):
    for _ in range(count):
        ang = random.uniform(math.pi * 0.3, math.pi * 0.7)  # mostly upward
        spd = random.uniform(40, 160)
        col = random.choice([C_FIRE, C_FIRE2, C_RUST])
        particles.append(Particle(x, y,
                                  math.cos(ang) * spd + random.uniform(-20, 20),
                                  math.sin(ang) * spd,
                                  col, random.uniform(0.3, 0.8),
                                  random.uniform(3, 8)))

def spawn_smoke(particles, x, y, count=5):
    for _ in range(count):
        particles.append(Particle(x, y,
                                  random.uniform(-30, 30),
                                  random.uniform(20, 80),
                                  C_SMOKE,
                                  random.uniform(0.5, 1.2),
                                  random.uniform(6, 14)))

# ── Bullet ─────────────────────────────────────────────────────────────────
class Bullet:
    def __init__(self, x, y, angle_deg, speed, color,
                 owner="player", damage=10, size=5, trail_col=None):
        self.x, self.y = x, y
        rad = math.radians(angle_deg)
        self.vx        = math.cos(rad) * speed
        self.vy        = math.sin(rad) * speed
        self.color     = color
        self.owner     = owner
        self.damage    = damage
        self.size      = size
        self.alive     = True
        self.trail     = []
        self.trail_col = trail_col or color
        self.pierce    = False
        self.max_range = 9999
        self.traveled  = 0.0

    def update(self, dt):
        self.trail.append((self.x, self.y, 0.12))
        self.trail = [(tx, ty, tl - dt) for tx, ty, tl in self.trail if tl - dt > 0]
        spd = math.hypot(self.vx, self.vy)
        self.traveled += spd * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        if not (0 < self.x < SCREEN_W and 0 < self.y < SCREEN_H):
            self.alive = False
        if self.traveled > self.max_range:
            self.alive = False

    def draw(self):
        for tx, ty, tl in self.trail:
            a = tl / 0.12
            r, g, b = self.trail_col
            arcade.draw_circle_filled(tx, ty, self.size * a * 0.7,
                                      (r, g, b, int(120 * a)))
        r, g, b = self.color
        arcade.draw_circle_filled(self.x, self.y, self.size + 3, (r, g, b, 50))
        arcade.draw_circle_filled(self.x, self.y, self.size, (r, g, b, 230))

# ── Dust Cloud (background effect) ────────────────────────────────────────
class DustCloud:
    def __init__(self):
        self.reset()

    def reset(self):
        self.x     = random.randint(-80, SCREEN_W + 80)
        self.y     = random.randint(0, SCREEN_H)
        self.r     = random.uniform(30, 80)
        self.vx    = random.uniform(-20, -60)
        self.alpha = random.randint(20, 55)

    def update(self, dt):
        self.x += self.vx * dt
        if self.x < -100:
            self.reset()
            self.x = SCREEN_W + 100

    def draw(self):
        r, g, b = C_SAND
        arcade.draw_circle_filled(self.x, self.y, self.r, (r, g, b, self.alpha))

# ── Player (MAX) ───────────────────────────────────────────────────────────
class Player:
    def __init__(self):
        self.x          = SCREEN_W // 2
        self.y          = 100
        self.hp         = PLAYER_MAX_HP
        self.max_hp     = PLAYER_MAX_HP
        self.radius     = 17
        self.fire_timer = 0
        self.invincible = 0
        self.angle      = 90
        self.trail      = []
        self.trail_timer = 0
        self.exhaust_timer = 0
        self.dodge_cd      = 0.0   # cooldown remaining
        self.dodge_dur     = 0.0   # active dodge remaining
        self.dodge_vx      = 0.0
        self.dodge_vy      = 0.0
        self.DODGE_SPEED   = 620
        self.DODGE_TIME    = 0.18
        self.DODGE_CD      = 1.1
        self.last_dx       = 0
        self.last_dy       = 1    # default dodge direction: up
        self.weapon_idx    = 0    # current weapon index into WEAPONS

    def update(self, dt, keys, mouse_x, mouse_y, particles):
        dx = dy = 0
        if keys.get(arcade.key.W) or keys.get(arcade.key.UP):    dy += 1
        if keys.get(arcade.key.S) or keys.get(arcade.key.DOWN):  dy -= 1
        if keys.get(arcade.key.A) or keys.get(arcade.key.LEFT):  dx -= 1
        if keys.get(arcade.key.D) or keys.get(arcade.key.RIGHT): dx += 1
        if dx and dy:
            dx *= 0.7071; dy *= 0.7071

        # remember last movement direction for dodge
        if dx or dy:
            self.last_dx = dx
            self.last_dy = dy

        self.dodge_cd  = max(0, self.dodge_cd  - dt)
        self.dodge_dur = max(0, self.dodge_dur - dt)

        if self.dodge_dur > 0:
            # during dodge — fast movement, invincible
            self.invincible = max(self.invincible, self.dodge_dur)
            self.x = max(self.radius, min(SCREEN_W - self.radius,
                                          self.x + self.dodge_vx * dt))
            self.y = max(self.radius, min(SCREEN_H - self.radius,
                                          self.y + self.dodge_vy * dt))
            # afterimage dust burst
            if random.random() < 0.6:
                spawn_smoke(particles, self.x, self.y, 2)
                spawn_particles(particles, self.x, self.y,
                                C_SAND_DARK, 3, 80, 3, 0.2)
        else:
            moving = bool(dx or dy)
            self.x = max(self.radius, min(SCREEN_W - self.radius,
                                          self.x + dx * PLAYER_SPEED * dt))
            self.y = max(self.radius, min(SCREEN_H - self.radius,
                                          self.y + dy * PLAYER_SPEED * dt))
            # dust trail when moving
            self.trail_timer -= dt
            if self.trail_timer <= 0 and moving:
                self.trail.append((self.x, self.y, 0.3))
                self.trail_timer = 0.06
                if random.random() < 0.4:
                    spawn_smoke(particles, self.x, self.y, 1)

        self.angle      = angle_to(self.x, self.y, mouse_x, mouse_y)
        self.fire_timer = max(0, self.fire_timer - dt)
        self.invincible = max(0, self.invincible - dt)
        self.trail = [(tx, ty, tl - dt) for tx, ty, tl in self.trail if tl - dt > 0]

    def try_dodge(self, particles):
        if self.dodge_cd > 0 or self.dodge_dur > 0:
            return False
        self.dodge_dur = self.DODGE_TIME
        self.dodge_cd  = self.DODGE_CD
        mag = math.hypot(self.last_dx, self.last_dy) or 1
        self.dodge_vx  = (self.last_dx / mag) * self.DODGE_SPEED
        self.dodge_vy  = (self.last_dy / mag) * self.DODGE_SPEED
        spawn_particles(particles, self.x, self.y, C_CHROME, 10, 180, 4, 0.35)
        play_sfx('dodge', _synth_dodge, 0.6)
        return True

    def try_shoot(self, bullets, particles=None):
        if self.fire_timer <= 0:
            w = WEAPONS[self.weapon_idx]
            col   = w['color'] or C_FIRE
            trail = w['trail'] or col
            for i in range(w['count']):
                spread = random.uniform(-w['spread'], w['spread'])
                b = Bullet(self.x, self.y, self.angle + spread,
                           w['speed'], col, "player",
                           w['damage'], w['size'], trail_col=trail)
                b.pierce = w.get('pierce', False)
                b.max_range = w['range']
                b.traveled  = 0.0
                bullets.append(b)
            self.fire_timer = w['cd']
            # weapon-specific particles
            if self.weapon_idx == 2 and particles:   # flamethrower
                rad = math.radians(self.angle + random.uniform(-10,10))
                fx  = self.x + math.cos(rad) * (self.radius + 8)
                fy  = self.y + math.sin(rad) * (self.radius + 8)
                particles.append(Particle(fx, fy,
                    math.cos(rad)*random.uniform(40,100),
                    math.sin(rad)*random.uniform(40,100),
                    random.choice([C_FIRE, C_FIRE2, C_RUST]),
                    random.uniform(0.15, 0.4), random.uniform(5, 10)))
            sfx_map = {'shoot': _synth_shoot, 'shotgun': _synth_shotgun,
                       'flame': _synth_flame, 'sniper': _synth_sniper}
            sfx_vol = [0.6, 0.65, 0.3, 0.85]
            play_sfx(w['sfx'], sfx_map[w['sfx']], sfx_vol[self.weapon_idx])
            return True
        return False

    def take_damage(self, dmg):
        if self.invincible > 0:
            return
        self.hp        -= dmg
        self.invincible = 0.55
        play_sfx('player_hurt', _synth_player_hurt, 0.7)

    def draw(self):
        # dust trail
        for tx, ty, tl in self.trail:
            a = tl / 0.3
            arcade.draw_circle_filled(tx, ty, 8 * a,
                                      (*C_SAND_DARK, int(60 * a)))

        flash = self.invincible > 0 and int(time.time() * 18) % 2 == 0

        # shadow
        arcade.draw_ellipse_filled(self.x + 3, self.y - 4,
                                   self.radius * 2.2, self.radius * 1.0,
                                   (0, 0, 0, 70))
        # body — war rig survivor silhouette
        col = C_WHITE if flash else C_CHROME
        arcade.draw_circle_filled(self.x, self.y, self.radius, C_OIL)
        arcade.draw_circle_outline(self.x, self.y, self.radius, col, 2)
        # coat detail
        arcade.draw_arc_filled(self.x, self.y - 4,
                               self.radius * 1.4, self.radius * 0.8,
                               C_RUST, 200, 340)
        # gun arm
        bx = self.x + math.cos(math.radians(self.angle)) * (self.radius + 12)
        by = self.y + math.sin(math.radians(self.angle)) * (self.radius + 12)
        arcade.draw_line(self.x, self.y, bx, by, C_CHROME, 5)
        arcade.draw_circle_filled(bx, by, 4, C_FIRE)
        # eye
        ex = self.x + math.cos(math.radians(self.angle)) * 9
        ey = self.y + math.sin(math.radians(self.angle)) * 9
        arcade.draw_circle_filled(ex, ey, 3, C_FIRE)

# ── Base Boss ──────────────────────────────────────────────────────────────
class Boss:
    name              = "???"
    subtitle          = ""
    max_hp            = 500
    color             = C_RUST
    accent            = C_CHROME
    radius            = 52
    phase_threshold   = 0.45

    def __init__(self):
        self.x           = SCREEN_W // 2
        self.y           = SCREEN_H - 160
        self.hp          = self.max_hp
        self.phase       = 1
        self.timer       = 0
        self.alive       = True
        self.intro_timer = 2.2
        self.hit_flash   = 0
        self.angle       = 0

    @property
    def hp_ratio(self):
        return max(0, self.hp / self.max_hp)

    def take_damage(self, dmg, particles):
        self.hp       -= dmg
        self.hit_flash = 0.14
        spawn_particles(particles, self.x, self.y, self.color, 5, 100, 4, 0.35)
        spawn_smoke(particles, self.x, self.y, 2)
        play_sfx('hit', _synth_hit, 0.5)
        if self.hp <= 0:
            self.alive = False
            spawn_fire(particles, self.x, self.y, 25)
            spawn_particles(particles, self.x, self.y, self.accent, 30, 280, 9, 1.4)
            play_sfx('boss_die', _synth_boss_die, 1.0)
        elif self.hp_ratio <= self.phase_threshold and self.phase == 1:
            self.phase = 2
            self.on_phase2()
            spawn_fire(particles, self.x, self.y, 15)
            play_sfx('phase2', _synth_boss_phase2, 0.9)

    def on_phase2(self): pass

    def update(self, dt, bullets, player, particles):
        if self.intro_timer > 0:
            self.intro_timer -= dt
            return
        self.timer    += dt
        self.hit_flash = max(0, self.hit_flash - dt)
        self.angle     = (self.angle + 55 * dt) % 360
        self._update(dt, bullets, player, particles)

    def _update(self, dt, bullets, player, particles): pass

    def _shoot_at(self, bullets, tx, ty, speed, color, damage,
                  size=6, spread=0, trail=None):
        a = angle_to(self.x, self.y, tx, ty) + random.uniform(-spread, spread)
        bullets.append(Bullet(self.x, self.y, a, speed, color, "boss",
                               damage, size, trail_col=trail or color))

    def _shoot_ring(self, bullets, count, speed, color, damage,
                    size=6, offset=0, trail=None):
        for i in range(count):
            a = (360 / count) * i + offset
            bullets.append(Bullet(self.x, self.y, a, speed, color, "boss",
                                   damage, size, trail_col=trail or color))

    def draw(self):
        flash = self.hit_flash > 0
        col   = C_WHITE if flash else self.color

        # shadow
        arcade.draw_ellipse_filled(self.x + 5, self.y - 5,
                                   self.radius * 2.4, self.radius * 1.2,
                                   (0, 0, 0, 80))
        arcade.draw_circle_filled(self.x, self.y, self.radius, C_OIL)
        arcade.draw_circle_outline(self.x, self.y, self.radius, col, 3)
        self._draw_details()

        # intro name banner
        if self.intro_timer > 0:
            a   = min(1.0, 2.2 - self.intro_timer)
            alp = int(a * 255)
            arcade.draw_text(self.name,
                             self.x, self.y + self.radius + 22,
                             (*self.accent, alp), 22,
                             anchor_x="center", font_name="Arial Black")
            arcade.draw_text(self.subtitle,
                             self.x, self.y + self.radius + 2,
                             (*C_SAND, alp), 13, anchor_x="center")

    def _draw_details(self): pass

# ── Boss 1: IMMORTAN JOE'S ENFORCER ───────────────────────────────────────
class BossImmortan(Boss):
    name     = "IMMORTAN'S ENFORCER"
    subtitle = "\"WITNESS ME, BROTHERS!\""
    max_hp   = 480
    color    = C_CHROME
    accent   = C_FIRE
    radius   = 54
    phase_threshold = 0.42

    def __init__(self):
        super().__init__()
        self.shot_timer   = 0
        self.shot_cd      = 1.1
        self.charge_timer = 0
        self.charge_cd    = 3.2
        self.charging     = False
        self.charge_vx = self.charge_vy = 0
        self.charge_dur   = 0
        self.warboy_spawn = 4.0
        self.warboy_timer = 0
        self.spikes       = [{'a': i * 45, 'l': 18} for i in range(8)]

    def on_phase2(self):
        self.shot_cd  = 0.6
        self.charge_cd = 1.8

    def _update(self, dt, bullets, player, particles):
        # spike animation
        for s in self.spikes:
            s['l'] = 18 + math.sin(self.timer * 4 + s['a'] * 0.05) * 6

        # move — patrol horizontally
        tx = SCREEN_W // 2 + math.sin(self.timer * 0.7) * 260
        ty = SCREEN_H - 170 + math.cos(self.timer * 0.4) * 50
        if not self.charging:
            self.x = lerp(self.x, tx, dt * 0.9)
            self.y = lerp(self.y, ty, dt * 0.9)

        # shotgun blast
        self.shot_timer += dt
        if self.shot_timer >= self.shot_cd:
            self.shot_timer = 0
            if self.phase == 1:
                for _ in range(3):
                    self._shoot_at(bullets, player.x, player.y, 230,
                                   C_FIRE, 11, 7, 18, trail=C_FIRE2)
            else:
                for _ in range(5):
                    self._shoot_at(bullets, player.x, player.y, 260,
                                   C_FIRE, 12, 7, 25, trail=C_FIRE2)
                # chrome spray ring
                self._shoot_ring(bullets, 6, 160, C_CHROME, 7, 5,
                                  self.timer * 15)

        # charge ram
        self.charge_timer += dt
        if self.charge_timer >= self.charge_cd and not self.charging:
            self.charge_timer = 0
            self.charging     = True
            self.charge_dur   = 0
            a   = angle_to(self.x, self.y, player.x, player.y)
            spd = 460
            self.charge_vx = math.cos(math.radians(a)) * spd
            self.charge_vy = math.sin(math.radians(a)) * spd
            spawn_fire(particles, self.x, self.y, 8)

        if self.charging:
            self.x        += self.charge_vx * dt
            self.y        += self.charge_vy * dt
            self.charge_dur += dt
            spawn_fire(particles, self.x, self.y, 2)
            if self.x < self.radius or self.x > SCREEN_W - self.radius:
                self.charge_vx *= -1
            if self.y < self.radius or self.y > SCREEN_H - self.radius:
                self.charge_vy *= -1
            if self.charge_dur > 0.65:
                self.charging = False

    def _draw_details(self):
        # chrome spikes
        for s in self.spikes:
            a  = math.radians(self.angle + s['a'])
            sx = self.x + math.cos(a) * (self.radius + s['l'])
            sy = self.y + math.sin(a) * (self.radius + s['l'])
            arcade.draw_line(self.x + math.cos(a) * self.radius,
                             self.y + math.sin(a) * self.radius,
                             sx, sy, self.color, 3)
            arcade.draw_circle_filled(sx, sy, 5, self.accent)
        # breathing mask
        arcade.draw_rectangle_filled(self.x, self.y + 8,
                                     28, 16, C_CHROME)
        arcade.draw_rectangle_outline(self.x, self.y + 8,
                                      28, 16, C_OIL, 2)
        # tubes
        arcade.draw_line(self.x - 14, self.y + 2,
                         self.x - 20, self.y - 10, C_CHROME, 3)
        arcade.draw_line(self.x + 14, self.y + 2,
                         self.x + 20, self.y - 10, C_CHROME, 3)
        # war paint eye
        arcade.draw_circle_filled(self.x, self.y - 10, 5, C_OIL)
        arcade.draw_circle_filled(self.x, self.y - 10, 2, C_FIRE)

# ── Boss 2: THE DOOF WARRIOR (on War Rig) ─────────────────────────────────
class BossDoof(Boss):
    name     = "THE DOOF WARRIOR"
    subtitle = "Sonic amp + flamethrower rig"
    max_hp   = 580
    color    = C_RUST
    accent   = C_FIRE2
    radius   = 62
    phase_threshold = 0.45

    def __init__(self):
        super().__init__()
        self.ring_timer   = 0
        self.ring_cd      = 2.0
        self.flame_timer  = 0
        self.flame_cd     = 3.5
        self.flame_active = False
        self.flame_dur    = 0
        self.flame_angle  = 0
        self.amp_timer    = 0
        self.amp_beat     = 0.5     # beats every 0.5s = rhythm!
        self.orbit_amps   = [{'a': i * 120, 'pulse': 0.0} for i in range(3)]

    def on_phase2(self):
        self.ring_cd   = 1.1
        self.flame_cd  = 2.0
        self.amp_beat  = 0.3

    def _update(self, dt, bullets, player, particles):
        # orbit on war rig
        tx = SCREEN_W // 2 + math.cos(self.timer * 0.6) * 200
        ty = SCREEN_H - 175 + math.sin(self.timer * 0.4) * 70
        self.x = lerp(self.x, tx, dt * 1.1)
        self.y = lerp(self.y, ty, dt * 1.1)

        # amp animation
        self.amp_timer += dt
        for amp in self.orbit_amps:
            amp['a']     = (amp['a'] + 70 * dt) % 360
            amp['pulse'] = max(0, amp['pulse'] - dt * 4)
        if self.amp_timer >= self.amp_beat:
            self.amp_timer = 0
            # BEAT — fire ring burst
            self._shoot_ring(bullets, 8 if self.phase == 1 else 12,
                             170, C_FIRE, 9, 5, self.timer * 20, trail=C_FIRE2)
            for amp in self.orbit_amps:
                amp['pulse'] = 1.0
                ox = self.x + math.cos(math.radians(amp['a'])) * (self.radius + 35)
                oy = self.y + math.sin(math.radians(amp['a'])) * (self.radius + 35)
                spawn_fire(particles, ox, oy, 3)

        # aimed shot
        self.ring_timer += dt
        if self.ring_timer >= self.ring_cd:
            self.ring_timer = 0
            if self.phase == 2:
                for _ in range(2):
                    self._shoot_at(bullets, player.x, player.y,
                                   240, C_FIRE2, 11, 6, 12)

        # FLAMETHROWER sweep
        self.flame_timer += dt
        if self.flame_timer >= self.flame_cd and not self.flame_active:
            self.flame_timer  = 0
            self.flame_active = True
            self.flame_dur    = 0
            self.flame_angle  = angle_to(self.x, self.y, player.x, player.y)

        if self.flame_active:
            self.flame_dur   += dt
            spd               = 90 * dt * (2 if self.phase == 2 else 1)
            self.flame_angle  = (self.flame_angle + spd) % 360
            # dense flame particles + bullets
            for _ in range(2):
                a    = self.flame_angle + random.uniform(-10, 10)
                rad  = math.radians(a)
                dist_out = self.radius + 10
                fx   = self.x + math.cos(rad) * dist_out
                fy   = self.y + math.sin(rad) * dist_out
                particles.append(Particle(fx, fy,
                                          math.cos(rad) * random.uniform(60, 140),
                                          math.sin(rad) * random.uniform(60, 140),
                                          random.choice([C_FIRE, C_FIRE2, C_RUST]),
                                          random.uniform(0.3, 0.7),
                                          random.uniform(6, 12)))
            if random.random() < 0.4:
                bullets.append(Bullet(self.x, self.y, self.flame_angle,
                                      220, C_FIRE, "boss", 8, 5,
                                      trail_col=C_FIRE2))
            if self.flame_dur > (1.5 if self.phase == 1 else 2.2):
                self.flame_active = False

    def _draw_details(self):
        # amplifiers orbiting
        for amp in self.orbit_amps:
            ox = self.x + math.cos(math.radians(amp['a'])) * (self.radius + 35)
            oy = self.y + math.sin(math.radians(amp['a'])) * (self.radius + 35)
            size = 12 + amp['pulse'] * 8
            arcade.draw_rectangle_filled(ox, oy, size, size * 1.4, C_RUST)
            arcade.draw_rectangle_outline(ox, oy, size, size * 1.4, self.accent, 2)
            # speaker cone
            arcade.draw_circle_filled(ox, oy, size * 0.35, C_OIL)
        # guitar neck sticking out
        gx = self.x + math.cos(math.radians(self.angle)) * (self.radius + 22)
        gy = self.y + math.sin(math.radians(self.angle)) * (self.radius + 22)
        arcade.draw_line(self.x, self.y, gx, gy, C_RUST, 6)
        arcade.draw_circle_filled(gx, gy, 7, C_FIRE)
        # face
        arcade.draw_circle_filled(self.x, self.y + 5, 16, C_SAND_DARK)
        arcade.draw_circle_filled(self.x - 6, self.y + 8, 4, C_OIL)
        arcade.draw_circle_filled(self.x + 6, self.y + 8, 4, C_OIL)
        # flame mask (red war paint)
        arcade.draw_line(self.x - 10, self.y + 4,
                         self.x - 18, self.y - 4, C_BLOOD, 3)
        arcade.draw_line(self.x + 10, self.y + 4,
                         self.x + 18, self.y - 4, C_BLOOD, 3)

# ── Boss 3: SCROTUS (Warlord Final) ───────────────────────────────────────
class BossScrotus(Boss):
    name     = "WARLORD SCROTUS"
    subtitle = "WHO KILLED THE WORLD?! - YOU DID."
    max_hp   = 750
    color    = C_BLOOD
    accent   = C_SAND
    radius   = 58
    phase_threshold = 0.5

    def __init__(self):
        super().__init__()
        self.spread_timer = 0
        self.spread_cd    = 0.9
        self.nuke_timer   = 0
        self.nuke_cd      = 5.5
        self.dash_timer   = 0
        self.dash_cd      = 2.5
        self.target_x     = SCREEN_W // 2
        self.target_y     = SCREEN_H - 180
        self.chains       = [{'a': i * 72, 'r': self.radius + 30,
                               'ball_r': 10} for i in range(5)]
        self.rage_mode    = False

    def on_phase2(self):
        self.spread_cd = 0.5
        self.nuke_cd   = 3.0
        self.dash_cd   = 1.4
        self.rage_mode = True

    def _update(self, dt, bullets, player, particles):
        # aggressive pursuit
        self.dash_timer += dt
        if self.dash_timer >= self.dash_cd:
            self.dash_timer = 0
            margin = 100
            self.target_x = random.randint(margin, SCREEN_W - margin)
            self.target_y = random.randint(SCREEN_H // 2, SCREEN_H - 120)
            spawn_smoke(particles, self.x, self.y, 4)

        spd = 3.5 if self.rage_mode else 2.2
        self.x = lerp(self.x, self.target_x, dt * spd)
        self.y = lerp(self.y, self.target_y, dt * spd)

        # chain balls spin
        spin = 130 if self.rage_mode else 80
        for c in self.chains:
            c['a']      = (c['a'] + spin * dt) % 360
            c['ball_r'] = 10 + math.sin(self.timer * 5 + c['a'] * 0.05) * 3

        # spread shot — war-gas canisters
        self.spread_timer += dt
        if self.spread_timer >= self.spread_cd:
            self.spread_timer = 0
            if self.phase == 1:
                for _ in range(2):
                    self._shoot_at(bullets, player.x, player.y,
                                   240, C_TOXIC, 11, 6, 14, trail=C_TOXIC)
            else:
                for _ in range(4):
                    self._shoot_at(bullets, player.x, player.y,
                                   270, C_TOXIC, 13, 6, 22, trail=C_TOXIC)
                self._shoot_ring(bullets, 6, 155, C_BLOOD, 9, 5,
                                  self.timer * 18)

        # NUKE RING — "GAS THE ROAD"
        self.nuke_timer += dt
        if self.nuke_timer >= self.nuke_cd:
            self.nuke_timer = 0
            n = 18 if self.rage_mode else 14
            self._shoot_ring(bullets, n, 210, C_TOXIC, 15, 7)
            self._shoot_ring(bullets, n, 210, C_BLOOD, 13, 7, 360 / n / 2)
            spawn_fire(particles, self.x, self.y, 20)
            spawn_smoke(particles, self.x, self.y, 10)

    def _draw_details(self):
        # chain + ball weapons
        for c in self.chains:
            cx = self.x + math.cos(math.radians(c['a'])) * c['r']
            cy = self.y + math.sin(math.radians(c['a'])) * c['r']
            arcade.draw_line(self.x, self.y, cx, cy,
                             C_CHROME, 2)
            arcade.draw_circle_filled(cx, cy, c['ball_r'], C_RUST)
            arcade.draw_circle_outline(cx, cy, c['ball_r'], self.accent, 2)
            # spikes on ball
            for i in range(4):
                sa = math.radians(c['a'] + i * 90)
                arcade.draw_line(cx, cy,
                                 cx + math.cos(sa) * (c['ball_r'] + 6),
                                 cy + math.sin(sa) * (c['ball_r'] + 6),
                                 C_CHROME, 2)
        # war-painted skull face
        arcade.draw_circle_filled(self.x, self.y + 5, 18, C_SAND_DARK)
        # skull eye sockets
        arcade.draw_circle_filled(self.x - 7, self.y + 8, 5, C_OIL)
        arcade.draw_circle_filled(self.x + 7, self.y + 8, 5, C_OIL)
        arcade.draw_circle_filled(self.x - 7, self.y + 8, 2, C_BLOOD)
        arcade.draw_circle_filled(self.x + 7, self.y + 8, 2, C_BLOOD)
        # blood stripes
        for i, ox in enumerate([-8, 0, 8]):
            arcade.draw_line(self.x + ox, self.y - 2,
                             self.x + ox, self.y - 16, C_BLOOD, 2)
        # saw blade on shoulder
        for i in range(6):
            sa = math.radians(i * 60 + self.angle * 2)
            arcade.draw_line(self.x + math.cos(sa) * (self.radius - 8),
                             self.y + math.sin(sa) * (self.radius - 8),
                             self.x + math.cos(sa) * (self.radius + 10),
                             self.y + math.sin(sa) * (self.radius + 10),
                             C_CHROME, 3)


# ── Boss 4: THE PEOPLE EATER ────────────────────────────────────────────────
class BossPeopleEater(Boss):
    name     = "THE PEOPLE EATER"
    subtitle = "Glutton warlord on throne rig"
    max_hp   = 800
    color    = C_SAND_DARK
    accent   = C_FIRE2
    radius   = 64
    phase_threshold = 0.5

    def __init__(self):
        super().__init__()
        self.y          = SCREEN_H - 140
        self.ring_timer = 0
        self.ring_cd    = 2.2
        self.mine_timer = 0
        self.mine_cd    = 1.8
        self.saw_angle  = 0

    def on_phase2(self):
        self.ring_cd = 1.3
        self.mine_cd = 1.0

    def _update(self, dt, bullets, player, particles):
        # jiggle
        self.x = SCREEN_W // 2 + math.sin(self.timer * 1.2) * 40

        # mines
        self.mine_timer += dt
        if self.mine_timer >= self.mine_cd:
            self.mine_timer = 0
            for i in range(3):
                a = 60 + i * 120 + random.uniform(-15,15)
                spd = random.uniform(90, 130)
                bullets.append(Bullet(self.x, self.y, a, spd,
                                      C_RUST, "boss", 10, 6))

        # ring blast
        self.ring_timer += dt
        if self.ring_timer >= self.ring_cd:
            self.ring_timer = 0
            n = 18 if self.phase == 1 else 24
            self._shoot_ring(bullets, n, 200, C_FIRE2, 12, 6)

        # saw blade spin
        self.saw_angle = (self.saw_angle + 250 * dt) % 360
        if random.random() < 0.03:
            a = self.saw_angle + 90 + random.uniform(-10,10)
            bullets.append(Bullet(self.x, self.y, a, 280,
                                  C_CHROME, "boss", 8, 5))

    def _draw_details(self):
        # 3 spiky maces rotating
        for i in range(3):
            a = self.angle + i * 120
            ax = math.cos(math.radians(a))
            ay = math.sin(math.radians(a))
            arcade.draw_circle_filled(self.x + ax * (self.radius + 18),
                                      self.y + ay * (self.radius + 18),
                                      8, self.color)
            for s in range(8):
                sa = math.radians(s * 45)
                arcade.draw_line(self.x + ax * (self.radius + 18),
                                 self.y + ay * (self.radius + 18),
                                 self.x + ax * (self.radius + 18) + math.cos(sa)*16,
                                 self.y + ay * (self.radius + 18) + math.sin(sa)*16,
                                 C_CHROME, 3)
        # front saw blade
        arcade.draw_circle_filled(self.x, self.y + 22, 20, self.color)
        arcade.draw_circle_outline(self.x, self.y + 22, 20, C_CHROME, 3)
        for i in range(6):
            a = math.radians(self.saw_angle + i * 60)
            arcade.draw_line(self.x, self.y + 22,
                             self.x + math.cos(a) * 24,
                             self.y + 22 + math.sin(a) * 24,
                             C_CHROME, 4)
        # throne
        arcade.draw_rectangle_filled(self.x, self.y - 20,
                                     self.radius * 1.2, self.radius * 0.8,
                                     C_OIL)
        arcade.draw_rectangle_outline(self.x, self.y - 20, 
                                      self.radius * 1.2, self.radius * 0.8,
                                      C_RUST, 2)
        # face / crown
        arcade.draw_circle_filled(self.x, self.y + 5, 18, C_SAND)
        arcade.draw_rectangle_filled(self.x, self.y + 22,
                                     24, 10, C_SAND)
        arcade.draw_rectangle_outline(self.x, self.y + 22, 
                                      24, 10, C_CHROME, 2)


# ── Boss 5: GIGAHORSE CONVOY ───────────────────────────────────────────────
class BossGigahorse(Boss):
    name     = "GIGAHORSE CONVOY"
    subtitle = "Tanky war rig, side bike escorts"
    max_hp   = 850
    color    = (140, 85, 30)  # rusty brown
    accent   = C_SAND
    radius   = 70
    phase_threshold = 0.45

    def __init__(self):
        super().__init__()
        self.y = SCREEN_H - 120
        self.movement_period = 4.0
        self.movement_timer  = random.uniform(0, self.movement_period)
        self.tank_timer = 0
        self.tank_cd    = 1.8
        self.tank_speed = 250
        self.bikes = [{'x': self.x - 60, 'y': self.y - 80, 'angle': 0},
                      {'x': self.x + 60, 'y': self.y - 80, 'angle': 0}]

    def on_phase2(self):
        self.tank_cd = 1.2
        self.tank_speed = 300

    def _update(self, dt, bullets, player, particles):
        # sinusoidal tank movement
        self.movement_timer += dt
        period = self.movement_period
        self.x = SCREEN_W//2 + math.sin(self.movement_timer * 2*math.pi / period) * 180
        self.y = SCREEN_H-120 + math.cos(self.movement_timer * 2*math.pi / period) * 40

        # bullet barrage from turret
        self.tank_timer += dt
        if self.tank_timer >= self.tank_cd:
            self.tank_timer = 0
            a  = angle_to(self.x, self.y, player.x, player.y) + random.uniform(-8,8)
            for _ in range(8):
                self._shoot_at(bullets, player.x, player.y,
                               self.tank_speed, self.accent, 12, 6, 3)

        # flamethrower from side bikes
        for b in self.bikes:
            b['angle'] = (b['angle'] + 200 * dt) % 360
            bx = self.x + math.cos(math.radians(b['angle'])) * 90
            by = self.y + math.sin(math.radians(b['angle'])) * 50
            b['x'], b['y'] = bx, by

            if random.random() < 0.15:
                a = b['angle'] + 90 + random.uniform(-20, 20)
                bullets.append(Bullet(b['x'], b['y'], a, 230,
                                      C_FIRE, "boss", 10, 5, trail_col=C_FIRE2))
                spawn_fire(particles, b['x'], b['y'], 1)

    def _draw_details(self, particles=[]):
        # turret
        arcade.draw_rectangle_filled(self.x, self.y + 10, 40, 20, self.accent)
        arcade.draw_rectangle_filled(self.x, self.y + 10, 44, 10, C_RUST)
        arcade.draw_circle_filled(self.x, self.y + 10, 10, C_CHROME)
        # engine
        arcade.draw_rectangle_filled(self.x, self.y - 20, 
                                     self.radius * 0.8, self.radius * 0.5,
                                     C_OIL)
        arcade.draw_rectangle_outline(self.x, self.y - 20,
                                      self.radius * 0.8, self.radius * 0.5,
                                      C_RUST, 2)
        arcade.draw_line(self.x - 20, self.y - 40,
                         self.x + 20, self.y - 40, C_CHROME, 6)
        # exhaust pipes
        for ox in [-34, 34]:
            arcade.draw_line(self.x + ox, self.y - 35,
                             self.x + ox, self.y - 50,
                             self.accent, 3)
        if random.random() < 0.5:
            spawn_fire(particles, self.x - 32 + random.random()*64,
                       self.y - 56, 1)
            spawn_smoke(particles, self.x - 32 + random.random()*64,
                        self.y - 56, 1)
        # side bikes
        for b in self.bikes:
            arcade.draw_circle_filled(b['x'], b['y'], 18, C_OIL)
            arcade.draw_circle_outline(b['x'], b['y'], 18, self.accent, 2)
            front_w = (b['x'] + math.cos(math.radians(b['angle'])) * 20,
                       b['y'] + math.sin(math.radians(b['angle'])) * 20)
            back_w  = (b['x'] + math.cos(math.radians(b['angle']+180)) * 24,
                       b['y'] + math.sin(math.radians(b['angle']+180)) * 24)
            arcade.draw_circle_filled(front_w[0], front_w[1], 6, C_CHROME)
            arcade.draw_circle_filled(back_w[0], back_w[1], 6, C_CHROME)


def draw_hp_bar(x, y, w, h, ratio, fg, label=""):
    arcade.draw_rectangle_filled(x, y, w, h, C_OIL)
    if ratio > 0:
        fw = w * ratio
        arcade.draw_rectangle_filled(x - w/2 + fw/2, y, fw, h, fg)
    arcade.draw_rectangle_outline(x, y, w, h, C_CHROME, 2)
    if label:
        arcade.draw_text(label, x, y - 7, C_WHITE, 11, anchor_x="center")

# ── Leaderboard ────────────────────────────────────────────────────────────
SCORES_FILE = "fury_road_scores.json"
MAX_ENTRIES = 10

def lb_load():
    try:
        with open(SCORES_FILE) as f:
            return json.load(f)
    except Exception:
        return []

def lb_save(entries):
    try:
        with open(SCORES_FILE, 'w') as f:
            json.dump(entries[:MAX_ENTRIES], f, indent=2)
    except Exception:
        pass

def lb_add(name, score, bosses_beaten):
    entries = lb_load()
    entries.append({
        'name':         name.strip() or "MAX",
        'score':        score,
        'bosses':       bosses_beaten,
        'date':         time.strftime("%Y-%m-%d"),
    })
    entries.sort(key=lambda e: e['score'], reverse=True)
    entries = entries[:MAX_ENTRIES]
    lb_save(entries)
    return entries

def lb_rank(score):
    entries = lb_load()
    entries_sorted = sorted(entries, key=lambda e: e['score'], reverse=True)
    for i, e in enumerate(entries_sorted):
        if score >= e['score']:
            return i + 1
    return len(entries_sorted) + 1


S_MENU    = "menu"
S_GAME    = "game"
S_HEALING = "healing"
S_DEAD    = "dead"
S_WIN     = "win"
S_BOSSDIE = "bossdie"
S_NAME    = "name"      # name entry after game over / win
S_SCORES  = "scores"    # leaderboard screen

BOSSES = [BossImmortan, BossDoof, BossScrotus, BossPeopleEater, BossGigahorse]

# ── Main Window ────────────────────────────────────────────────────────────
class FuryRoad(arcade.Window):
    def __init__(self):
        super().__init__(SCREEN_W, SCREEN_H, TITLE, update_rate=1/FPS)
        self.set_mouse_visible(True)
        arcade.set_background_color(C_BG)

    def on_close(self):
        cleanup_sounds()
        super().on_close()

    def setup(self):
        self.state         = S_MENU
        self.player        = Player()
        self.bullets       = []
        self.particles     = []
        self.keys          = {}
        self.mouse_x       = SCREEN_W // 2
        self.mouse_y       = SCREEN_H // 2
        self.mouse_down    = False
        self.boss_idx      = 0
        self.boss          = None
        self.score         = 0
        self.heal_timer    = 0
        self.bossdie_timer = 0
        self.shake         = 0
        self.shake_x = self.shake_y = 0
        # background
        self.dust_clouds   = [DustCloud() for _ in range(12)]
        self.sand_cracks   = [(random.randint(0, SCREEN_W),
                                random.randint(0, SCREEN_H),
                                random.uniform(0, 360),
                                random.randint(20, 80)) for _ in range(35)]
        self.tread_marks   = []
        self.menu_timer    = 0.0
        self.name_input    = ""
        self.lb_entries    = []
        _init_weapon_colors()
        # preload all sounds
        for name, fn in [('shoot',       _synth_shoot),
                         ('shotgun',     _synth_shotgun),
                         ('flame',       _synth_flame),
                         ('sniper',      _synth_sniper),
                         ('hit',         _synth_hit),
                         ('explosion',   _synth_explosion),
                         ('dodge',       _synth_dodge),
                         ('player_hurt', _synth_player_hurt),
                         ('phase2',      _synth_boss_phase2),
                         ('boss_die',    _synth_boss_die)]:
            _load(name, fn)

    def start_boss(self):
        self.boss    = BOSSES[self.boss_idx]()
        self.bullets = []
        self.state   = S_GAME

    # ── Input ──────────────────────────────────────────────────────────────
    def on_key_press(self, key, mod):
        self.keys[key] = True

        if self.state == S_MENU:
            if key == arcade.key.ENTER:
                self.boss_idx  = 0
                self.player    = Player()
                self.score     = 0
                self.start_boss()
            elif key == arcade.key.TAB:
                self.state = S_SCORES

        elif self.state == S_SCORES:
            if key in (arcade.key.ESCAPE, arcade.key.R, arcade.key.ENTER):
                self.setup()

        elif self.state in (S_DEAD, S_WIN):
            if key == arcade.key.ENTER:
                # go to name entry
                self.name_input = ""
                self.state      = S_NAME
            elif key == arcade.key.R:
                self.setup()

        elif self.state == S_NAME:
            if key == arcade.key.ENTER:
                # submit score
                name = self.name_input.strip() or "MAX"
                self.lb_entries = lb_add(name, self.score, self.boss_idx)
                self.state      = S_SCORES
            elif key == arcade.key.BACKSPACE:
                self.name_input = self.name_input[:-1]
            elif key == arcade.key.ESCAPE:
                self.state = S_SCORES

        elif self.state == S_HEALING:
            if key == arcade.key.SPACE:
                self.boss_idx += 1
                if self.boss_idx >= len(BOSSES):
                    self.state = S_WIN
                else:
                    self.start_boss()

        elif self.state == S_GAME:
            if key in (arcade.key.LSHIFT, arcade.key.RSHIFT, arcade.key.SPACE):
                self.player.try_dodge(self.particles)
            elif key == arcade.key.KEY_1: self.player.weapon_idx = 0
            elif key == arcade.key.KEY_2: self.player.weapon_idx = 1
            elif key == arcade.key.KEY_3: self.player.weapon_idx = 2
            elif key == arcade.key.KEY_4: self.player.weapon_idx = 3

    def on_text(self, text):
        if self.state == S_NAME and len(self.name_input) < 12:
            if text.isprintable() and text != '\r':
                self.name_input += text.upper()

    def on_key_release(self, key, mod):
        self.keys[key] = False

    def on_mouse_motion(self, x, y, dx, dy):
        self.mouse_x = x
        self.mouse_y = y

    def on_mouse_press(self, x, y, btn, mod):
        if btn == arcade.MOUSE_BUTTON_LEFT:
            self.mouse_down = True

    def on_mouse_release(self, x, y, btn, mod):
        if btn == arcade.MOUSE_BUTTON_LEFT:
            self.mouse_down = False

    # ── Update ─────────────────────────────────────────────────────────────
    def on_update(self, dt):
        dt = min(dt, 0.05)
        self.menu_timer += dt
        self.particles = [p for p in self.particles if p.update(dt)]
        for dc in self.dust_clouds:
            dc.update(dt)
        self.shake = max(0, self.shake - dt * 9)
        self.shake_x = random.uniform(-1, 1) * self.shake * 7
        self.shake_y = random.uniform(-1, 1) * self.shake * 7

        if self.state not in (S_GAME, S_BOSSDIE, S_HEALING):
            return
        if self.state == S_GAME:
            self.player.update(dt, self.keys, self.mouse_x, self.mouse_y,
                               self.particles)
            if self.mouse_down:
                self.player.try_shoot(self.bullets, self.particles)

            for b in self.bullets:
                b.update(dt)
            self.bullets = [b for b in self.bullets if b.alive]

            if self.boss and self.boss.alive:
                self.boss.update(dt, self.bullets, self.player, self.particles)
                self._check_hits()

            if self.player.hp <= 0:
                self.state = S_DEAD
                spawn_fire(self.particles, self.player.x, self.player.y, 20)

            if self.boss and not self.boss.alive:
                self.score        += 500
                self.state         = S_BOSSDIE
                self.bossdie_timer = 2.2

        if self.state == S_BOSSDIE:
            self.bossdie_timer -= dt
            spawn_fire(self.particles,
                       SCREEN_W // 2 + random.uniform(-100, 100),
                       SCREEN_H // 2 + random.uniform(-60, 60), 3)
            if self.bossdie_timer <= 0:
                self.state = S_HEALING

        if self.state == S_HEALING:
            self.heal_timer += dt
            if self.player.hp < self.player.max_hp:
                self.player.hp = min(self.player.max_hp,
                                     self.player.hp + 28 * dt)

    def _check_hits(self):
        for b in self.bullets:
            if not b.alive:
                continue
            if b.owner == "player" and self.boss.alive:
                if dist(b.x, b.y, self.boss.x, self.boss.y) < self.boss.radius + b.size:
                    self.boss.take_damage(b.damage, self.particles)
                    if not b.pierce:
                        b.alive = False
                    self.score += 5
                    self.shake  = min(self.shake + 0.28, 2.2)
            if b.owner == "boss":
                if dist(b.x, b.y, self.player.x, self.player.y) < self.player.radius + b.size:
                    self.player.take_damage(b.damage)
                    b.alive  = False
                    spawn_particles(self.particles,
                                    self.player.x, self.player.y,
                                    C_BLOOD, 8, 130, 4, 0.5)
                    self.shake = min(self.shake + 1.2, 3.5)

        # charge collision (boss 1)
        if (self.boss.alive
                and hasattr(self.boss, 'charging')
                and self.boss.charging):
            if dist(self.player.x, self.player.y,
                    self.boss.x, self.boss.y) < self.boss.radius + self.player.radius:
                self.player.take_damage(22)
                spawn_fire(self.particles, self.player.x, self.player.y, 8)
                play_sfx('explosion', _synth_explosion, 0.8)
                self.shake = 3.5

    # ── Draw ───────────────────────────────────────────────────────────────
    def on_draw(self):
        self.clear()
        if self.state == S_MENU:
            self._draw_menu(); return
        if self.state == S_DEAD:
            self._draw_over(); return
        if self.state == S_WIN:
            self._draw_win(); return
        if self.state == S_NAME:
            self._draw_name_entry(); return
        if self.state == S_SCORES:
            self._draw_scores(); return

        ox, oy = self.shake_x, self.shake_y
        self._draw_bg(ox, oy)

        for p in self.particles:
            p.draw()
        for b in self.bullets:
            b.draw()

        if self.boss and self.boss.alive:
            self.boss.draw()

        if self.state != S_BOSSDIE:
            self.player.draw()

        self._draw_hud()

        if self.state == S_HEALING:
            self._draw_healing_overlay()
        if self.state == S_BOSSDIE:
            self._draw_bossdie_overlay()

    def _draw_bg(self, ox=0, oy=0):
        # sky gradient (dust storm)
        arcade.draw_rectangle_filled(SCREEN_W//2, SCREEN_H*0.75,
                                     SCREEN_W, SCREEN_H//2, (200, 150, 70))
        arcade.draw_rectangle_filled(SCREEN_W//2, SCREEN_H*0.35,
                                     SCREEN_W, SCREEN_H*0.7, (140, 100, 45))
        arcade.draw_rectangle_filled(SCREEN_W//2, SCREEN_H*0.1,
                                     SCREEN_W, SCREEN_H*0.2, C_BG)
        # sand floor tiles
        for gx in range(0, SCREEN_W + 80, 80):
            for gy in range(0, SCREEN_H + 80, 80):
                shade = 35 + ((gx//80 + gy//80) % 2) * 8
                arcade.draw_rectangle_filled(gx + ox, gy + oy, 79, 79,
                                             (shade + 80, shade + 55, shade + 20))
        # cracks / dried earth
        for cx, cy, ca, cl in self.sand_cracks:
            rad = math.radians(ca)
            ex  = cx + math.cos(rad) * cl
            ey  = cy + math.sin(rad) * cl
            arcade.draw_line(cx + ox, cy + oy, ex + ox, ey + oy,
                             (*C_SAND_DARK, 80), 1)
        # dust clouds
        for dc in self.dust_clouds:
            dc.draw()
        # danger zone stripe top
        for i in range(0, SCREEN_W, 50):
            arcade.draw_rectangle_filled(i + 12 + ox, SCREEN_H - 6 + oy,
                                         25, 10, C_BLOOD)

    def _draw_hud(self):
        # Player HP
        draw_hp_bar(130, 30, 220, 18,
                    self.player.hp / self.player.max_hp,
                    C_BLOOD if self.player.hp < 30 else C_FIRE,
                    f"MAX  {int(self.player.hp)}/{self.player.max_hp}")
        # fuel icon
        arcade.draw_text("⛽", 18, 18, C_FIRE, 20)
        # Dodge cooldown bar
        dodge_ready = self.player.dodge_cd <= 0 and self.player.dodge_dur <= 0
        dodge_ratio = 1.0 - (self.player.dodge_cd / self.player.DODGE_CD) if self.player.dodge_cd > 0 else 1.0
        bar_col = C_CHROME if dodge_ready else C_SAND_DARK
        draw_hp_bar(130, 56, 220, 10, dodge_ratio, bar_col)
        label = "DODGE READY  [SHIFT]" if dodge_ready else f"DODGE  {self.player.dodge_cd:.1f}s"
        arcade.draw_text(label, 22, 61, C_CHROME if dodge_ready else C_SMOKE, 10)

        # Weapon selector
        wx = 20
        for i, w in enumerate(WEAPONS):
            active = (i == self.player.weapon_idx)
            bw, bh = 68, 36
            bx = wx + bw // 2
            by = 90
            arcade.draw_rectangle_filled(bx, by, bw, bh,
                                         C_OIL if not active else C_RUST)
            arcade.draw_rectangle_outline(bx, by, bw, bh,
                                          C_FIRE if active else C_SMOKE, 2)
            arcade.draw_text(w['icon'], bx - 18, by - 6,
                             C_WHITE, 14)
            arcade.draw_text(str(i+1), bx + 10, by + 6,
                             C_FIRE if active else C_SMOKE, 11)
            if active:
                arcade.draw_text(w['name'], bx, by - 22,
                                 C_FIRE2, 9, anchor_x="center")
            wx += bw + 4
            ratio     = self.boss.hp_ratio
            bar_color = C_BLOOD if ratio > 0.45 else C_TOXIC
            draw_hp_bar(SCREEN_W//2, SCREEN_H - 28, 520, 22,
                        ratio, bar_color,
                        f"{self.boss.name}   {max(0,int(self.boss.hp))} / {self.boss.max_hp}")
            if self.boss.phase == 2:
                t = time.time()
                a = int(200 + 55 * math.sin(t * 6))
                arcade.draw_text("☠ RAGE MODE",
                                 SCREEN_W//2, SCREEN_H - 58,
                                 (*C_BLOOD, a), 15, anchor_x="center")
        # Score
        arcade.draw_text(f"SCORE  {self.score}",
                         SCREEN_W - 16, 22, C_SAND, 16, anchor_x="right")
        arcade.draw_text(f"ROAD  {self.boss_idx+1} / {len(BOSSES)}",
                         SCREEN_W - 16, 44, C_SMOKE, 13, anchor_x="right")

    def _draw_menu(self):
        # bg
        arcade.draw_rectangle_filled(SCREEN_W//2, SCREEN_H//2,
                                     SCREEN_W, SCREEN_H, (22, 16, 8))
        for gx in range(0, SCREEN_W + 80, 80):
            for gy in range(0, SCREEN_H + 80, 80):
                shade = 35 + ((gx//80 + gy//80) % 2) * 8
                arcade.draw_rectangle_filled(gx, gy, 79, 79,
                                             (shade + 70, shade + 48, shade + 15))
        for cx, cy, ca, cl in self.sand_cracks:
            rad = math.radians(ca)
            arcade.draw_line(cx, cy,
                             cx + math.cos(rad)*cl,
                             cy + math.sin(rad)*cl,
                             (*C_SAND_DARK, 70), 1)
        for dc in self.dust_clouds:
            dc.draw()

        t = self.menu_timer
        # Title
        arcade.draw_text("FURY  ROAD",
                         SCREEN_W//2, SCREEN_H//2 + 130,
                         C_FIRE, 76, anchor_x="center",
                         font_name="Arial Black")
        arcade.draw_text("BOSS  RUSH",
                         SCREEN_W//2, SCREEN_H//2 + 60,
                         C_CHROME, 38, anchor_x="center")
        arcade.draw_text("Mad Max Inspired  •  Top-Down Shooter",
                         SCREEN_W//2, SCREEN_H//2 + 22,
                         C_SAND_DARK, 15, anchor_x="center")

        # Controls
        controls = [
            "WASD / Arrows  —  Move",
            "Mouse  —  Aim",
            "Left Click (hold)  —  Shoot",
        ]
        for i, line in enumerate(controls):
            arcade.draw_text(line, SCREEN_W//2,
                             SCREEN_H//2 - 22 - i * 24,
                             C_SMOKE, 14, anchor_x="center")

        # Enemy preview
        arcade.draw_text("THE GAUNTLET:",
                         SCREEN_W//2, SCREEN_H//2 - 110,
                         C_FIRE2, 16, anchor_x="center")
        enemies = [
            "I.   IMMORTAN'S ENFORCER — Chrome warrior, charge ram",
            "II.  THE DOOF WARRIOR    — Sonic amp + flamethrower",
            "III. WARLORD SCROTUS     — Chaos chains, toxic barrage",
        ]
        for i, line in enumerate(enemies):
            arcade.draw_text(line, SCREEN_W//2,
                             SCREEN_H//2 - 136 - i * 22,
                             C_SAND if i < 2 else C_BLOOD,
                             13, anchor_x="center")

        # Blink enter
        a = int(180 + 75 * math.sin(t * 3))
        arcade.draw_text("PRESS  ENTER  TO  RIDE",
                         SCREEN_W//2, 66,
                         (*C_FIRE, a), 24, anchor_x="center")
        arcade.draw_text("TAB  —  Leaderboard",
                         SCREEN_W//2, 36,
                         (*C_SMOKE, 180), 14, anchor_x="center")

    def _draw_healing_overlay(self):
        arcade.draw_rectangle_filled(SCREEN_W//2, SCREEN_H//2,
                                     SCREEN_W, SCREEN_H, (0,0,0,165))
        arcade.draw_text("ENEMY DOWN!",
                         SCREEN_W//2, SCREEN_H//2 + 110,
                         C_FIRE, 44, anchor_x="center",
                         font_name="Arial Black")
        arcade.draw_text("+500  GLORY",
                         SCREEN_W//2, SCREEN_H//2 + 62,
                         C_FIRE2, 24, anchor_x="center")
        arcade.draw_text("Patching wounds...",
                         SCREEN_W//2, SCREEN_H//2 + 22,
                         C_CHROME, 18, anchor_x="center")
        hp_ratio = self.player.hp / self.player.max_hp
        draw_hp_bar(SCREEN_W//2, SCREEN_H//2 - 12, 260, 20,
                    hp_ratio, C_FIRE)
        if self.boss_idx + 1 < len(BOSSES):
            next_b = BOSSES[self.boss_idx + 1].name
            arcade.draw_text(f"Next threat:  {next_b}",
                             SCREEN_W//2, SCREEN_H//2 - 55,
                             C_SAND, 15, anchor_x="center")
        t = time.time()
        a = int(180 + 75 * math.sin(t * 4))
        arcade.draw_text("PRESS  SPACE  TO  KEEP  RIDING",
                         SCREEN_W//2, SCREEN_H//2 - 100,
                         (*C_FIRE, a), 20, anchor_x="center")

    def _draw_bossdie_overlay(self):
        arcade.draw_rectangle_filled(SCREEN_W//2, SCREEN_H//2,
                                     SCREEN_W, SCREEN_H, (0,0,0,110))
        arcade.draw_text("ELIMINATED!",
                         SCREEN_W//2, SCREEN_H//2,
                         C_FIRE, 56, anchor_x="center",
                         font_name="Arial Black")

    def _draw_over(self):
        arcade.draw_rectangle_filled(SCREEN_W//2, SCREEN_H//2,
                                     SCREEN_W, SCREEN_H, C_BG)
        arcade.draw_text("YOU DIED ON THE ROAD",
                         SCREEN_W//2, SCREEN_H//2 + 90,
                         C_BLOOD, 46, anchor_x="center",
                         font_name="Arial Black")
        arcade.draw_text(f"SCORE:  {self.score}",
                         SCREEN_W//2, SCREEN_H//2 + 30,
                         C_FIRE, 30, anchor_x="center")
        arcade.draw_text(f"Reached enemy {self.boss_idx+1} of {len(BOSSES)}",
                         SCREEN_W//2, SCREEN_H//2 - 15,
                         C_SAND, 18, anchor_x="center")
        t = time.time()
        a = int(180 + 75 * math.sin(t * 3))
        arcade.draw_text("PRESS  ENTER  TO  SAVE  SCORE",
                         SCREEN_W//2, SCREEN_H//2 - 70,
                         (*C_CHROME, a), 20, anchor_x="center")
        arcade.draw_text("PRESS  R  TO  RETRY  WITHOUT  SAVING",
                         SCREEN_W//2, SCREEN_H//2 - 100,
                         (*C_SMOKE, 180), 14, anchor_x="center")

    def _draw_win(self):
        arcade.draw_rectangle_filled(SCREEN_W//2, SCREEN_H//2,
                                     SCREEN_W, SCREEN_H, C_BG)
        arcade.draw_text("FURY ROAD CONQUERED!",
                         SCREEN_W//2, SCREEN_H//2 + 100,
                         C_FIRE, 46, anchor_x="center",
                         font_name="Arial Black")
        arcade.draw_text('"WHO KILLED THE WORLD?"',
                         SCREEN_W//2, SCREEN_H//2 + 48,
                         C_SAND, 20, anchor_x="center")
        arcade.draw_text('"NOT YOU."',
                         SCREEN_W//2, SCREEN_H//2 + 20,
                         C_CHROME, 20, anchor_x="center")
        arcade.draw_text(f"FINAL SCORE:  {self.score}",
                         SCREEN_W//2, SCREEN_H//2 - 25,
                         C_FIRE2, 34, anchor_x="center")
        t = time.time()
        a = int(180 + 75 * math.sin(t * 3))
        arcade.draw_text("PRESS  ENTER  TO  SAVE  SCORE",
                         SCREEN_W//2, SCREEN_H//2 - 85,
                         (*C_FIRE, a), 22, anchor_x="center")
        arcade.draw_text("PRESS  R  TO  PLAY  AGAIN  WITHOUT  SAVING",
                         SCREEN_W//2, SCREEN_H//2 - 115,
                         (*C_SMOKE, 180), 14, anchor_x="center")

    def _draw_name_entry(self):
        arcade.draw_rectangle_filled(SCREEN_W//2, SCREEN_H//2,
                                     SCREEN_W, SCREEN_H, C_BG)
        arcade.draw_text("ENTER YOUR NAME",
                         SCREEN_W//2, SCREEN_H//2 + 120,
                         C_FIRE, 42, anchor_x="center",
                         font_name="Arial Black")
        arcade.draw_text(f"SCORE:  {self.score}",
                         SCREEN_W//2, SCREEN_H//2 + 60,
                         C_FIRE2, 24, anchor_x="center")
        # name input box
        box_w, box_h = 380, 52
        arcade.draw_rectangle_filled(SCREEN_W//2, SCREEN_H//2,
                                     box_w, box_h, C_OIL)
        arcade.draw_rectangle_outline(SCREEN_W//2, SCREEN_H//2,
                                      box_w, box_h, C_CHROME, 2)
        display = self.name_input or "MAX"
        col     = C_CHROME if self.name_input else C_SMOKE
        t       = time.time()
        cursor  = "|" if int(t * 2) % 2 == 0 else ""
        arcade.draw_text(display + cursor,
                         SCREEN_W//2, SCREEN_H//2 - 10,
                         col, 28, anchor_x="center")
        arcade.draw_text("(max 12 chars — letters & numbers)",
                         SCREEN_W//2, SCREEN_H//2 - 48,
                         C_SMOKE, 12, anchor_x="center")
        arcade.draw_text("PRESS  ENTER  TO  CONFIRM",
                         SCREEN_W//2, SCREEN_H//2 - 90,
                         C_SAND, 16, anchor_x="center")

    def _draw_scores(self):
        arcade.draw_rectangle_filled(SCREEN_W//2, SCREEN_H//2,
                                     SCREEN_W, SCREEN_H, C_BG)
        # header
        arcade.draw_text("FURY ROAD  LEADERBOARD",
                         SCREEN_W//2, SCREEN_H - 60,
                         C_FIRE, 40, anchor_x="center",
                         font_name="Arial Black")
        arcade.draw_line(100, SCREEN_H - 85, SCREEN_W - 100, SCREEN_H - 85,
                         C_RUST, 2)

        entries = lb_load()
        if not entries:
            arcade.draw_text("No scores yet — be the first!",
                             SCREEN_W//2, SCREEN_H//2,
                             C_SMOKE, 20, anchor_x="center")
        else:
            cols = [120, 220, 620, 780, 900]   # rank, name, score, bosses, date
            headers = ["#", "NAME", "SCORE", "BOSSES", "DATE"]
            for i, (hdr, cx) in enumerate(zip(headers, cols)):
                arcade.draw_text(hdr, cx, SCREEN_H - 115,
                                 C_SAND, 14, anchor_x="center")
            arcade.draw_line(100, SCREEN_H - 125, SCREEN_W - 100, SCREEN_H - 125,
                             C_SMOKE, 1)

            # highlight current run score
            current_score = self.score
            for rank, e in enumerate(entries[:MAX_ENTRIES], 1):
                y      = SCREEN_H - 145 - (rank - 1) * 38
                is_new = (e['score'] == current_score and
                          e.get('name', '') == (self.name_input.strip() or 'MAX'))
                row_col = C_FIRE2 if (rank == 1) else (C_CHROME if is_new else C_WHITE)
                prefix  = "► " if is_new else ""
                data = [
                    f"{rank}",
                    prefix + e.get('name', '???'),
                    str(e.get('score', 0)),
                    f"{e.get('bosses', 0)} / {len(BOSSES)}",
                    e.get('date', ''),
                ]
                for val, cx in zip(data, cols):
                    arcade.draw_text(val, cx, y, row_col, 15, anchor_x="center")
                if rank == 1:
                    arcade.draw_text("👑", cols[0] - 30, y, C_FIRE2, 14)

        arcade.draw_line(100, 75, SCREEN_W - 100, 75, C_RUST, 2)
        arcade.draw_text("PRESS  ENTER  TO  RETURN  TO  MENU",
                         SCREEN_W//2, 44, C_SMOKE, 15, anchor_x="center")


def main():
    window = FuryRoad()
    window.setup()
    arcade.run()

if __name__ == "__main__":
    main()
