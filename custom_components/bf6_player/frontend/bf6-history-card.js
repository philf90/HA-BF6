/*
 * Karte "BF6 Verlauf": Langzeitstatistik eines Werts eines Spielers.
 *
 *   type: custom:bf6-history-card
 *   entity: sensor.<spieler>_kills   # leer: erster Spieler
 *   metric: kd                       # kd, kpm, win_rate, accuracy, headshot_rate, rank,
 *                                    # kills, matches, wins, xp, time_played
 *   period: day                      # day, week oder month
 *   days: 30                         # Zeitraum in Tagen, 7 bis 365
 *
 * Die API liefert keinen Verlauf; die Karte liest die Langzeitstatistik von
 * Home Assistant (recorder/statistics_during_period). Quoten (measurement)
 * als Linie des Mittelwerts je Zeitraum, Zaehler (total_increasing) als
 * Balken des Zuwachses je Zeitraum (z. B. Kills pro Tag). Werte erscheinen
 * beim Ueberfahren mit der Maus (SVG-Titel); darunter stehen Start, Ende,
 * kleinster und groesster Wert als Text.
 */

const C = await import(new URL(`bf6-common.js${new URL(import.meta.url).search}`, import.meta.url));
const { esc, fmt, FARBEN, grenze } = C;

const TAG = 86400000;
// Wert -> [Art, Nachkommastellen, Prozent]
const WERTE = {
  kd: ["mean", 2, false],
  kpm: ["mean", 2, false],
  win_rate: ["mean", 1, true],
  accuracy: ["mean", 1, true],
  headshot_rate: ["mean", 1, true],
  rank: ["mean", 0, false],
  kills: ["change", 0, false],
  matches: ["change", 0, false],
  wins: ["change", 0, false],
  xp: ["change", 0, false],
  time_played: ["change", 1, false],
};
const ZEITRAEUME = ["day", "week", "month"];

class Bf6HistoryCard extends C.Bf6Card {
  static TEXT = {
    de: {
      title: "BF6 Verlauf",
      kd: "K/D",
      kpm: "KPM",
      win_rate: "Siegquote",
      accuracy: "Treffergenauigkeit",
      headshot_rate: "Headshot-Quote",
      rank: "Rang",
      kills: "Kills",
      matches: "Matches",
      wins: "Siege",
      xp: "XP",
      time_played: "Spielzeit",
      day: "pro Tag",
      week: "pro Woche",
      month: "pro Monat",
      mean_day: "Mittel je Tag",
      mean_week: "Mittel je Woche",
      mean_month: "Mittel je Monat",
      days: "Tage",
      loading: "Lade Langzeitstatistik …",
      none: "Noch keine Langzeitstatistik. Home Assistant bildet sie stündlich; nach einigen Stunden erscheinen die ersten Werte.",
      error: "Langzeitstatistik nicht lesbar",
      min: "min.",
      max: "max.",
      sum: "Summe",
    },
    en: {
      title: "BF6 History",
      kd: "K/D",
      kpm: "KPM",
      win_rate: "Win rate",
      accuracy: "Accuracy",
      headshot_rate: "Headshot rate",
      rank: "Rank",
      kills: "Kills",
      matches: "Matches",
      wins: "Wins",
      xp: "XP",
      time_played: "Time played",
      day: "per day",
      week: "per week",
      month: "per month",
      mean_day: "daily mean",
      mean_week: "weekly mean",
      mean_month: "monthly mean",
      days: "days",
      loading: "Loading long-term statistics …",
      none: "No long-term statistics yet. Home Assistant compiles them hourly; the first values appear after a few hours.",
      error: "Long-term statistics not readable",
      min: "min.",
      max: "max.",
      sum: "Total",
    },
  };

  static EDITOR = {
    extra: (lang) => {
      const t = Bf6HistoryCard.TEXT[lang] || Bf6HistoryCard.TEXT.en;
      return [
        { name: "metric", selector: { select: { mode: "dropdown", options: Object.keys(WERTE).map((value) => ({ value, label: t[value] })) } } },
        { name: "period", selector: { select: { mode: "dropdown", options: ZEITRAEUME.map((value) => ({ value, label: t[value] })) } } },
        { name: "days", selector: { number: { min: 7, max: 365, mode: "box" } } },
      ];
    },
    labels: {
      metric: { de: "Wert", en: "Value" },
      period: { de: "Zeitraster", en: "Period" },
      days: { de: "Zeitraum in Tagen (7–365)", en: "Range in days (7–365)" },
    },
  };

