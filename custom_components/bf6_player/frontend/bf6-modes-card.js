/*
 * Karte "BF6 Modi": Matches, Siegquote und K/D je Spielmodus eines Spielers.
 *
 *   type: custom:bf6-modes-card
 *   entity: sensor.<spieler>_kills   # leer: erster Spieler
 *   limit: 8                         # hoechstens so viele Modi (Vorgabe 8)
 *
 * Daten: Attribut "modes" des Sensors "Matches" (ohne Sammeleintraege; seit
 * 0.6.0 doppelte Eintraege mit gleichen Zahlen einmal, der zweite Name unter
 * "auch"). Der Balken zeigt den Anteil an den Matches der gezeigten Modi.
 */

const C = await import(new URL(`bf6-common.js${new URL(import.meta.url).search}`, import.meta.url));
const { esc, fmt, prozent, attrListe, grenze, quotenFarbe } = C;

class Bf6ModesCard extends C.Bf6Card {
  static TEXT = {
    de: { title: "BF6 Modi", matches: "Matches", win_rate: "Siegquote", kills: "Kills", also: "auch", none: "Keine Spielmodi in der Statistik." },
    en: { title: "BF6 Modes", matches: "Matches", win_rate: "Win rate", kills: "Kills", also: "also", none: "No game modes in the statistics." },
  };

  static EDITOR = {
    extra: [{ name: "limit", selector: { number: { min: 1, max: 30, mode: "box" } } }],
    labels: { limit: { de: "Höchstens Modi", en: "Maximum modes" } },
  };

  _inhalt() {
    const s = this._spieler();
    if (!s) {
      return this._keinSpieler("mdi:flag-variant");
    }
    const lang = this._lang();
    const kopf = this._spielerKopf(s, "mdi:flag-variant", this._t("title"));
    const modi = attrListe(this._st(s.ids.matches), "modes")
      .filter((m) => (m.matches || 0) > 0)
      .slice(0, grenze(this._config.limit, 8, 1, 30));
    if (!modi.length) {
      return { ...kopf, body: `<div class="hinweis">${esc(this._t("none"))}</div>` };
    }
    const max = Math.max(...modi.map((m) => m.matches));
    const zeilen = modi
      .map((m) => {
        const auch = Array.isArray(m.aliases) && m.aliases.length ? ` · ${this._t("also")} ${m.aliases.join(", ")}` : "";
        const info = `${this._t("win_rate")} ${prozent(m.win_rate, lang)} · K/D\u00a0${fmt(m.kd, lang, 2)} · ${fmt(m.kills, lang)}\u00a0${this._t("kills")}${auch}`;
        return `
          <div class="zeile">
            <span class="zn">${esc(m.name || "–")}</span><span class="zw">${esc(fmt(m.matches, lang))}</span>
            <span class="zi" style="grid-column: 1 / -1"><span class="punkt" style="background:${quotenFarbe(m.win_rate)}"></span>${esc(info)}</span>
            <div class="spur"><i style="width:${Math.round((m.matches / max) * 100)}%"></i></div>
          </div>`;
      })
      .join("");
    return {
      ...kopf,
      body: `<div class="gruppe"><div class="gkopf"><span class="gname"></span><span class="ganz">${esc(this._t("matches"))}</span></div>${zeilen}</div>`,
    };
  }
}

C.registrieren("bf6-modes-card", Bf6ModesCard, "BF6 Modi", "Matches, Siegquote und K/D je Spielmodus eines Battlefield-6-Spielers.");
