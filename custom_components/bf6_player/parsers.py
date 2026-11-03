"""Auswertung der Antworten der gametools API.

Feldnamen aus echten Antworten vom 01. und 02.11.2026 (Schreibweisen der API
wie "loses", "humanPrecentage" bleiben hier gekapselt). Fehlende oder
unpassende Felder ergeben None oder eine leere Liste statt eines Fehlers.

Kennzahlen rechnet die Integration selbst aus den Zaehlern: Die API rechnet
mit unterschiedlichen Zeitbasen (killsPerMinute 1,55 gegenueber
classes[All].kpm 1,96 beim selben Konto).
"""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from .const import IMAGE_HOSTS, NAME_MAX, TOP_COUNT

# Sammeleintraege, die keine einzelne Klasse, Karte oder keinen Modus meinen
# (IDs aus den Antworten vom 01.11.2026).
CLASS_ALL = "kit"
MAP_ALL = "lvlmp"
# "Official" (gm_official) zaehlt alle offiziellen Multiplayer-Matches
# zusammen (223 = Gruppe "Multiplayer" beim selben Konto).
MODE_AGGREGATES = frozenset({"gm_official"})

_SEASON = re.compile(r"^Season(\d+)$")
_BATTLE_PASS = re.compile(r"^BP(\d+)$")
# Nur die Ziffern 0-9: str.isdigit() liesse auch "²" durch, das int() ablehnt
# (ValueError statt None, Review 0.6.8).
_DIGITS = re.compile(r"\d+", re.ASCII)
# Zeitstempel ueber diesem Wert waeren in Sekunden nach dem Jahr 5000; die API
# meint dann Millisekunden (heute liefert sie Sekunden, Stand 02.11.2026).
_MILLISECONDS = 10**11


def _int(value: Any) -> int | None:
    """Ganzzahl auch aus Text ("1000000001"), sonst None; bool zaehlt nicht."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and _DIGITS.fullmatch(text := value.strip()):
        return int(text)
    return None


def _num(value: Any) -> float | None:
    """Endliche Zahl, sonst None (json.loads laesst NaN und Infinity durch)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except OverflowError:
        # int groesser als der Wertebereich von float
        return None
    return number if math.isfinite(number) else None


def ratio(
    numerator: Any, denominator: Any, factor: float = 1, digits: int = 2
) -> float | None:
    """numerator / denominator * factor, gerundet; None ohne gueltigen Nenner."""
    num, den = _num(numerator), _num(denominator)
    if num is None or not den:
        return None
    result = num / den * factor
    # Grenzwerte koennen trotz endlicher Eingaben ueberlaufen (1e308 / 1e-308)
    return round(result, digits) if math.isfinite(result) else None


def _text(value: Any) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


# Zeichen, die in einem Namen nichts zu suchen haben: Steuerzeichen
# (Zeilenumbruch, Nullbyte, Tabulator) und die Richtungszeichen, mit denen
# sich Text in der Anzeige umdrehen laesst (U+202A-U+202E, U+2066-U+2069).
_BIDI = frozenset("\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")


def unsafe_char(char: str) -> bool:
    return unicodedata.category(char) == "Cc" or char in _BIDI


# Zeichen mit Bedeutung in Markdown. Das Frontend zeigt Beschreibungen als
# Markdown (marked, danach filterXSS); ein Name wie "[x](https://...)" wuerde
# sonst zum Link.
_MARKDOWN = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~])")


def markdown_text(text: str) -> str:
    """Text fuer einen Platzhalter in einer Beschreibung, ohne Markdown-Wirkung."""
    return _MARKDOWN.sub(r"\\\1", text)


def valid_name(name: str) -> bool:
    """Eingegebener Name: nicht leer, hoechstens NAME_MAX Zeichen, keine
    Steuer- oder Richtungszeichen. Sonderzeichen sind erlaubt; die Abfrage
    kodiert sie (aiohttp/yarl), es gibt keinen anderen Weg des Namens nach
    aussen.
    """
    return 0 < len(name) <= NAME_MAX and not any(map(unsafe_char, name))


