/*
 * Karte "BF6 Spielwelt": laufende Saison und Portal.
 *
 *   type: custom:bf6-world-card
 *
 * Daten: Geraet "BF6-Spielwelt" (Saisonende mit den Attributen season,
 * season_start und battle_pass; Portal-Server, -Spieler und seit 0.7.0 die
 * Warteschlange). Der Balken zeigt,
 * wie viel der Saison vergangen ist; die Restzeit rechnet die Karte bei jedem
 * Zeichnen aus der Uhr des Browsers.
 */

const C = await import(new URL(`bf6-common.js${new URL(import.meta.url).search}`, import.meta.url));
const { esc, fmt, zahl, leer, welt } = C;

const TAG = 86400000;

class Bf6WorldCard extends C.Bf6Card {
  static TEXT = {
    de: {
      title: "BF6 Spielwelt",
      none: "Keine Spielwelt gefunden. Integration „BF6 Spieler“ einrichten.",
      season: "Saison",
      battle_pass: "Battle Pass",
      left: "noch",
      days: "Tage",
      day: "Tag",
      hours: "Std.",
      ended: "beendet",
      unknown: "Keine laufende Saison bekannt.",
      servers: "Portal-Server",
      players: "Portal-Spieler",
      // Weicher Trennstrich: auf schmalen Karten passt das Wort sonst nicht
      queue: "Warte\u00adschlange",
    },
    en: {
      title: "BF6 Game world",
      none: "No game world found. Set up the integration “BF6 Spieler”.",
      season: "Season",
      battle_pass: "Battle Pass",
      left: "",
      days: "days left",
      day: "day left",
      hours: "hours left",
      ended: "ended",
      unknown: "No current season known.",
      servers: "Portal servers",
      players: "Portal players",
      queue: "Queue",
    },
  };

  static EDITOR = { welt: true };

  _ids() {
    const w = welt(this._hass);
    return w ? Object.values(w.ids) : [];
  }

  _datum(ms, lang) {
    return new Date(ms).toLocaleDateString(lang, { day: "2-digit", month: "2-digit", year: "numeric" });
  }

  _rest(ms) {
    const lang = this._lang();
    const vor = this._t("left") ? `${this._t("left")} ` : "";
    if (ms <= 0) {
      return this._t("ended");
    }
    if (ms < TAG) {
      return `${vor}${fmt(Math.ceil(ms / 3600000), lang)}\u00a0${this._t("hours")}`;
    }
    const tage = Math.floor(ms / TAG);
    return `${vor}${fmt(tage, lang)}\u00a0${this._t(tage === 1 ? "day" : "days")}`;
  }

  _inhalt() {
    const w = welt(this._hass);
    const symbol = `<ha-icon icon="mdi:earth"></ha-icon>`;
    if (!w) {
      return { symbol, name: this._t("title"), label: "", body: `<div class="hinweis">${esc(this._t("none"))}</div>` };
    }
    const lang = this._lang();
    const ende = this._st(w.ids.season_end);
    const a = ende?.attributes || {};
    const teile = [];
    let label = "";
    const endeMs = leer(ende) ? NaN : Date.parse(ende.state);
    if (!Number.isNaN(endeMs)) {
      const startMs = Date.parse(a.season_start || "");
      label = [a.season ? `${this._t("season")} ${fmt(a.season, lang)}` : "", a.battle_pass ? `${this._t("battle_pass")} ${fmt(a.battle_pass, lang)}` : ""]
        .filter(Boolean)
        .join(" · ");
      const jetzt = Date.now();
      const anteil = Number.isNaN(startMs) || endeMs <= startMs ? null : Math.max(0, Math.min(1, (jetzt - startMs) / (endeMs - startMs)));
      teile.push(`
        <div class="uk saison">
          <div class="zeile0"><span class="zn">${esc(this._rest(endeMs - jetzt))}</span><span class="zr">${anteil === null ? "" : `${esc(fmt(anteil * 100, lang))}\u00a0%`}</span></div>
          ${anteil === null ? "" : `<div class="fort"><i style="width:${(anteil * 100).toFixed(1)}%"></i></div>`}
          <div class="zeile0"><span class="zi">${Number.isNaN(startMs) ? "" : esc(this._datum(startMs, lang))}</span><span class="zr">${esc(this._datum(endeMs, lang))}</span></div>
        </div>`);
    } else {
      teile.push(`<div class="hinweis">${esc(this._t("unknown"))}</div>`);
    }
    const kacheln = [
      ["servers", zahl(this._st(w.ids.portal_servers))],
      ["players", zahl(this._st(w.ids.portal_players))],
      ["queue", zahl(this._st(w.ids.portal_queue))],
    ]
      .map(([key, n]) => `<div class="uk"><span class="l">${esc(this._t(key))}</span><span class="n">${esc(fmt(n, lang))}</span></div>`)
      .join("");
    teile.push(`<div class="kz">${kacheln}</div>`);
    return { symbol, name: w.name || this._t("title"), label: esc(label), body: teile.join("") };
  }

  static STYLE = `
    .saison { display: grid; gap: 7px; padding: 10px 12px; }
    .zeile0 { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
  `;
}

C.registrieren("bf6-world-card", Bf6WorldCard, "BF6 Spielwelt", "Laufende Battlefield-6-Saison mit Restzeit und Portal-Server.");