  static getStubConfig() {
    return { metric: "kd", period: "day", days: 30 };
  }

  static STYLE = `
    .diagramm { display: block; width: 100%; height: 120px; }
    .diagramm .linie { fill: none; stroke: ${FARBEN.akzent}; stroke-width: 2px; stroke-linejoin: round; stroke-linecap: round; }
    .diagramm .balken { fill: ${FARBEN.akzent}; }
    .diagramm .treffer { fill: transparent; }
    .diagramm .treffer:hover + .balken, .diagramm .treffer:hover { fill: color-mix(in srgb, ${FARBEN.akzent} 22%, transparent); }
    .diagramm .gitter { stroke: ${FARBEN.rand}; stroke-width: 1px; }
    .achse { display: flex; justify-content: space-between; gap: 10px; font-size: 12px; color: ${FARBEN.sek}; font-variant-numeric: tabular-nums; }
  `;

  _einstellungen() {
    const metric = WERTE[this._config.metric] ? this._config.metric : "kd";
    const period = ZEITRAEUME.includes(this._config.period) ? this._config.period : "day";
    const days = grenze(this._config.days, 30, 7, 365);
    return { metric, period, days, art: WERTE[metric][0] };
  }

  _inhalt() {
    const s = this._spieler();
    if (!s) {
      return this._keinSpieler("mdi:chart-line");
    }
    const e = this._einstellungen();
    const lang = this._lang();
    const id = s.ids[e.metric];
    const zustand = this._st(id);
    const proText = e.art === "mean" ? this._t(`mean_${e.period}`) : this._t(e.period);
    const kopf = this._spielerKopf(s, "mdi:chart-line", `${this._t(e.metric)} ${proText}`);
    const schluessel = [id, e.period, e.days, e.art, zustand?.last_changed].join("|");
    if (id && this._schluessel !== schluessel) {
      this._schluessel = schluessel;
      this._laden(schluessel, id, e);
    }
    const daten = this._daten?.schluessel === schluessel ? this._daten : this._altDaten?.id === id ? this._altDaten : null;
    if (!daten) {
      return { ...kopf, body: `<div class="hinweis">${esc(this._t("loading"))}</div>` };
    }
    if (daten.fehler) {
      return { ...kopf, body: `<div class="hinweis">${esc(this._t("error"))}: ${esc(daten.fehler)}</div>` };
    }
    if (!daten.punkte.length) {
      return { ...kopf, body: `<div class="hinweis">${esc(this._t("none"))}</div>` };
    }
    return { ...kopf, body: this._diagramm(daten.punkte, e, lang, zustand?.attributes?.unit_of_measurement) };
  }

  async _laden(schluessel, id, e) {
    const ende = new Date();
    const start = new Date(ende.getTime() - e.days * TAG);
    try {
      const antwort = await this._hass.callWS({
        type: "recorder/statistics_during_period",
        start_time: start.toISOString(),
        end_time: ende.toISOString(),
        statistic_ids: [id],
        period: e.period,
        types: [e.art],
      });
      const punkte = (antwort?.[id] || [])
        .map((p) => ({ t: typeof p.start === "number" ? p.start : Date.parse(p.start), v: p[e.art] }))
        .filter((p) => typeof p.v === "number" && Number.isFinite(p.v) && !Number.isNaN(p.t));
      this._daten = { schluessel, id, punkte };
    } catch (err) {
      this._daten = { schluessel, id, punkte: [], fehler: err?.message || String(err) };
    }
    if (this._schluessel === schluessel) {
      this._altDaten = this._daten;
      this._render();
    }
  }

