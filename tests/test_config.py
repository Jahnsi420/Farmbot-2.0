from pathlib import Path

import pytest
import yaml

from farmbot.config import ConfigError, load, parse

EXAMPLE = Path(__file__).parent.parent / "config.example.yaml"


def test_example_config_loads():
    cfg = load(EXAMPLE)
    assert cfg.slots[0].name == "kobold"
    assert cfg.slots[0].template == "slot_goblin"
    assert cfg.deploy_sides == ["top_left", "top_right"]
    assert cfg.deploy_lines["top_left"] == ((0.115, 0.410), (0.320, 0.135))
    assert set(cfg.loot_regions) == {"gold", "elixir", "dark"}
    assert Path(cfg.templates_dir) == EXAMPLE.parent / "templates"


def _example():
    return yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))


def test_rejects_absolute_pixel_coordinates():
    data = _example()
    data["army"]["slots"][0]["pos"] = [120, 900]
    with pytest.raises(ConfigError, match="relativ"):
        parse(data)


def test_rejects_unknown_deploy_line():
    data = _example()
    data["army"]["deploy_sides"] = ["left"]
    with pytest.raises(ConfigError, match="Absetzlinie"):
        parse(data)


def test_requires_deploy_lines():
    data = _example()
    data["deploy_lines"] = {}
    with pytest.raises(ConfigError):
        parse(data)


def test_requires_slots():
    data = _example()
    data["army"]["slots"] = []
    with pytest.raises(ConfigError):
        parse(data)
