/*
 * Karte "BF6 Karten": Siegquote je Karte eines Spielers.
 *
 *   type: custom:bf6-maps-card
 *   entity: sensor.<spieler>_kills   # leer: erster Spieler
 *   min_matches: 3                   # nur Karten mit mindestens so vielen Matches (Vorgabe 1)
 *   limit: 10                        # hoechstens so viele Karten (Vorgabe 10)
 *   sort: matches                    # matches (Vorgabe) oder win_rate
 *
 * Daten: Attribut "maps" des Sensors "Matches" (ohne Sammeleintrag; doppelte
 * Eintraege der API mit gleichen Zahlen stehen einmal, der zweite Name unter
 * "auch"). Farbe der Quote: ab 55 % Gruen, ab 45 % Amber, darunter Rot; der
 * Wert steht immer als Zahl daneben.
 */

const C = await import(new URL(`bf6-common.js${new URL(import.meta.url).search}`, import.meta.url));
const { esc, fmt, prozent, attrListe, grenze, quotenFarbe } = C;

class Bf6MapsCard extends C.Bf6Card {
  static TEXT = {
    de: {
      title: "BF6 Karten",
      matches: "Matches",
      wins: "S",
      losses: "N",
      also: "auch",
      none: "Keine Karte mit genug Matches.",
      sort_matches: "Matches",
      sort_win_rate: "Siegquote",
    },
    en: {
      title: "BF6 Maps",
      matches: "Matches",
      wins: "W",
      losses: "L",
      also: "also",
      none: "No map with enough matches.",
      sort_matches: "Matches",
      sort_win_rate: "Win rate",
    },
  };

  static EDITOR = {
    extra: (lang) => [
      { name: "min_matches", selector: { number: { min: 1, max: 1000, mode: "box" } } },
      { name: "limit", selector: { number: { min: 1, max: 50, mode: "box" } } },
      {
        name: "sort",
        selector: {
          select: {
            mode: "dropdown",
            options: ["matches", "win_rate"].map((value) => ({
              value,
              label: (Bf6MapsCard.TEXT[lang] || Bf6MapsCard.TEXT.en)[`sort_${value}`],
            })),
          },
        },
      },
    ],
    labels: {
      min_matches: { de: "Mindestens Matches", en: "Minimum matches" },
      limit: { de: "Höchstens Karten", en: "Maximum maps" },
      sort: { de: "Sortierung", en: "Sort by" },
    },
  };

  static getStubConfig() {
    return { min_matches: 1, limit: 10 };
  }

  _inhalt() {
    const s = this._spieler();
    if (!s) {
      return this._keinSpieler("mdi:map");
    }
    const lang = this._lang();
    const min = grenze(this._config.min_matches, 1, 1, 100000);
    const limit = grenze(this._config.limit, 10, 1, 50);
    let karten = attrListe(this._st(s.ids.matches), "maps").filter((k) => (k.matches || 0) >= min);
    if (this._config.sort === "win_rate") {
      karten = [...karten].sort((a, b) => (b.win_rate ?? -1) - (a.win_rate ?? -1) || (b.matches || 0) - (a.matches || 0));
    }
    const kopf = this._spielerKopf(s, "mdi:map", this._t("title"));
    if (!karten.length) {
      return { ...kopf, body: `<div class="hinweis">${esc(this._t("none"))}</div>` };
    }
    const zeilen = karten
      .slice(0, limit)
      .map((k) => {
        const farbe = quotenFarbe(k.win_rate);
        const auch = Array.isArray(k.aliases) && k.aliases.length ? ` · ${this._t("also")} ${k.aliases.join(", ")}` : "";
        const info = `${fmt(k.matches, lang)}\u00a0${this._t("matches")} · ${fmt(k.wins, lang)}\u00a0${this._t("wins")} / ${fmt(k.losses, lang)}\u00a0${this._t("losses")}${auch}`;
        const breite = Math.max(0, Math.min(100, k.win_rate || 0));
        return `
          <div class="zeile">
            <span class="zn">${esc(k.name || "–")}</span><span class="zw" style="color:${farbe}">${esc(prozent(k.win_rate, lang))}</span>
            <span class="zi" style="grid-column: 1 / -1">${esc(info)}</span>
            <div class="spur"><i style="width:${breite}%;background:${farbe}"></i></div>
          </div>`;
      })
      .join("");
    return { ...kopf, body: `<div class="gruppe">${zeilen}</div>` };
  }
}

C.registrieren("bf6-maps-card", Bf6MapsCard, "BF6 Karten", "Siegquote je Karte eines Battlefield-6-Spielers.");
