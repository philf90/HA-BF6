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
 * Balken des Zuwachses je Zeitraum (z. B. Kills pro Tag), jeder Wert an
 * seinem Platz auf der Zeitachse (seit 0.6.2).
 *
 * Seit 0.8.1: Links stehen der oberste und der unterste Wert der Skala.
 * Beim Ueberfahren mit der Maus oder Antippen steht "Datum: Wert" unter dem
 * Diagramm; bis 0.8.0 gab es den Wert nur im Tooltip des Browsers (SVG-Titel,
 * auf Touch-Geraeten nie). Die Linie hat eine Mindestspanne von zehn
 * Anzeigeschritten (K/D: 0,1): Live am 03.11.2026 lagen zwei Tagesmittel bei
 * 1,5040 und 1,5006, und die Linie fiel ueber die volle Hoehe, obwohl beide
 * als 1,50 angezeigt wurden.
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
// Laenge eines Zeitraums in ms; Monate im Mittel (365,25 / 12 Tage), die
// Zuordnung rundet, Sommerzeit und Monatslaengen fallen so heraus
const PERIODE = { day: TAG, week: 7 * TAG, month: (365.25 / 12) * TAG };

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
    .flaeche { position: relative; }
    .diagramm { display: block; width: 100%; height: 120px; }
    .skala { position: absolute; left: 0; font-size: 11px; line-height: 1; color: ${FARBEN.sek}; font-variant-numeric: tabular-nums; pointer-events: none; }
    .skala.oben { top: 0; }
    .skala.unten { bottom: 2px; }
    .diagramm .gewaehlt.balken { fill: ${FARBEN.text}; }
    .diagramm .treffer.gewaehlt { fill: color-mix(in srgb, ${FARBEN.akzent} 22%, transparent); }
    .anzeige { color: ${FARBEN.text}; }
    .diagramm .linie { fill: none; stroke: ${FARBEN.akzent}; stroke-width: 2px; stroke-linejoin: round; stroke-linecap: round; }
    .diagramm .balken { fill: ${FARBEN.akzent}; }
    .diagramm .treffer { fill: transparent; }
    .diagramm .treffer:hover + .balken, .diagramm .treffer:hover { fill: color-mix(in srgb, ${FARBEN.akzent} 22%, transparent); }
    .diagramm .gitter { stroke: ${FARBEN.rand}; stroke-width: 1px; }
    .achse { display: flex; justify-content: space-between; gap: 10px; font-size: 12px; color: ${FARBEN.sek}; font-variant-numeric: tabular-nums; }
  `;

  setConfig(config) {
    super.setConfig(config);
    if (!this._wertanzeige) {
      // Am Schatten-DOM, nicht an den Elementen: Diese entstehen bei jedem
      // Zeichnen neu, die Listener bleiben.
      this._wertanzeige = true;
      this.shadowRoot.addEventListener("pointerover", (ev) => this._zeigen(ev, ev.pointerType !== "mouse"));
      this.shadowRoot.addEventListener("pointerdown", (ev) => this._zeigen(ev, true));
      this.shadowRoot.addEventListener("pointerout", (ev) => {
        // Maus verlaesst das Diagramm: wieder die Zusammenfassung. Bei
        // Beruehrung bleibt der angetippte Wert stehen.
        if (ev.pointerType === "mouse" && !ev.relatedTarget?.closest?.(".diagramm")) {
          this._zeigen(ev, false, true);
        }
      });
    }
  }

  // Wert unter dem Diagramm zeigen; ohne Treffer bzw. beim Verlassen die
  // Zusammenfassung
  _zeigen(ev, halten, zurueck = false) {
    const anzeige = this.shadowRoot?.querySelector(".anzeige");
    if (!anzeige) {
      return;
    }
    const ziel = zurueck ? null : ev.target?.closest?.("[data-info]");
    if (!ziel && !zurueck && !halten) {
      return;
    }
    anzeige.textContent = ziel ? ziel.dataset.info : anzeige.dataset.standard;
    for (const el of this.shadowRoot.querySelectorAll(".gewaehlt")) {
      el.classList.remove("gewaehlt");
    }
    if (ziel) {
      for (const el of this.shadowRoot.querySelectorAll(`[data-i="${ziel.dataset.i}"]`)) {
        el.classList.add("gewaehlt");
      }
    }
  }

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
    const zusatz = istProzent ? "\u00a0%" : e.metric === "time_played" && einheit ? `\u00a0${einheit}` : "";
    const text = (v) => `${fmt(v, lang, stellen)}${zusatz}`;
    const datum = (t) => new Date(t).toLocaleDateString(lang, { day: "2-digit", month: "2-digit" });
    const werte = punkte.map((p) => p.v);
    const min = Math.min(...werte);
    const max = Math.max(...werte);
    const B = 300;
    const H = 120;
    const rand = 4;
    // Zeitachse: ein Platz je Zeitraum (Tag, Woche, Monat) ueber den ganzen
    // Bereich, der laufende Zeitraum rechts. Fehlende Tage bleiben leer,
    // statt dass wenige Werte die ganze Breite fuellen (live am 02.11.2026:
    // ein einziger Tageswert als Balken ueber die volle Breite).
    const laenge = PERIODE[e.period];
    const jetzt = this._periodenStart(e.period, 0);
    const zurueck = (t) => Math.max(0, Math.round((jetzt - t) / laenge));
    const plaetze = Math.max(Math.ceil((e.days * TAG) / laenge), ...punkte.map((p) => zurueck(p.t) + 1));
    const breite = B / plaetze;
    const links = (p) => (plaetze - 1 - zurueck(p.t)) * breite;
    const info = (p) => `${datum(p.t)}: ${text(p.v)}`;
    const titel = (p) => `<title>${esc(info(p))}</title>`;
    // data-i verbindet Trefferflaeche und Balken, data-info ist der Text der
    // Wertanzeige (beides von esc(), die Anzeige setzt ihn als textContent)
    const merkmale = (p, i) => `data-i="${i}" data-info="${esc(info(p))}"`;
    const treffer = (p, i) =>
      `<rect class="treffer" ${merkmale(p, i)} x="${links(p).toFixed(2)}" y="0" width="${breite.toFixed(2)}" height="${H}">${titel(p)}</rect>`;
    let marken;
    let skala;
    if (e.art === "change") {
      // Balken ab der Nulllinie, 2 Einheiten Abstand, oben bis 4 gerundet
      const hoch = Math.max(max, 0) || 1;
      const balken = Math.max(1, breite - 2);
      marken = punkte
        .map((p, i) => {
          const h = Math.max(0, (p.v / hoch) * (H - rand));
          const r = Math.min(4, balken / 2, h);
          return `${treffer(p, i)}${h > 0 ? `<path class="balken" ${merkmale(p, i)} d="${this._balken(links(p) + (breite - balken) / 2, H - h, balken, h, r)}">${titel(p)}</path>` : ""}`;
        })
        .join("");
      skala = [hoch, 0];
    } else {
      // Linie durch die Mitte der Plaetze; Luecken unterbrechen sie, ein
      // einzelner Wert ist ein kurzer Strich ueber seinen Platz. Die Skala
      // umfasst mindestens zehn Anzeigeschritte um die Mitte der Werte:
      // Unterschiede unter der angezeigten Genauigkeit wirken flach, statt
      // auf die volle Hoehe gestreckt zu werden.
      const mindest = 10 * 10 ** -stellen;
      const mitte = (min + max) / 2;
      const spanne = Math.max(max - min, mindest);
      const unten = mitte - spanne / 2;
      const y = (v) => (H - rand - ((v - unten) / spanne) * (H - 2 * rand)).toFixed(2);
      const f = (n) => n.toFixed(2);
      const sortiert = [...punkte].sort((a, b) => a.t - b.t);
      const laeufe = [];
      for (const p of sortiert) {
        const lauf = laeufe[laeufe.length - 1];
        if (lauf && zurueck(lauf[lauf.length - 1].t) - zurueck(p.t) === 1) {
          lauf.push(p);
        } else {
          laeufe.push([p]);
        }
      }
      const strich = Math.max(breite - 2, 4);
      const d = laeufe
        .map((lauf) =>
          lauf.length === 1
            ? `M${f(links(lauf[0]) + (breite - strich) / 2)},${y(lauf[0].v)}H${f(links(lauf[0]) + (breite + strich) / 2)}`
            : lauf.map((p, i) => `${i ? "L" : "M"}${f(links(p) + breite / 2)},${y(p.v)}`).join("")
        )
        .join("");
      marken = `<path class="linie" vector-effect="non-scaling-stroke" d="${d}"></path>${punkte.map(treffer).join("")}`;
      skala = [unten + spanne, unten];
    }
    const zusammen =
      e.art === "change"
        ? `${this._t("sum")} ${text(werte.reduce((a, b) => a + b, 0))}`
        : `${this._t("min")} ${text(min)} · ${this._t("max")} ${text(max)}`;
    return `
      <div class="flaeche">
        <svg class="diagramm" viewBox="0 0 ${B} ${H}" preserveAspectRatio="none" role="img" aria-label="${esc(`${this._t(e.metric)}: ${zusammen}`)}">
          <line class="gitter" x1="0" x2="${B}" y1="${H - 0.5}" y2="${H - 0.5}" vector-effect="non-scaling-stroke"></line>
          ${marken}
        </svg>
        <span class="skala oben">${esc(text(skala[0]))}</span>
        <span class="skala unten">${esc(text(skala[1]))}</span>
      </div>
      <div class="achse"><span>${esc(datum(this._periodenStart(e.period, plaetze - 1)))}</span><span>${esc(datum(jetzt))}</span></div>
      <div class="leg"><span class="anzeige" data-standard="${esc(zusammen)}">${esc(zusammen)}</span><span>${esc(`${fmt(e.days, lang)}\u00a0${this._t("days")}`)}</span></div>`;
  }

  // Beginn des Zeitraums, der zurueck Zeitraeume vor dem laufenden liegt, in
  // Ortszeit (Home Assistant teilt Tage, Wochen ab Montag und Monate ebenso)
  _periodenStart(period, zurueck) {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    if (period === "month") {
      d.setDate(1);
      d.setMonth(d.getMonth() - zurueck);
    } else if (period === "week") {
      d.setDate(d.getDate() - ((d.getDay() + 6) % 7) - 7 * zurueck);
    } else {
      d.setDate(d.getDate() - zurueck);
    }
    return d.getTime();
  }

  // Rechteck mit oben gerundeten Ecken (Radius r), unten eckig auf der Nulllinie
  _balken(x, y, b, h, r) {
    const f = (n) => n.toFixed(2);
    return `M${f(x)},${f(y + h)}V${f(y + r)}Q${f(x)},${f(y)} ${f(x + r)},${f(y)}H${f(x + b - r)}Q${f(x + b)},${f(y)} ${f(x + b)},${f(y + r)}V${f(y + h)}Z`;
  }
}

C.registrieren("bf6-history-card", Bf6HistoryCard, "BF6 Verlauf", "Verlauf eines Werts (K/D, Kills pro Tag …) aus der Langzeitstatistik von Home Assistant.");
