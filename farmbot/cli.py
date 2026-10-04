"""Command line interface: `python -m farmbot <command>`."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from farmbot import imaging
from farmbot.adb import AdbError, Device
from farmbot.bot import Bot, BotError
from farmbot.config import ConfigError, load
from farmbot.deploy import spread, to_pixels
from farmbot.digits import digit_mask, read_number
from farmbot.vision import Templates, crop_rel

log = logging.getLogger("farmbot")


def _device(args) -> Device:
    serial, adb_path = args.serial, "adb"
    if Path(args.config).exists():
        cfg = load(args.config)
        serial = serial or cfg.serial
        adb_path = cfg.adb_path
    return Device(serial, adb_path)


def _screen(args):
    _wait(args)
    if getattr(args, "image", None):
        img = imaging.imread(args.image)
        if img is None:
            raise SystemExit(f"Bild {args.image} konnte nicht gelesen werden.")
        return img
    return _device(args).screenshot()


def _wait(args) -> None:
    """Give the user time to switch from the terminal (e.g. Termux) to the game."""
    if getattr(args, "delay", 0) and not getattr(args, "image", None):
        print(f"Screenshot in {args.delay:.0f}s – jetzt zu Clash of Clans wechseln …")
        time.sleep(args.delay)


def cmd_devices(args) -> None:
    devices = Device(adb_path="adb").list_devices()
    print("\n".join(devices) if devices else "Keine Geräte verbunden.")


def cmd_screenshot(args) -> None:
    _wait(args)
    img = _device(args).screenshot()
    imaging.imwrite(args.output, img)
    print(f"Gespeichert: {args.output} ({img.shape[1]}x{img.shape[0]})")


def cmd_capture(args) -> None:
    img = _screen(args)
    if args.box:
        x1, y1, x2, y2 = (int(v) for v in args.box.split(","))
    else:
        print("Bereich mit der Maus markieren, dann ENTER/LEERTASTE drücken (C = abbrechen).")
        try:
            import cv2

            # OpenCV works in BGR, our images are RGB
            x, y, w, h = cv2.selectROI("Template auswählen", img[:, :, ::-1], showCrosshair=True)
            cv2.destroyAllWindows()
        except Exception:  # no OpenCV or no GUI (e.g. Termux)
            imaging.imwrite("screenshot.png", img)
            raise SystemExit(
                "Keine grafische Oberfläche (z. B. Termux) – Maus-Auswahl nicht möglich.\n"
                f"Screenshot gespeichert: screenshot.png ({img.shape[1]}x{img.shape[0]}).\n"
                "Bereich stattdessen in Pixeln angeben, z. B.:\n"
                f"  python -m farmbot capture {args.name} --image screenshot.png --box 100,800,300,950\n"
                "Tipp: Entwickleroptionen → 'Zeigerposition' zeigt beim Antippen X/Y oben am Bildschirm."
            ) from None
        if w == 0 or h == 0:
            raise SystemExit("Abgebrochen.")
        x1, y1, x2, y2 = x, y, x + w, y + h
    templates_dir = load(args.config).templates_dir if Path(args.config).exists() else "templates"
    out = Path(templates_dir) / f"{args.name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    imaging.imwrite(out, img[y1:y2, x1:x2])
    print(f"Template gespeichert: {out} ({x2 - x1}x{y2 - y1})")


def cmd_test_loot(args) -> None:
    cfg = load(args.config)
    img = _screen(args)
    out = Path(args.debug_dir)
    out.mkdir(parents=True, exist_ok=True)
    for res, region in cfg.loot_regions.items():
        crop = crop_rel(img, region)[0]
        imaging.imwrite(out / f"loot_{res}.png", crop)
        imaging.imwrite(out / f"loot_{res}_mask.png", (~digit_mask(crop)).astype("uint8") * 255)
        print(f"{res:7s}: {read_number(crop)}")
    print(f"Ausschnitte gespeichert in {out}/")


def cmd_check(args) -> None:
    """Show which templates are visible on the current screen."""
    cfg = load(args.config)
    img = _screen(args)
    templates = Templates(cfg.templates_dir, cfg.threshold, cfg.reference_width)
    print(f"Bildgröße: {img.shape[1]}x{img.shape[0]}"
          + (f" (Templates für Breite {cfg.reference_width})" if cfg.reference_width else ""))
    for path in sorted(Path(cfg.templates_dir).glob("*.png")):
        match = templates.find(img, path.stem, threshold=0.0)
        hit = match and match.score >= cfg.threshold
        print(f"{'✔' if hit else '·'} {path.stem:20s} Score {match.score if match else 0:.3f}")


def cmd_show_deploy(args) -> None:
    """Draw deploy lines and points, troop slots and loot regions onto a screenshot."""
    from PIL import Image, ImageDraw

    cfg = load(args.config)
    img = Image.fromarray(_screen(args))
    draw = ImageDraw.Draw(img)
    w, h = img.size
    px = lambda p: (int(p[0] * w), int(p[1] * h))  # noqa: E731
    lines = to_pixels(cfg.deploy_lines, w, h, cfg.line_shift)
    for name, (a, b) in lines.items():
        draw.line([a, b], fill=(255, 255, 0), width=3)
        draw.text((a[0] + 8, a[1]), name, fill=(255, 255, 0))
    for slot in cfg.slots:
        n = min(cfg.deploy_points, slot.count) or slot.count
        for x, y in spread(lines, slot.sides or cfg.deploy_sides, n):
            draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill=(255, 0, 0))
        x, y = px(slot.pos)
        draw.ellipse((x - 14, y - 14, x + 14, y + 14), outline=(255, 0, 255), width=3)
        draw.text((x - 30, y - 34), slot.name, fill=(255, 0, 255))
    for res, (x1, y1, x2, y2) in cfg.loot_regions.items():
        draw.rectangle((*px((x1, y1)), *px((x2, y2))), outline=(0, 255, 0), width=2)
        draw.text((px((x2, y1))[0] + 5, px((x2, y1))[1]), res, fill=(0, 255, 0))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    img.save(args.output)
    print(f"Kalibrierungsbild gespeichert: {args.output}")


def cmd_run(args) -> None:
    cfg = load(args.config)
    if args.max_attacks is not None:
        cfg.max_attacks = args.max_attacks
    device = Device(args.serial or cfg.serial, cfg.adb_path)
    bot = Bot(cfg, device, debug_dir=Path(args.debug_dir) if args.debug else None)
    try:
        bot.run()
    except KeyboardInterrupt:
        log.info("Gestoppt nach %d Angriffen.", bot.attacks)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="farmbot", description="Clash of Clans Farm-Bot über ADB")
    p.add_argument("-c", "--config", default="config.yaml", help="Pfad zur Konfiguration")
    p.add_argument("-s", "--serial", help="ADB-Seriennummer des Geräts")
    p.add_argument("-v", "--verbose", action="store_true", help="Ausführliches Log")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("devices", help="Verbundene Geräte anzeigen").set_defaults(func=cmd_devices)

    s = sub.add_parser("screenshot", help="Screenshot vom Handy speichern")
    s.add_argument("output", nargs="?", default="screenshot.png")
    s.add_argument("-d", "--delay", type=float, default=0, help="Sekunden warten vor dem Screenshot")
    s.set_defaults(func=cmd_screenshot)

    s = sub.add_parser("capture", help="Button-Template aufnehmen")
    s.add_argument("name", help="Name des Templates, z. B. attack_button")
    s.add_argument("--image", help="Vorhandenen Screenshot statt Live-Bild verwenden")
    s.add_argument("--box", help="Bereich in Pixeln x1,y1,x2,y2 (statt Maus-Auswahl)")
    s.add_argument("-d", "--delay", type=float, default=0, help="Sekunden warten vor dem Screenshot")
    s.set_defaults(func=cmd_capture)

    for name, func, helptext in (
        ("test-loot", cmd_test_loot, "Beute-Erkennung auf dem aktuellen Bild testen"),
        ("check", cmd_check, "Prüfen, welche Templates gerade sichtbar sind"),
        ("show-deploy", cmd_show_deploy, "Absetzpunkte, Slots und Beute-Bereiche einzeichnen"),
    ):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("--image", help="Vorhandenen Screenshot statt Live-Bild verwenden")
        s.add_argument("--debug-dir", default="debug")
        s.add_argument("-o", "--output", default="debug/calibration.png")
        s.add_argument("-d", "--delay", type=float, default=0, help="Sekunden warten vor dem Screenshot")
        s.set_defaults(func=func)

    s = sub.add_parser("run", help="Bot starten")
    s.add_argument("-n", "--max-attacks", type=int, help="Anzahl Angriffe (überschreibt Konfig)")
    s.add_argument("--debug", action="store_true", help="Screenshots bei Fehlern speichern")
    s.add_argument("--debug-dir", default="debug")
    s.set_defaults(func=cmd_run)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        args.func(args)
    except (AdbError, BotError, ConfigError, FileNotFoundError) as e:
        log.error("%s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
