"""The attack loop: train -> search -> evaluate -> deploy -> return home."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np

from farmbot import imaging
from farmbot.adb import Device
from farmbot.config import Config
from farmbot.deploy import spread
from farmbot.loot import Loot
from farmbot.vision import Templates, crop_rel, read_number

log = logging.getLogger(__name__)

DEFAULT_TIMEOUTS = {
    "home": 30,          # waiting for the village screen
    "search": 60,        # waiting for an enemy base to show up
    "button": 10,        # waiting for a button after a tap
}


MAX_FAILURES = 3


class BotError(RuntimeError):
    pass


class Bot:
    def __init__(self, config: Config, device: Device, debug_dir: Path | None = None):
        self.cfg = config
        self.device = device
        self.templates = Templates(config.templates_dir, config.threshold)
        self.timeouts = {**DEFAULT_TIMEOUTS, **config.timeouts}
        self.debug_dir = debug_dir
        self.attacks = 0

    # --- helpers -----------------------------------------------------------

    def rel_to_px(self, x: float, y: float) -> tuple[int, int]:
        w, h = self.device.size
        return int(x * w), int(y * h)

    def tap_rel(self, x: float, y: float) -> None:
        self.device.tap(*self.rel_to_px(x, y))

    def wait_for(self, name: str, timeout: float, interval: float = 0.7):
        deadline = time.monotonic() + timeout
        while True:
            screen = self.device.screenshot()
            match = self.templates.find(screen, name)
            if match:
                return match, screen
            if time.monotonic() >= deadline:
                self.save_debug(screen, f"timeout_{name}")
                raise BotError(f"'{name}' nach {timeout:.0f}s nicht gefunden.")
            time.sleep(interval)

    def wait_gone(self, name: str, timeout: float, interval: float = 0.4) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.templates.find(self.device.screenshot(), name):
                return
            time.sleep(interval)

    def tap_template(self, name: str, timeout: float | None = None) -> None:
        match, _ = self.wait_for(name, timeout if timeout is not None else self.timeouts["button"])
        self.device.tap(*match.center)

    def save_debug(self, screen: np.ndarray, label: str) -> None:
        if self.debug_dir is None:
            return
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        path = self.debug_dir / f"{time.strftime('%Y%m%d-%H%M%S')}_{label}.png"
        imaging.imwrite(path, screen)
        log.info("Debug-Screenshot gespeichert: %s", path)

    # --- steps -------------------------------------------------------------

    def ensure_home(self) -> None:
        log.info("Warte auf Dorf-Ansicht …")
        self.wait_for("attack_button", self.timeouts["home"])

    def train(self) -> None:
        if not self.cfg.train_sequence:
            return
        log.info("Trainiere Armee (%s)", " → ".join(self.cfg.train_sequence))
        for name in self.cfg.train_sequence:
            self.tap_template(name)
            time.sleep(0.8)
        if self.cfg.wait_after_train > 0:
            log.info("Warte %.0fs auf die Armee …", self.cfg.wait_after_train)
            time.sleep(self.cfg.wait_after_train)

    def start_search(self) -> None:
        log.info("Starte Gegnersuche")
        self.tap_template("attack_button")
        self.tap_template("find_match")
        # Newer game versions show an army overview with a second "Attack!" button.
        if self.templates.has("attack_confirm"):
            self.tap_template("attack_confirm")
        self.wait_for("next_button", self.timeouts["search"])

    def read_loot(self, screen: np.ndarray) -> Loot:
        values: dict[str, int | None] = {}
        for res in ("gold", "elixir", "dark"):
            region = self.cfg.loot_regions.get(res)
            values[res] = read_number(crop_rel(screen, region)[0]) if region else None
        return Loot(**values)

    def find_target(self) -> bool:
        """Skip bases until one passes the loot filter. Returns False if max_skips is hit."""
        for skip in range(self.cfg.max_skips + 1):
            time.sleep(1.0)  # let the base and loot numbers render
            screen = self.device.screenshot()
            loot = self.read_loot(screen)
            unreadable = loot.gold is None and loot.elixir is None
            log.info("Basis %d: %s", skip + 1, loot)
            if unreadable:
                self.save_debug(screen, "loot_unreadable")
            if self.cfg.loot_filter.accept(loot) or (unreadable and self.cfg.attack_on_unreadable):
                log.info("→ Angriff!")
                return True
            if skip == self.cfg.max_skips:
                break
            log.info("→ Weiter")
            self.tap_template("next_button")
            self.wait_gone("next_button", self.timeouts["button"])
            self.wait_for("next_button", self.timeouts["search"])
        return False

    def deploy(self) -> list[tuple[float, str, tuple[float, float]]]:
        """Deploy all slots. Returns pending hero abilities as (due_time, name, slot_pos)."""
        abilities = []
        for slot in self.cfg.slots:
            sides = slot.sides or self.cfg.deploy_sides
            points = spread(self.cfg.diamond, sides, slot.count, self.cfg.deploy_outward)
            log.info("Setze %s ab (%d×)", slot.name, len(points))
            self.tap_rel(*slot.pos)
            time.sleep(0.2)
            for x, y in points:
                self.tap_rel(x, y)
                time.sleep(self.cfg.tap_delay)
            if slot.ability_after is not None:
                abilities.append((time.monotonic() + slot.ability_after, slot.name, slot.pos))
        return abilities

    def surrender(self) -> None:
        log.info("Beende Kampf vorzeitig")
        self.tap_template("end_battle")
        if self.templates.has("surrender_confirm"):
            self.tap_template("surrender_confirm")

    def wait_battle_end(self, abilities: list[tuple[float, str, tuple[float, float]]]) -> None:
        start = time.monotonic()
        surrendered = False
        while True:
            now = time.monotonic()
            for item in list(abilities):
                due, name, pos = item
                if now >= due:
                    log.info("Aktiviere Fähigkeit: %s", name)
                    self.tap_rel(*pos)
                    abilities.remove(item)

            screen = self.device.screenshot()
            match = self.templates.find(screen, "return_home")
            if match:
                self.save_debug(screen, "result")
                self.device.tap(*match.center)
                return

            elapsed = now - start
            if (not surrendered and self.cfg.surrender_after is not None
                    and elapsed >= self.cfg.surrender_after and self.templates.has("end_battle")):
                self.surrender()
                surrendered = True
            if elapsed > self.cfg.battle_max_duration + 30:
                self.save_debug(screen, "battle_timeout")
                raise BotError("Kampfende nicht erkannt.")
            time.sleep(1.5)

    # --- main loop ---------------------------------------------------------

    def attack_once(self) -> None:
        self.ensure_home()
        self.train()
        self.start_search()
        if not self.find_target():
            log.warning("Keine passende Basis nach %d Skips – greife trotzdem an.", self.cfg.max_skips)
        abilities = self.deploy()
        self.wait_battle_end(abilities)
        self.attacks += 1
        log.info("Angriff %d abgeschlossen", self.attacks)

    def run(self) -> None:
        self.device.ensure_connected()
        log.info("Bildschirm: %dx%d", *self.device.size)
        failures = 0
        while self.cfg.max_attacks == 0 or self.attacks < self.cfg.max_attacks:
            try:
                self.attack_once()
                failures = 0
            except BotError as e:
                failures += 1
                log.error("%s (Fehler %d/%d)", e, failures, MAX_FAILURES)
                if failures >= MAX_FAILURES:
                    raise
                log.info("Starte das Spiel neu und versuche es erneut …")
                self.device.restart_app(self.cfg.package)
                time.sleep(15)
            time.sleep(self.cfg.pause_between_attacks)
        log.info("Fertig: %d Angriffe.", self.attacks)
