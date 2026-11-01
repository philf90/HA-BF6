# BF6 Spieler

[![Erstellt mit Claude Code](https://img.shields.io/badge/erstellt%20mit-Claude%20Code-D97757?logo=claude&logoColor=white)](https://claude.com/claude-code)
[![KI-generiert](https://img.shields.io/badge/Code%20%26%20Doku-KI--generiert-6A2BB0)](#ki-hinweis)

Home-Assistant-Integration für Spielerstatistiken aus Battlefield 6: K/D,
Winrate, Waffen, Fahrzeuge, Klassen, Karten, Modi und Rang als Sensoren, dazu
Saison und Portal-Server. Die Daten kommen aus der Community-API
[api.gametools.network](https://api.gametools.network/docs), nicht von EA.
Version 0.1.0.

> **Stand:** Version 0.1.0 ist das Grundgerüst. Die Integration lässt sich
> installieren und der Eintrag „gametools API“ anlegen; Spieler und Sensoren
> gibt es noch nicht. Den Plan zeigt die Recherche in
> [`docs/bf6-api-recherche.html`](docs/bf6-api-recherche.html).

> **KI-Hinweis:** Dieses Projekt entsteht mit Claude Code. Code, Tests und
> Dokumentation schreibt die KI; Details im Abschnitt [KI-Hinweis](#ki-hinweis).

Aufbau, Prüfungen und Karten folgen der Integration
[WoW Charakter](https://github.com/philf90/HA-WOW), Farben und Bausteine der
Karten dem Nachtblau-Stil aus
[philf90/home-assistant](https://github.com/philf90/home-assistant)
(`DESIGN.md`, `design/palette.yaml`).

## Voraussetzungen

- **Home Assistant 2026.2.3 oder neuer**
- **[HACS](https://hacs.xyz)** für die Installation per Klick (ohne HACS geht es
  auch, siehe unten)
- Kein API-Schlüssel: Die gametools API ist ohne Anmeldung erreichbar.

## Installation

[![In HACS öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=philf90&repository=HA-BF6&category=integration)
[![Integration hinzufügen](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=bf6_player)

1. **Integration herunterladen:** Erste Schaltfläche oben → HACS fragt, ob das
   Repository hinzugefügt werden soll → **Hinzufügen** → **Herunterladen**.
   Von Hand: HACS → ⋮ → **Benutzerdefinierte Repositories** →
   `https://github.com/philf90/HA-BF6`, Typ „Integration“ → „BF6 Spieler“
   herunterladen.
   Ohne HACS: Ordner `custom_components/bf6_player` nach
   `config/custom_components/` kopieren.
2. **Home Assistant neu starten.**
3. **Einrichten:** Zweite Schaltfläche oben, oder Einstellungen → Geräte & Dienste
   → Integration hinzufügen → „BF6 Spieler“ → **Absenden**. Es entsteht der
   Eintrag „gametools API“; einen zweiten lehnt der Dialog ab.

## Datenquelle

Battlefield 6 hat keine offizielle, öffentlich dokumentierte Stats-API von EA.
Die Integration nutzt deshalb die Community-API von
[Community Network](https://github.com/community-network) (OpenAPI 1.3.0 unter
<https://api.gametools.network/openapi.json>). Sie braucht keinen Schlüssel,
cacht Antworten 600 Sekunden und nennt kein Abfragelimit. Laut ihrer
Beschreibung stammen die Daten aus den Systemen von EA/DICE. Die Integration
ist kein Produkt von EA, DICE oder Community Network. Fragen zur API:
[Discord von Community Network](https://discord.gg/zMuxW6c); unterstützen:
[GitHub Sponsors](https://github.com/sponsors/community-network).

## Aufbau

- **Haupteintrag „gametools API“** (seit 0.1.0): einmalig, ohne Zugangsdaten.
  Später mit den Optionen für Takte und Gruppen.
- **Untereintrag je Spieler** (geplant): Name suchen, Konto aus der Trefferliste
  wählen. Gespeichert werden Persona-ID, Nucleus-ID und Plattform, weil Namen
  nicht eindeutig sind. Jeder Spieler wird ein eigenes Gerät.
- **Gerät „BF6-Spielwelt“** (geplant): Saison, Battle Pass und Portal-Server.

## Grenzen

- Inoffizielle Datenquelle ohne zugesagte Verfügbarkeit; ändert EA oder
  gametools etwas, können Werte fehlen.
- Keine Match-Historie und kein „spielt gerade“: Die API liefert nur
  Gesamtwerte. Verläufe entstehen erst ab der Installation im Recorder.

## Teststand

Automatische Tests laufen gegen Home Assistant 2026.2.3
(`pytest-homeassistant-custom-component` 0.13.316).

- **0.1.x:** 38 automatische Tests. 0.1.0: Einrichtungsdialog (Anlegen, kein
  zweiter Eintrag), Laden und Entladen, Prüfung der PR-Vorlage und
  Konsistenz von Version, README, Versionshinweisen, Übersetzungen und
  Manifest. Die PR-Prüfung kommt ohne `manifest.json` im Basisstand aus
  (erster PR). Nicht live geprüft.

## Tests

```bash
pip install pytest-homeassistant-custom-component==0.13.316 ruff==0.16.9
ruff check . && ruff format --check .
pytest tests   # pytest.ini setzt asyncio_mode = auto
```

Dieselben Schritte laufen bei jedem Push auf `main` und jedem Pull Request im
Workflow „Pruefung“, zusammen mit hassfest und der HACS-Prüfung.

`tests/test_repo_konsistenz.py` prüft, dass Version, README (auch die Testzahl
oben im Teststand), Versionshinweise, Übersetzungen und Manifest zusammenpassen.

**Pull Requests** folgen der Vorlage `.github/pull_request_template.md`. Der
Workflow „PR-Vorlage“ prüft bei jedem neuen Stand und jeder Änderung der
Beschreibung, dass alle Abschnitte ausgefüllt und alle Punkte der Checkliste
angekreuzt sind (nicht Zutreffendes mit „entfällt: <Grund>“). Ändert ein PR die
Integration, verlangt er eine neue Version in `manifest.json` und
Versionshinweise dazu. Lokal: `PR_BODY="$(cat beschreibung.md)" python3
.github/scripts/pruefe_pr.py`.

**Releases** entstehen mit dem Workflow „Release“ aus einem Tag `v<Version>`
oder von Hand; der Text kommt aus `.github/release-notes/v<Version>.md`.

## KI-Hinweis

Dieses Projekt wird mit [Claude Code](https://claude.com/claude-code) entwickelt,
einem KI-Assistenten von Anthropic. Recherche, Code, Tests und Dokumentation
erstellt die KI im Auftrag und unter Anleitung des Repo-Inhabers. Geprüft wird
mit automatischen Tests (`pytest`) und `ruff`, mit Gegenproben und im Betrieb in
einer echten Home-Assistant-Instanz (Stand im Abschnitt „Teststand“).
Endpunkte und Feldnamen stammen aus der OpenAPI der gametools API und aus
echten Antworten vom 01.11.2026 (siehe `docs/bf6-api-recherche.html`).

## Lizenz

MIT, siehe `LICENSE`.
