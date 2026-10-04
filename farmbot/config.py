"""Load and validate the YAML configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from farmbot.deploy import Line
from farmbot.loot import LootFilter
from farmbot.vision import DEFAULT_REGIONS, Rect


class ConfigError(ValueError):
    pass


@dataclass
class TroopSlot:
    name: str
    pos: tuple[float, float]  # relative position of the slot in the troop bar
    count: int = 1            # taps to deploy (1 for heroes / clan castle)
    sides: list[str] | None = None  # deploy lines, overrides army.deploy_sides
    ability_after: float | None = None  # heroes: tap slot again after N seconds
    template: str | None = None  # find the slot in the troop bar by image instead of pos
    until_empty: bool = False  # deploy leftovers one by one until the card is greyed out


@dataclass
class Config:
    serial: str | None = None
    adb_path: str = "adb"
    package: str = "com.supercell.clashofclans"

    templates_dir: str = "templates"
    threshold: float = 0.85
    reference_width: int | None = None
    regions: dict[str, Rect] = field(default_factory=lambda: dict(DEFAULT_REGIONS))

    loot_filter: LootFilter = field(default_factory=LootFilter)
    loot_regions: dict[str, Rect] = field(default_factory=dict)
    max_skips: int = 100
    attack_on_unreadable: bool = False

    slots: list[TroopSlot] = field(default_factory=list)
    deploy_lines: dict[str, Line] = field(default_factory=dict)
    deploy_sides: list[str] = field(default_factory=list)
    deploy_points: int = 0  # >0: deploy at this many points, tapping all of them at the same time
    line_shift: float = 0  # move all deploy lines this many pixels outwards (negative: inwards)
    leftover_hold: float = 4.0  # seconds to keep the finger down per leftover burst (until_empty)
    leftover_timeout: float = 60  # give up on leftovers after this many seconds

    battle_max_duration: float = 180
    surrender_after: float | None = None
    surrender_when_idle: float | None = None  # window in seconds for surrender_min_loot
    surrender_min_loot: int = 1  # give up once less loot than this was taken within the window
    surrender_min_time: float = 30  # seconds after deploy start before stalled looting may end the battle

    train_sequence: list[str] = field(default_factory=list)
    wait_after_train: float = 0

    max_attacks: int = 0  # 0 = unlimited
    pause_between_attacks: float = 2

    timeouts: dict[str, float] = field(default_factory=dict)


def _rel_point(value: Any, where: str) -> tuple[float, float]:
    if not (isinstance(value, (list, tuple)) and len(value) == 2):
        raise ConfigError(f"{where}: erwartet [x, y], bekommen {value!r}")
    x, y = float(value[0]), float(value[1])
    if not (0 <= x <= 1 and 0 <= y <= 1):
        raise ConfigError(f"{where}: Koordinaten müssen relativ (0..1) sein, bekommen {value!r}")
    return x, y


def _rel_rect(value: Any, where: str) -> Rect:
    if not (isinstance(value, (list, tuple)) and len(value) == 4):
        raise ConfigError(f"{where}: erwartet [x1, y1, x2, y2], bekommen {value!r}")
    x1, y1 = _rel_point(value[:2], where)
    x2, y2 = _rel_point(value[2:], where)
    if x2 <= x1 or y2 <= y1:
        raise ConfigError(f"{where}: x2/y2 müssen größer als x1/y1 sein")
    return x1, y1, x2, y2


def _sides(value: Any, lines: dict[str, Line], where: str) -> list[str]:
    sides = list(value)
    if not sides:
        raise ConfigError(f"{where}: mindestens eine Absetzlinie angeben")
    for s in sides:
        if s not in lines:
            raise ConfigError(f"{where}: unbekannte Absetzlinie '{s}', vorhanden: {', '.join(lines) or '-'}")
    return sides


def parse(data: dict[str, Any]) -> Config:
    cfg = Config()
    device = data.get("device") or {}
    cfg.serial = device.get("serial")
    cfg.adb_path = device.get("adb_path", cfg.adb_path)
    cfg.package = (data.get("game") or {}).get("package", cfg.package)

    templates = data.get("templates") or {}
    cfg.templates_dir = templates.get("dir", cfg.templates_dir)
    cfg.threshold = float(templates.get("threshold", cfg.threshold))
    if templates.get("reference_width"):
        cfg.reference_width = int(templates["reference_width"])
    for name, rect in (templates.get("regions") or {}).items():
        if rect is None:  # null = search the whole screen
            cfg.regions.pop(name, None)
        else:
            cfg.regions[name] = _rel_rect(rect, f"templates.regions.{name}")

    search = data.get("search") or {}
    try:
        cfg.loot_filter = LootFilter(
            min_gold=int(search.get("min_gold", 0)),
            min_elixir=int(search.get("min_elixir", 0)),
            min_dark=int(search.get("min_dark", 0)),
            mode=search.get("mode", "any"),
            min_total=int(search.get("min_total", 0)),
        )
    except ValueError as e:
        raise ConfigError(str(e)) from e
    cfg.max_skips = int(search.get("max_skips", cfg.max_skips))
    cfg.attack_on_unreadable = bool(search.get("attack_on_unreadable", False))
    cfg.loot_regions = {
        name: _rel_rect(rect, f"loot_regions.{name}")
        for name, rect in (data.get("loot_regions") or {}).items()
    }

    for name, line in (data.get("deploy_lines") or {}).items():
        if not (isinstance(line, (list, tuple)) and len(line) == 2):
            raise ConfigError(f"deploy_lines.{name}: erwartet [[x1, y1], [x2, y2]]")
        where = f"deploy_lines.{name}"
        cfg.deploy_lines[name] = (_rel_point(line[0], where), _rel_point(line[1], where))
    if not cfg.deploy_lines:
        raise ConfigError("deploy_lines ist leer – mindestens eine Absetzlinie wird benötigt.")

    army = data.get("army") or {}
    cfg.deploy_sides = _sides(army.get("deploy_sides", list(cfg.deploy_lines)), cfg.deploy_lines,
                              "army.deploy_sides")
    cfg.deploy_points = int(army.get("deploy_points", 0))
    cfg.line_shift = float(army.get("line_shift", 0))
    cfg.leftover_hold = float(army.get("leftover_hold", cfg.leftover_hold))
    cfg.leftover_timeout = float(army.get("leftover_timeout", cfg.leftover_timeout))
    for i, slot in enumerate(army.get("slots") or []):
        where = f"army.slots[{i}]"
        cfg.slots.append(TroopSlot(
            name=str(slot.get("name", f"slot{i}")),
            pos=_rel_point(slot.get("pos"), f"{where}.pos"),
            count=int(slot.get("count", 1)),
            sides=_sides(slot["sides"], cfg.deploy_lines, f"{where}.sides") if "sides" in slot else None,
            ability_after=float(slot["ability_after"]) if slot.get("ability_after") is not None else None,
            template=slot.get("template"),
            until_empty=bool(slot.get("until_empty", False)),
        ))
    if not cfg.slots:
        raise ConfigError("army.slots ist leer – mindestens ein Truppen-Slot wird benötigt.")


    battle = data.get("battle") or {}
    cfg.battle_max_duration = float(battle.get("max_duration", cfg.battle_max_duration))
    if battle.get("surrender_after") is not None:
        cfg.surrender_after = float(battle["surrender_after"])
    if battle.get("surrender_when_idle") is not None:
        cfg.surrender_when_idle = float(battle["surrender_when_idle"])
    cfg.surrender_min_loot = int(battle.get("surrender_min_loot", cfg.surrender_min_loot))
    cfg.surrender_min_time = float(battle.get("surrender_min_time", cfg.surrender_min_time))

    training = data.get("training") or {}
    cfg.train_sequence = list(training.get("sequence") or [])
    cfg.wait_after_train = float(training.get("wait_after", 0))

    session = data.get("session") or {}
    cfg.max_attacks = int(session.get("max_attacks", 0))
    cfg.pause_between_attacks = float(session.get("pause_between_attacks", cfg.pause_between_attacks))

    cfg.timeouts = {k: float(v) for k, v in (data.get("timeouts") or {}).items()}
    return cfg


def load(path: str | Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Konfiguration {path} nicht gefunden. Tipp: config.example.yaml nach {path} kopieren.")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    cfg = parse(data)
    # Relative template dirs are resolved next to the config file.
    if not Path(cfg.templates_dir).is_absolute():
        cfg.templates_dir = str(path.parent / cfg.templates_dir)
    return cfg
