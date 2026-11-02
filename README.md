# BF6 Spieler

[![Erstellt mit Claude Code](https://img.shields.io/badge/erstellt%20mit-Claude%20Code-D97757?logo=claude&logoColor=white)](https://claude.com/claude-code)
[![KI-generiert](https://img.shields.io/badge/Code%20%26%20Doku-KI--generiert-6A2BB0)](#ki-hinweis)

Home-Assistant-Integration für Spielerstatistiken aus Battlefield 6: K/D,
Winrate, Waffen, Fahrzeuge, Klassen, Karten, Modi und Rang als Sensoren, dazu
Saison und Portal-Server. Die Daten kommen aus der Community-API
[api.gametools.network](https://api.gametools.network/docs), nicht von EA.
Version 0.3.1.

> **Stand:** Version 0.3.1: Spieler lassen sich am Eintrag „gametools API“
> hinzufügen (siehe [Installation](#installation)). Geräte und Sensoren je
> Spieler gibt es noch nicht; sie kommen mit 0.4.0. Den Plan zeigt die Recherche in
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
4. **Spieler hinzufügen** (seit 0.3.0): Einstellungen → Geräte & Dienste →
   BF6 Spieler → beim Eintrag „gametools API“ **Spieler hinzufügen**.
   Spielernamen eingeben, so wie er in Battlefield 6 steht (EA-Name, Steam-,
   PlayStation- oder Xbox-Name), höchstens 64 Zeichen; Sonderzeichen sind
   erlaubt (siehe [Sicherheit](#sicherheit)). Die Liste zeigt alle Konten mit diesem Namen,
   die noch nicht eingerichtet sind, je Zeile Name, Plattform und das Datum, an
   dem das Konto angelegt wurde; 🔒 kennzeichnet ein nicht öffentliches Konto.
   Das richtige Konto wählen. Vor dem Anlegen fragt die Integration die
   Statistik ab; kennt die API zu dem Konto keine BF6-Werte, meldet der Dialog
   das und legt nichts an. Gespeichert werden Persona-ID, Nucleus-ID und
   Plattform, nicht der Name: Namen sind nicht eindeutig (am 01.11.2026 zwei
   Steam-Konten mit demselben Namen und völlig anderen Werten). In der Liste
   heißt der Spieler „Name · Plattform“, z. B. „Testspieler · Steam“ (seit
   0.3.1); ein eigenes Symbol je Spieler zeigt Home Assistant dort nicht an.

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
- **Untereintrag je Spieler** (seit 0.3.0): Name suchen, Konto aus der
  Trefferliste wählen. Gespeichert werden Persona-ID, Nucleus-ID und Plattform,
  weil Namen nicht eindeutig sind. Ab 0.4.0 wird jeder Spieler ein eigenes
  Gerät.
- **Plattform-Symbole** (geplant ab 0.4.0, für Entitäten und Karten): Home
  Assistant bringt MDI 7.4.47 mit; darin gibt es `mdi:steam`,
  `mdi:sony-playstation`, `mdi:microsoft-xbox` und `mdi:microsoft-windows`.
  Für EA app und Epic Games gibt es dort kein Symbol.
- **Gerät „BF6-Spielwelt“** (geplant): Saison, Battle Pass und Portal-Server.

## Abfragen und Auswertung

Seit 0.2.0 (`api.py`, `parsers.py`), noch ohne Entitäten. Abgefragt wird immer
per ID, nie per Name:

| Endpunkt | Parameter | Auswertung |
|---|---|---|
| `/bf6/player/` | `name`, `limit` | Konten mit Persona-ID, Nucleus-ID, Plattform, Name, Erstellungsdatum, öffentlich ja/nein |
| `/bf6/stats/` | `playerid`, `nucleus_id`, `platform`, `format_values=false`, `seperation` | Kennzahlen, Top 5 Waffen, Fahrzeuge und Gadgets, Klassen, Karten, Modi |
| `/bf6/profile/` | `playerid`, `nucleus_id`, `platform` | Rang, Rangname, Rang-Bild, Dog Tags, Abzeichen, Ranked-Rang |
| `/bf6/gameevents/` | – | Laufende Saison mit Start und Ende, Battle Pass |
| `/bf6/status/` | – | Server, Spieler und Warteschlange der Portal-Server |

- **Selbst gerechnet** aus den Zählern: K/D (Kills ÷ Deaths), KPM (Kills ÷
  Spielminuten), Winrate (Siege ÷ Matches), Accuracy (Treffer ÷ Schüsse),
  Headshot-Quote (Headshots ÷ Kills) und Anteil der Kills gegen Menschen. Die
  API rechnet mit unterschiedlichen Zeitbasen (KPM 1,55 oben, 1,96 bei den
  Klassen desselben Kontos). Gegen echte Antworten vom 01.11.2026 geprüft:
  alle sechs Werte gleich den Werten der API.
- **Unbekannte IDs** liefern HTTP 200 mit `hasResults: false` und lauter
  Nullen, keinen Fehler. Daraus wird `has_results`.
- **Sammeleinträge** fallen weg: Klasse „All“ (`kit`), Karte „All“ (`lvlmp`),
  Modus „Official“ (`gm_official`, alle offiziellen Matches zusammen).
- **Doppelte Karten** mit gleichen Zahlen werden zusammengelegt, der zweite
  Name steht unter `aliases` (am 01.11.2026 „Fort Lyndon“ und „REDSEC“).
- **Fehler:** HTTP 404 → nicht gefunden, HTTP 429 → Abfragelimit, andere
  Statuscodes, Zeitüberschreitung (30 s), Verbindungsfehler und Antworten ohne
  JSON-Objekt → allgemeiner Fehler.

## Sicherheit

Spielernamen dürfen beliebige Sonderzeichen enthalten. Der Name ist für die
Integration reiner Text und wird nie als Code ausgeführt (kein `eval`, keine
Shell, keine Datenbank-Abfrage, kein Template); geprüft am 02.11.2026:

| Weg des Namens | Schutz |
|---|---|
| Eingabe im Dialog | 1 bis 64 Zeichen nach Entfernen von Leerzeichen am Rand; Zeilenumbrüche, Nullbyte, Tabulator und andere Steuerzeichen sowie Richtungszeichen (U+202A–U+202E, U+2066–U+2069) lehnt der Dialog ab, ohne die API zu fragen |
| Abfrage an die API | nur als Parameter `name` an den festen Pfad `/bf6/player/`; aiohttp kodiert ihn (`&` → `%26`, `#` → `%23`, `%` → `%25`). Getestet mit `&limit=…`, `#`, `../`, `%2F%00`, HTML, SQL und Unicode: Pfad und `limit` bleiben unverändert |
| Text im Dialog | Das Frontend zeigt Beschreibungen als Markdown und filtert HTML danach mit `filterXSS`; Links ließe es durch. Der Name im Text „Konto wählen“ wird deshalb mit `\` vor jedem Markdown-Zeichen eingesetzt |
| Auswahlliste, Titel | Das Frontend setzt Beschriftungen als Text ein (Lit), nicht als HTML |
| Name aus der API-Antwort | Steuer- und Richtungszeichen entfernt, höchstens 64 Zeichen, bevor er Titel des Spielers wird |
| Bildadressen aus der API | nur `https://cdn.gametools.network/…` ohne Benutzer, Passwort und fremden Port; alles andere wird verworfen, damit Home Assistant keine Adressen im eigenen Netz abruft |

Für die späteren Karten gilt wie bei WoW Charakter: Jeder Text aus Entitäten
wird vor dem Einsetzen in HTML maskiert. Namen erscheinen nicht im Log.

## Grenzen

- Inoffizielle Datenquelle ohne zugesagte Verfügbarkeit; ändert EA oder
  gametools etwas, können Werte fehlen.
- Keine Match-Historie und kein „spielt gerade“: Die API liefert nur
  Gesamtwerte. Verläufe entstehen erst ab der Installation im Recorder.

## Teststand

Automatische Tests laufen gegen Home Assistant 2026.2.3
(`pytest-homeassistant-custom-component` 0.13.316).

- **0.3.x:** 120 automatische Tests. 0.3.1: Plattform im Titel neuer und
  alter Spieler, umbenannte Spieler bleiben (2 Tests). 0.3.0 **live geprüft**
  (02.11.2026, iOS-App, Home Assistant 2026.10.4): Installation über HACS als
  v0.3.0, Symbol angezeigt, ein Steam-Spieler mit Sonderzeichen im Namen
  hinzugefügt und korrekt angezeigt. 0.3.0: Dialog „Spieler hinzufügen“
  (Suche, Auswahl, Prüfung der Statistik, schon eingerichtete Konten, keine
  Treffer, 404, Verbindungsfehler, Eintrag nicht geladen, Zeile der
  Auswahlliste) und [Sicherheit](#sicherheit) (ungültige Namen, Sonderzeichen
  im Parameter, Markdown im Dialogtext, bereinigte Namen aus der API, nur
  erlaubte Bildadressen). Ein Test fand dabei einen Fehler vor dem Commit: Bei HTTP 404
  der Suche blieb der Dialog ohne Meldung stehen. Gegenprobe: Filter für schon
  eingerichtete Konten, Prüfung auf `hasResults`, Kürzen des Namens, Prüfung
  auf geladenen Eintrag, Prüfung des Namens, Maskieren von Markdown,
  Bereinigen der API-Namen und Prüfung der Bildadressen einzeln entfernt – jedes Mal schlug ein Test
  fehl. Nicht live in Home Assistant geprüft.
- **0.2.x:** 72 automatische Tests. 0.2.0: API-Client (Parameter, Fehler
  404/429/5xx, kein JSON, Zeitüberschreitung, Verbindungsfehler) und
  Auswertung mit erfundenen Werten im Aufbau echter Antworten. Gegenprobe:
  Prüfung auf `hasResults`, Zusammenlegen doppelter Karten, Parameter
  `format_values=false` und Filter für „Official“ einzeln entfernt – jedes
  Mal schlug ein Test fehl. Zusätzlich gegen echte Antworten vom 01. und
  02.11.2026 laufen lassen. Nicht live in Home Assistant geprüft.
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