  _diagramm(punkte, e, lang, einheit) {
    const [, stellen, istProzent] = WERTE[e.metric];
    // Spielzeit in der Einheit des Sensors (Vorgabe Stunden), Quoten in %
    const zusatz = istProzent ? " %" : e.metric === "time_played" && einheit ? ` ${einheit}` : "";
    const text = (v) => `${fmt(v, lang, stellen)}${zusatz}`;
    const datum = (t) => new Date(t).toLocaleDateString(lang, { day: "2-digit", month: "2-digit" });
    const werte = punkte.map((p) => p.v);
    const min = Math.min(...werte);
    const max = Math.max(...werte);
    const B = 300;
    const H = 120;
    const rand = 4;
    let marken;
    if (e.art === "change") {
      // Balken ab der Nulllinie, 2 px Abstand, oben 4 px gerundet
      const hoch = Math.max(max, 0) || 1;
      const breite = B / punkte.length;
      const balken = Math.max(1, breite - 2);
      marken = punkte
        .map((p, i) => {
          const h = Math.max(0, (p.v / hoch) * (H - rand));
          const x = i * breite + (breite - balken) / 2;
          const r = Math.min(4, balken / 2, h);
          const titel = `<title>${esc(`${datum(p.t)}: ${text(p.v)}`)}</title>`;
          return `<rect class="treffer" x="${(i * breite).toFixed(2)}" y="0" width="${breite.toFixed(2)}" height="${H}">${titel}</rect>${
            h > 0 ? `<path class="balken" d="${this._balken(x, H - h, balken, h, r)}">${titel}</path>` : ""
          }`;
        })
        .join("");
    } else {
      // Gleiche Werte (auch ein einziger Wert) als waagrechte Linie in der
      // Mitte; eine Polylinie aus nur einem Punkt waere unsichtbar (live am
      // 02.11.2026: am ersten Tag gibt es genau einen Tageswert).
      const spanne = max - min;
      const y = (v) => (spanne ? H - rand - ((v - min) / spanne) * (H - 2 * rand) : H / 2).toFixed(2);
      const x = (i) => ((i / (punkte.length - 1)) * B).toFixed(2);
      const linie =
        punkte.length === 1 ? `0,${y(punkte[0].v)} ${B},${y(punkte[0].v)}` : punkte.map((p, i) => `${x(i)},${y(p.v)}`).join(" ");
      const breite = B / punkte.length;
      marken =
        `<polyline class="linie" vector-effect="non-scaling-stroke" points="${linie}"></polyline>` +
        punkte
          .map(
            (p, i) =>
              `<rect class="treffer" x="${(punkte.length === 1 ? 0 : Math.max(0, x(i) - breite / 2)).toFixed(2)}" y="0" width="${breite.toFixed(2)}" height="${H}"><title>${esc(`${datum(p.t)}: ${text(p.v)}`)}</title></rect>`
          )
          .join("");
    }
    const zusammen =
      e.art === "change"
        ? `${this._t("sum")} ${text(werte.reduce((a, b) => a + b, 0))}`
        : `${this._t("min")} ${text(min)} · ${this._t("max")} ${text(max)}`;
    return `
      <svg class="diagramm" viewBox="0 0 ${B} ${H}" preserveAspectRatio="none" role="img" aria-label="${esc(`${this._t(e.metric)}: ${zusammen}`)}">
        <line class="gitter" x1="0" x2="${B}" y1="${H - 0.5}" y2="${H - 0.5}" vector-effect="non-scaling-stroke"></line>
        ${marken}
      </svg>
      <div class="achse"><span>${esc(datum(punkte[0].t))}</span><span>${esc(datum(punkte[punkte.length - 1].t))}</span></div>
      <div class="leg"><span>${esc(zusammen)}</span><span>${esc(`${fmt(e.days, lang)} ${this._t("days")}`)}</span></div>`;
  }

  // Rechteck mit oben gerundeten Ecken (Radius r), unten eckig auf der Nulllinie
  _balken(x, y, b, h, r) {
    const f = (n) => n.toFixed(2);
    return `M${f(x)},${f(y + h)}V${f(y + r)}Q${f(x)},${f(y)} ${f(x + r)},${f(y)}H${f(x + b - r)}Q${f(x + b)},${f(y)} ${f(x + b)},${f(y + r)}V${f(y + h)}Z`;
  }
}

C.registrieren("bf6-history-card", Bf6HistoryCard, "BF6 Verlauf", "Verlauf eines Werts (K/D, Kills pro Tag …) aus der Langzeitstatistik von Home Assistant.");