def clean_name(value: Any) -> str | None:
    """Name aus einer API-Antwort fuer Titel und Geraetenamen.

    Die API liefert Namen ungeprueft; Sonderzeichen bleiben, Steuer- und
    Richtungszeichen fallen weg, die Laenge ist auf NAME_MAX begrenzt.
    """
    if not isinstance(value, str):
        return None
    cleaned = "".join(char for char in value if not unsafe_char(char)).strip()
    return cleaned[:NAME_MAX].strip() or None


def image_url(value: Any) -> str | None:
    """Bildadresse nur ueber https von den bekannten Bildservern der API.

    Home Assistant laedt solche Bilder spaeter selbst (Bild-Entitaet); eine
    beliebige Adresse aus der Antwort koennte sonst auf Geraete im eigenen
    Netz zeigen.
    """
    text = _text(value)
    if text is None:
        return None
    try:
        parts = urlsplit(text)
        # .port wirft ValueError bei "abc" oder ausserhalb 0-65535
        port = parts.port
    except ValueError:
        return None
    if parts.scheme != "https" or parts.hostname not in IMAGE_HOSTS:
        return None
    if parts.username or parts.password or port not in (None, 443):
        return None
    return text


def image_problem(value: Any) -> str | None:
    """Warum image_url eine Adresse nicht nimmt; None, wenn sie passt.

    "empty": kein Text oder leer. Beim Beispielkonto der API-Dokumentation
    am 03.11.2026 so bei 2 von 4 Gadgets und 2 von 6 Fahrzeugen.
    "host:<name>": anderer Server als IMAGE_HOSTS. "invalid": sonst.
    """
    if image_url(value) is not None:
        return None
    text = _text(value)
    if text is None:
        return "empty"
    try:
        host = urlsplit(text).hostname
    except ValueError:
        return "invalid"
    if host and host not in IMAGE_HOSTS:
        return f"host:{host}"
    return "invalid"


def missing_images(data: dict[str, Any], limit: int = 15) -> list[dict[str, Any]]:
    """Waffen, Fahrzeuge und Gadgets mit Kills, aber ohne Bild, mit Grund.

    Seit 0.7.1 fuer die Diagnose: Live fehlte das Bild der Frag Grenade
    (Top-Gadget), und aus der Auswertung allein war nicht zu sehen, ob die
    API keine Adresse lieferte oder image_url eine verwarf.
    """
    result = []
    for key, name_key in (
        ("weapons", "weaponName"),
        ("vehicles", "vehicleName"),
        ("gadgets", "gadgetName"),
    ):
        for item in _list(data, key):
            kills = _int(item.get("kills"))
            if not kills or (problem := image_problem(item.get("image"))) is None:
                continue
            result.append(
                {
                    "list": key,
                    "name": _text(item.get(name_key)) or _text(item.get("name")),
                    "kills": kills,
                    "problem": problem,
                }
            )
    result.sort(key=lambda item: item["kills"], reverse=True)
    return result[:limit]


