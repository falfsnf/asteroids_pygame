# ASTEROIDE SINGLEPLAYER v1.0
# This file coordinates world state, spawning, collisions, scoring, and progression.

import math
from random import random, uniform

import pygame as pg

import config as C
from sprites import Asteroid, ShieldPickup, Ship, UFO, RapidFirePickup, ShotgunPickup
from utils import Vec, rand_edge_pos, rand_unit_vec


class World:
    def __init__(self):
        self.ship = Ship(Vec(C.WIDTH / 2, C.HEIGHT / 2))
        self.bullets = pg.sprite.Group()
        self.ufo_bullets = pg.sprite.Group()
        self.asteroids = pg.sprite.Group()
        self.ufos = pg.sprite.Group()
        self.powerups = pg.sprite.Group()
        self.all_sprites = pg.sprite.Group(self.ship)

        self.score = 0
        self.lives = C.START_LIVES
        self.wave = 0
        self.wave_cool = C.WAVE_DELAY
        self.safe = C.SAFE_SPAWN_TIME
        self.ufo_timer = C.UFO_SPAWN_EVERY
        self.game_over = False

        self.combo_multiplier = 1
        self.combo_timer = 0.0

        self.shotgun_timer = 30.0

    def should_spawn_resistant(self, size: str) -> bool:
        if size == "L":
            return random() < C.RESISTANT_ASTEROID_CHANCE_L
        if size == "M":
            return random() < C.RESISTANT_ASTEROID_CHANCE_M
        return False

    def start_wave(self):
        self.wave += 1
        count = 3 + self.wave

        for _ in range(count):
            pos = rand_edge_pos()
            while (pos - self.ship.pos).length() < 150:
                pos = rand_edge_pos()

            ang = uniform(0, math.tau)
            speed = uniform(C.AST_VEL_MIN, C.AST_VEL_MAX)
            vel = Vec(math.cos(ang), math.sin(ang)) * speed
            resistant = self.should_spawn_resistant("L")
            self.spawn_asteroid(pos, vel, "L", resistant=resistant)

    def spawn_asteroid(self, pos: Vec, vel: Vec, size: str, resistant: bool = False):
        asteroid = Asteroid(pos, vel, size, resistant=resistant)
        self.asteroids.add(asteroid)
        self.all_sprites.add(asteroid)

    def spawn_shield_pickup(self, pos: Vec):
        pickup = ShieldPickup(pos)
        self.powerups.add(pickup)
        self.all_sprites.add(pickup)

    def spawn_rapid_fire_pickup(self, pos: Vec):
        pickup = RapidFirePickup(pos)
        self.powerups.add(pickup)
        self.all_sprites.add(pickup)

    def spawn_shotgun_pickup(self):
        pos = Vec(uniform(50, C.WIDTH - 50), uniform(50, C.HEIGHT - 50))
        pickup = ShotgunPickup(pos)
        self.powerups.add(pickup)
        self.all_sprites.add(pickup)

    def spawn_ufo(self):
        if self.ufos:
            return

        small = uniform(0, 1) < 0.5
        y = uniform(0, C.HEIGHT)
        x = 0 if uniform(0, 1) < 0.5 else C.WIDTH

        ufo = UFO(Vec(x, y), small)
        ufo.dir.xy = (1, 0) if x == 0 else (-1, 0)
        self.ufos.add(ufo)
        self.all_sprites.add(ufo)

    def ufo_try_fire(self):
        for ufo in self.ufos:
            bullet = ufo.fire_at(self.ship.pos)
            if bullet:
                self.ufo_bullets.add(bullet)
                self.all_sprites.add(bullet)

    def try_fire(self):
        if len(self.bullets) >= C.MAX_BULLETS:
            return

        if self.ship.has_shotgun():
            result = self.ship.fire_shotgun()
        else:
            result = self.ship.fire()

        if isinstance(result, list):
            for b in result:
                self.bullets.add(b)
                self.all_sprites.add(b)
        elif result:
            self.bullets.add(result)
            self.all_sprites.add(result)

    def hyperspace(self):
        self.ship.hyperspace()
        self.score = max(0, self.score - C.HYPERSPACE_COST)

    def register_combo(self):
        if self.combo_timer > 0:
            self.combo_multiplier = min(
                self.combo_multiplier + 1,
                C.COMBO_MAX_MULTIPLIER,
            )
        else:
            self.combo_multiplier = 2

        self.combo_timer = C.COMBO_WINDOW

    def reset_combo(self):
        self.combo_multiplier = 1
        self.combo_timer = 0.0

    def update(self, dt: float, keys):
        self.ship.control(keys, dt)
        self.all_sprites.update(dt)

        self.shotgun_timer -= dt
        if self.shotgun_timer <= 0:
            if len(self.powerups) == 0:
                self.spawn_shotgun_pickup()
            self.shotgun_timer = 30.0

        if self.combo_timer > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.reset_combo()

        if self.safe > 0:
            self.safe -= dt
            self.ship.invuln = max(self.ship.invuln, 0.5)

        if self.ufos:
            self.ufo_try_fire()
        else:
            self.ufo_timer -= dt

        if not self.ufos and self.ufo_timer <= 0:
            self.spawn_ufo()
            self.ufo_timer = C.UFO_SPAWN_EVERY

        self.handle_collisions()

        if not self.asteroids and self.wave_cool <= 0:
            self.start_wave()
            self.wave_cool = C.WAVE_DELAY
        elif not self.asteroids:
            self.wave_cool -= dt

    def handle_collisions(self):
        hits = pg.sprite.groupcollide(
            self.asteroids,
            self.bullets,
            False,
            True,
            collided=lambda a, b: (a.pos - b.pos).length() < a.r,
        )
        for asteroid, _ in hits.items():
            if asteroid.take_hit():
                self.split_asteroid(asteroid)

        ufo_hits = pg.sprite.groupcollide(
            self.asteroids,
            self.ufo_bullets,
            False,
            True,
            collided=lambda a, b: (a.pos - b.pos).length() < a.r,
        )
        for asteroid, _ in ufo_hits.items():
            if asteroid.take_hit():
                self.split_asteroid(asteroid)

        for pickup in list(self.powerups):
            if (pickup.pos - self.ship.pos).length() < (pickup.r + self.ship.r):

                if isinstance(pickup, ShieldPickup):
                    self.ship.activate_shield()
                elif isinstance(pickup, RapidFirePickup):
                    self.ship.activate_rapid_fire()
                elif isinstance(pickup, ShotgunPickup):
                    self.ship.activate_shotgun()

                pickup.kill()

        if self.ship.invuln <= 0 and self.safe <= 0:
            for asteroid in self.asteroids:
                if (asteroid.pos - self.ship.pos).length() < (asteroid.r + self.ship.r):
                    self.damage_ship()
                    break

            for ufo in self.ufos:
                if (ufo.pos - self.ship.pos).length() < (ufo.r + self.ship.r):
                    self.damage_ship()
                    break

            for bullet in list(self.ufo_bullets):
                if (bullet.pos - self.ship.pos).length() < (bullet.r + self.ship.r):
                    bullet.kill()
                    self.damage_ship()
                    break

        for ufo in list(self.ufos):
            for bullet in list(self.bullets):
                if (ufo.pos - bullet.pos).length() < (ufo.r + bullet.r):
                    score = C.UFO_SMALL["score"] if ufo.small else C.UFO_BIG["score"]
                    self.score += score
                    ufo.kill()
                    bullet.kill()

    def split_asteroid(self, asteroid: Asteroid):
        base_score = C.AST_SIZES[asteroid.size]["score"]
        self.register_combo()
        self.score += base_score * self.combo_multiplier

        split = C.AST_SIZES[asteroid.size]["split"]
        pos = Vec(asteroid.pos)
        size = asteroid.size

        asteroid.kill()

        if size in ("L", "M") and len(self.powerups) == 0:
            roll = random()

            if roll < C.SHIELD_DROP_CHANCE:
                self.spawn_shield_pickup(pos)

            elif roll < C.SHIELD_DROP_CHANCE + C.RAPID_FIRE_DROP_CHANCE:
                self.spawn_rapid_fire_pickup(pos)

        for new_size in split:
            direction = rand_unit_vec()
            speed = uniform(C.AST_VEL_MIN, C.AST_VEL_MAX) * 1.2
            resistant = self.should_spawn_resistant(new_size)
            self.spawn_asteroid(pos, direction * speed, new_size, resistant=resistant)

    def damage_ship(self):
        if self.ship.has_shield():
            self.ship.invuln = max(self.ship.invuln, 0.5)
            return

        self.ship_die()

    def ship_die(self):
        self.reset_combo()
        self.lives -= 1

        if self.lives <= 0:
            self.game_over = True
            return

        self.ship.pos.xy = (C.WIDTH / 2, C.HEIGHT / 2)
        self.ship.vel.xy = (0, 0)
        self.ship.angle = -90
        self.ship.invuln = C.SAFE_SPAWN_TIME
        self.safe = C.SAFE_SPAWN_TIME

    def draw(self, surf: pg.Surface, font: pg.font.Font):
        for sprite in self.all_sprites:
            sprite.draw(surf)

        pg.draw.line(surf, (60, 60, 60), (0, 50), (C.WIDTH, 50), width=1)

        shield_txt = (
            f"SHIELD {self.ship.shield:0.1f}s"
            if self.ship.has_shield()
            else "SHIELD OFF"
        )

        rapid_txt = (
            f"RAPID {self.ship.rapid_fire:0.1f}s"
            if self.ship.has_rapid_fire()
            else "RAPID OFF"
        )

        combo_txt = (
            f"COMBO x{self.combo_multiplier}"
            if self.combo_multiplier > 1 and self.combo_timer > 0
            else "COMBO x1"
        )

        text = (
            f"SCORE {self.score:06d} "
            f"LIVES {self.lives} "
            f"WAVE {self.wave} "
            f"{shield_txt} "
            f"{rapid_txt} "
            f"{combo_txt}"
        )
        label = font.render(text, True, C.WHITE)
        surf.blit(label, (10, 10))
