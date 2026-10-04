# Templates

Hier liegen die Button-Bilder, an denen der Bot erkennt, wo er gerade ist.
Sie müssen **auf deinem eigenen Handy** aufgenommen werden, weil sie zur Bildschirmauflösung passen müssen:

```bash
python -m farmbot capture <name>
```

| Name                | Wo im Spiel                                                       | Pflicht |
|---------------------|-------------------------------------------------------------------|---------|
| `attack_button`     | Dorf: „Angriff!“-Button unten links                               | ja      |
| `find_match`        | Angriffsmenü: „Gegner suchen“                                     | ja      |
| `attack_confirm`    | Armee-Übersicht vor der Suche: zweiter „Angriff!“-Button          | nur wenn dein Spiel ihn zeigt |
| `next_button`       | Gegnerische Basis: „Weiter“ unten rechts                          | ja      |
| `slot_goblin`       | Truppenleiste im Kampf: nur das Kobold-Bild, ohne „x320“ und Level | empfohlen |
| `return_home`       | Kampfende: „Nach Hause“                                           | ja      |
| `end_battle`        | Während des Kampfes: „Kampf beenden“                              | nur für `surrender_after` |
| `surrender_confirm` | Bestätigungsdialog „Okay“ beim Aufgeben                           | nur für `surrender_after` |
| eigene Namen        | alle Buttons aus `training.sequence` (z. B. `army_button`, `train_again`, `close_window`) | wenn Training aktiv |

Tipps:
- Nur den Button selbst ausschneiden, möglichst ohne Hintergrund und ohne Zahlen (Kosten ändern sich).
- Mit `python -m farmbot check` prüfst du, welche Templates gerade erkannt werden (Score ≥ threshold).