def _datetime(value: Any) -> datetime | None:
    """ISO-Zeit ("2012-09-30T15:52:49Z") oder Sekunden seit 1970."""
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    if (seconds := _int(value)) is not None:
        if seconds > _MILLISECONDS:
            seconds //= 1000
        try:
            return datetime.fromtimestamp(seconds, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    return None


def _list(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = data.get(key)
    return (
        [item for item in value if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


def player_results(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Treffer der Spielersuche (/bf6/player/).

    IDs kommen dort als Text. Treffer ohne gueltige IDs fallen weg.
    """
    results = []
    for item in _list(data or {}, "results"):
        persona_id = _int(item.get("personaId"))
        nucleus_id = _int(item.get("nucleusId"))
        platform = _text(item.get("platform"))
        if persona_id is None or nucleus_id is None or platform is None:
            continue
        results.append(
            {
                "persona_id": persona_id,
                "nucleus_id": nucleus_id,
                "platform": platform,
                "name": clean_name(item.get("displayName"))
                or clean_name(item.get("username")),
                "created": _datetime(item.get("createdAt")),
                "public": item.get("visibility") == "EVERYONE",
            }
        )
    return results


def player_name(data: dict[str, Any] | None, persona_id: int) -> str | None:
    """Name des Kontos mit dieser Persona-ID aus /bf6/player/, sonst None.

    Die Antwort kann weitere Konten derselben Nucleus-ID enthalten (beim
    Beispielkonto am 03.11.2026 EA und Steam mit verschiedenen Namen).
    """
    for account in player_results(data):
        if account["persona_id"] == persona_id:
            return account["name"]
    return None


def _weapon(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": _text(item.get("weaponName")) or _text(item.get("name")),
        "type": _text(item.get("type")),
        "kills": _int(item.get("kills")),
        "accuracy": ratio(item.get("shotsHit"), item.get("shotsFired"), 100),
        "headshot_rate": ratio(item.get("headshotKills"), item.get("kills"), 100),
        "kpm": ratio(item.get("kills"), item.get("timeEquipped"), 60),
        "image": image_url(item.get("image")),
    }


def _vehicle(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": _text(item.get("vehicleName")) or _text(item.get("name")),
        "type": _text(item.get("type")),
        "kills": _int(item.get("kills")),
        "seconds": _int(item.get("timeIn")),
        "image": image_url(item.get("image")),
    }


def _gadget(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": _text(item.get("gadgetName")) or _text(item.get("name")),
        "type": _text(item.get("type")),
        "kills": _int(item.get("kills")),
        "image": image_url(item.get("image")),
    }


def _top(items: list[dict[str, Any]], count: int = TOP_COUNT) -> list[dict[str, Any]]:
    """Die count Eintraege mit den meisten Kills, ohne Eintraege ohne Kill."""
    ranked = [item for item in items if (item.get("kills") or 0) > 0]
    ranked.sort(key=lambda item: item["kills"], reverse=True)
    return ranked[:count]


def classes(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Klassen ohne den Sammeleintrag, nach Spielzeit absteigend."""
    result = []
    for item in _list(data, "classes"):
        if item.get("id") == CLASS_ALL:
            continue
        kills, deaths = item.get("kills"), item.get("deaths")
        result.append(
            {
                "name": _text(item.get("className")) or _text(item.get("name")),
                "kills": _int(kills),
                "deaths": _int(deaths),
                "kd": ratio(kills, deaths),
                "kpm": ratio(kills, item.get("secondsPlayed"), 60),
                "seconds": _int(item.get("secondsPlayed")),
            }
        )
    result.sort(key=lambda item: item["seconds"] or 0, reverse=True)
    return result


def maps(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Karten ohne Sammeleintrag, nach Matches absteigend.

    Doppelte Eintraege mit gleichen Zahlen (am 01.11.2026 "Fort Lyndon" und
    "REDSEC", 28 Matches, 4 Siege) werden zu einem mit "aliases".
    """
    result: list[dict[str, Any]] = []
    seen: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in _list(data, "maps"):
        if item.get("id") == MAP_ALL:
            continue
        name = _text(item.get("mapName")) or _text(item.get("name"))
        wins, losses = _int(item.get("wins")), _int(item.get("losses"))
        matches = _int(item.get("matches"))
        seconds = _int(item.get("secondsPlayed"))
        key = (wins, losses, matches, seconds)
        if matches and key in seen:
            seen[key]["aliases"].append(name)
            continue
        entry = {
            "name": name,
            "aliases": [],
            "matches": matches,
            "wins": wins,
            "losses": losses,
            "win_rate": ratio(wins, matches, 100),
            "seconds": seconds,
        }
        seen[key] = entry
        result.append(entry)
    result.sort(key=lambda item: item["matches"] or 0, reverse=True)
    return result


def modes(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Spielmodi ohne Sammeleintraege, nach Matches absteigend.

    Doppelte Eintraege mit gleichen Zahlen werden wie bei den Karten zu einem
    (am 02.11.2026 "Obliteration" als gm_oblit und gm_oblitall, je 1 Match,
    20 Kills, 12 Tode, 3178 s); ein abweichender Name kommt unter "aliases".
    """
    result: list[dict[str, Any]] = []
    seen: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in _list(data, "gameModes"):
        # Nur Text kann ein Sammeleintrag sein; eine Liste als "id" waere
        # nicht hashbar (TypeError beim Test gegen das frozenset).
        if isinstance(item.get("id"), str) and item["id"] in MODE_AGGREGATES:
            continue
        name = _text(item.get("gamemodeName"))
        kills, deaths = _int(item.get("kills")), _int(item.get("deaths"))
        wins, losses = _int(item.get("wins")), _int(item.get("losses"))
        matches = _int(item.get("matches"))
        key = (matches, wins, losses, kills, deaths, _int(item.get("secondsPlayed")))
        if matches and key in seen:
            first = seen[key]
            if name and name != first["name"] and name not in first["aliases"]:
                first["aliases"].append(name)
            continue
        entry = {
            "name": name,
            "aliases": [],
            "matches": matches,
            "wins": wins,
            "losses": losses,
            "win_rate": ratio(wins, matches, 100),
            "kills": kills,
            "kd": ratio(kills, deaths),
        }
        seen[key] = entry
        result.append(entry)
    result.sort(key=lambda item: item["matches"] or 0, reverse=True)
    return result


def player_stats(data: dict[str, Any] | None) -> dict[str, Any]:
    """Kennzahlen eines Kontos aus /bf6/stats/.

    has_results ist False, wenn die API zu den IDs nichts kennt: Unbekannte
    IDs liefern HTTP 200 mit hasResults = false und lauter Nullen.
    """
    data = data or {}
    kills, deaths = data.get("kills"), data.get("deaths")
    matches, seconds = data.get("matchesPlayed"), data.get("secondsPlayed")
    divided = data.get("dividedKills")
    human_kills = divided.get("human") if isinstance(divided, dict) else None
    xp = _list(data, "XP")
    class_list = classes(data)
    return {
        "has_results": data.get("hasResults") is True,
        "kills": _int(kills),
        "deaths": _int(deaths),
        "assists": _int(data.get("assists")),
        "revives": _int(data.get("revives")),
        "wins": _int(data.get("wins")),
        "losses": _int(data.get("loses")),
        "matches": _int(matches),
        "seconds_played": _int(seconds),
        "score": _int(data.get("score")),
        "xp": _int(xp[0].get("total")) if xp else None,
        "kd": ratio(kills, deaths),
        "kpm": ratio(kills, seconds, 60),
        "win_rate": ratio(data.get("wins"), matches, 100),
        "accuracy": ratio(data.get("shotsHit"), data.get("shotsFired"), 100),
        "headshot_rate": ratio(data.get("headShots"), kills, 100),
        "human_kill_rate": ratio(human_kills, kills, 100),
        "weapons": _top([_weapon(item) for item in _list(data, "weapons")]),
        "vehicles": _top([_vehicle(item) for item in _list(data, "vehicles")]),
        "gadgets": _top([_gadget(item) for item in _list(data, "gadgets")]),
        "classes": class_list,
        "favorite_class": class_list[0]["name"]
        if class_list and class_list[0]["seconds"]
        else None,
        "maps": maps(data),
        "modes": modes(data),
        "missing_images": missing_images(data),
    }


def _reduced_profile(data: dict[str, Any]) -> dict[str, Any] | None:
    """Verkuerzte Antwort von /bf6/profile/ oder None.

    Live am 02.11.2026 bei einem privaten Konto: statt "playerProfiles"
    kommt {"other": [{"playerProfiles": [{"rank", "rankName", "rankImage",
    "badges"}]}]}, flach und ohne Dog Tags, badgeSummary und Ranked-Rang.
    """
    for other in _list(data, "other"):
        profiles = _list(other, "playerProfiles")
        if profiles:
            return profiles[0]
    return None


def player_profile(data: dict[str, Any] | None) -> dict[str, Any]:
    """Rang, Dog Tags, Abzeichen und Ranked-Rang aus /bf6/profile/.

    Aus der verkuerzten Antwort (privates Konto) kommen nur Rang, Rangname
    und Rang-Bild. Ihr flaches Feld "badges" bleibt ungenutzt: Es heisst wie
    playerCard.badges, und das entsprach beim Abgleich am 02.11.2026 nicht
    der Zahl im Spiel (120 statt 48).
    """
    profiles = _list(data or {}, "playerProfiles")
    profile = profiles[0] if profiles else {}
    card = profile.get("playerCard")
    card = card if isinstance(card, dict) else {}
    if not profiles and (reduced := _reduced_profile(data or {})) is not None:
        images = reduced.get("rankImage")
        images = images if isinstance(images, dict) else {}
        return {
            "rank": _int(reduced.get("rank")),
            "rank_name": _text(reduced.get("rankName")),
            "rank_image": image_url(images.get("large")),
            "dog_tags": None,
            "badges": None,
            "ranked": [],
        }
    images = card.get("rankImage")
    images = images if isinstance(images, dict) else {}
    tags = profile.get("totalDogTags")
    badges = profile.get("badgeSummary")
    return {
        "rank": _int(card.get("rank")),
        "rank_name": _text(profile.get("rankName")),
        "rank_image": image_url(images.get("large")),
        "dog_tags": _int(tags.get("intValue")) if isinstance(tags, dict) else None,
        "badges": _int(badges.get("totalBadges")) if isinstance(badges, dict) else None,
        "ranked": [
            {
                "season": _text(item.get("type")),
                "mode": _text(item.get("modeName")),
                "rank": _text(item.get("rankName")),
            }
            for item in _list(profile, "competitiveRanks")
        ],
    }


def _event_window(event: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    window = event.get("validUntil")
    window = window if isinstance(window, dict) else {}

    def edge(key: str) -> datetime | None:
        value = window.get(key)
        return _datetime(value.get("value")) if isinstance(value, dict) else None

    return edge("start"), edge("end")


def season(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Laufende Saison und Battle Pass aus /bf6/gameevents/.

    Am 02.11.2026: "Season5" und "BP05", beide aktiv vom 13.10.2026 bis
    19.01.2027 (Feld validUntil.start.value / end.value in Sekunden).
    """
    current = None
    battle_pass = None
    for event in _list(data or {}, "events"):
        name = event.get("name")
        if event.get("active") is not True or not isinstance(name, str):
            continue
        if (match := _SEASON.match(name)) and current is None:
            start, end = _event_window(event)
            current = {"number": int(match.group(1)), "start": start, "end": end}
        elif (match := _BATTLE_PASS.match(name)) and battle_pass is None:
            battle_pass = int(match.group(1))
    if current is None:
        return None
    return {**current, "battle_pass": battle_pass}


def portal_status(data: dict[str, Any] | None) -> dict[str, Any]:
    """Server, Spieler und Warteschlange aller Portal-Regionen (/bf6/status/)."""
    regions = (data or {}).get("regions")
    total = regions.get("ALL") if isinstance(regions, dict) else None
    amounts = total.get("amounts") if isinstance(total, dict) else None
    amounts = amounts if isinstance(amounts, dict) else {}
    return {
        "servers": _int(amounts.get("serverAmount")),
        "players": _int(amounts.get("soldierAmount")),
        "queue": _int(amounts.get("queueAmount")),
    }
