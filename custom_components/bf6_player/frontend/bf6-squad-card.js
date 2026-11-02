/*
 * Karte "BF6 Squad": mehrere Spieler im Vergleich.
 *
 *   type: custom:bf6-squad-card
 *   entities:                        # Entitaeten der Spieler; leer: alle Spieler
 *     - sensor.<spieler_1>_kills
 *     - sensor.<spieler_2>_kills
 *   title: Squad                     # Titel, Vorgabe "BF6 Squad"
 *
 * Je Spieler K/D, KPM und Siegquote, darunter Kills, Matches und Spielzeit.
 * Der beste Wert je Spalte steht im Akzent (Rose), bei Gleichstand bei allen.
 */

const C = await import(new URL(`bf6-common.js${new URL(import.meta.url).search}`, import.meta.url));
const { esc, fmt, prozent, zahl, stunden, gewaehlt, spieler } = C;

const SPALTEN = [
  ["kd", 2],
  ["kpm", 2],
  ["win_rate", 1],
];

class Bf6SquadCard extends C.Bf6Card {
  static TEXT = {
    de: { title: "BF6 Squad", players: "Spieler", kd: "K/D", kpm: "KPM", win_rate: "Sieg %", kills: "Kills", matches: "Matches", hours: "h" },
    en: { title: "BF6 Squad", players: "players", kd: "K/D", kpm: "KPM", win_rate: "Win %", kills: "Kills", matches: "Matches", hours: "h" },
  };

  static EDITOR = {
    name: "entities",
    multiple: true,
    extra: [{ name: "title", selector: { text: {} } }],
    labels: { title: { de: "Titel", en: "Title" } },
  };

  static STYLE = `
    .sq { display: grid; grid-template-columns: minmax(0, 1fr) repeat(3, 54px); gap: 2px 8px; align-items: center; padding: 8px 12px; }
    .sq + .sq { border-top: 1px solid ${C.FARBEN.rand}; }
    .sq .w { justify-self: end; font-size: 14px; font-weight: 750; font-variant-numeric: tabular-nums; white-space: nowrap; }
    .sq .h { justify-self: end; font-size: 12px; color: ${C.FARBEN.sek}; white-space: nowrap; }
    .sq .zi { grid-column: 1 / -1; }
    .sq .zi ha-icon { --mdc-icon-size: 14px; vertical-align: 0.09em; color: ${C.FARBEN.label}; }
    @container (max-width: 327px) { .sq { grid-template-columns: minmax(0, 1fr) repeat(3, 48px); gap: 2px 6px; } }
  `;

  _liste() {
    const eintraege = Array.isArray(this._config?.entities) ? this._config.entities : [];
    if (!eintraege.length) {
      return spieler(this._hass);
    }
    const liste = [];
    for (const id of eintraege) {
      const s = gewaehlt(this._hass, id);
      if (s && !liste.some((x) => x.device === s.device)) {
        liste.push(s);
      }
    }
    return liste;
  }

  _ids() {
    return this._liste().flatMap((s) => Object.values(s.ids));
  }

  _inhalt() {
    const liste = this._liste();
    if (!liste.length) {
      return this._keinSpieler("mdi:account-group");
    }
    const lang = this._lang();
    const werte = liste.map((s) => Object.fromEntries(SPALTEN.map(([key]) => [key, zahl(this._st(s.ids[key]))])));
    const beste = Object.fromEntries(
      SPALTEN.map(([key]) => {
        const zahlen = werte.map((w) => w[key]).filter((n) => n !== null);
        return [key, liste.length > 1 && zahlen.length ? Math.max(...zahlen) : null];
      })
    );
    const kopfzeile = `<div class="sq"><span class="h"></span>${SPALTEN.map(([key]) => `<span class="h">${esc(this._t(key))}</span>`).join("")}</div>`;
    const zeilen = liste
      .map((s, i) => {
        const zellen = SPALTEN.map(([key, stellen]) => {
          const n = werte[i][key];
          const text = key === "win_rate" ? prozent(n, lang, stellen) : fmt(n, lang, stellen);
          return `<span class="w${n !== null && n === beste[key] ? " best" : ""}">${esc(text)}</span>`;
        }).join("");
        const unten = [
          `${fmt(zahl(this._st(s.ids.kills)), lang)}\u00a0${this._t("kills")}`,
          `${fmt(zahl(this._st(s.ids.matches)), lang)}\u00a0${this._t("matches")}`,
          `${fmt(stunden(this._st(s.ids.time_played)), lang)}\u00a0${this._t("hours")}`,
        ];
        return `
          <div class="sq">
            <span class="zn">${esc(s.name)}</span>${zellen}
            <span class="zi">${this._plattform(s)} · ${esc(unten.join(" · "))}</span>
          </div>`;
      })
      .join("");
    return {
      symbol: `<ha-icon icon="mdi:account-group"></ha-icon>`,
      name: this._config.title || this._t("title"),
      label: esc(`${liste.length} ${this._t("players")}`),
      body: `<div class="gruppe">${kopfzeile}${zeilen}</div>`,
    };
  }
}

C.registrieren("bf6-squad-card", Bf6SquadCard, "BF6 Squad", "Mehrere Battlefield-6-Spieler im Vergleich: K/D, KPM, Siegquote.");
