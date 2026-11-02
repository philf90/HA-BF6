/*
 * Gemeinsame Teile der Karten der Integration BF6 Spieler (seit 0.6.0).
 *
 * Die Karten laden diese Datei mit ihrer eigenen Version im Pfad nach, damit
 * nach einem Update beide zusammenpassen:
 *   const C = await import(new URL(`bf6-common.js${new URL(import.meta.url).search}`, import.meta.url));
 *
 * Farben: Nachtblau-Stil (philf90/home-assistant, DESIGN.md und
 * design/palette.yaml). Jede Farbe ist eine Theme-Variable mit dem dunklen
 * Palettenwert als Rueckfall; ohne das Theme "nachtblau" sind die Karten in
 * beiden Modi dunkel. Akzent Rose, wie die WoW-Karten (Bereich Freizeit).
 *
 * Sicherheit: Jeder Text aus Entitaeten (Spielernamen, Waffen, Karten ...)
 * geht durch esc(), bevor er in innerHTML landet. Bildadressen kommen nur aus
 * der Integration, die sie auf https://cdn.gametools.network beschraenkt;
 * die Karten pruefen das zusaetzlich (bild()).
 */

export const FARBEN = {
  akzent: "var(--nachtblau-rose, #e6a0c4)",
  text: "var(--nachtblau-text, #f2f5f8)",
  titel: "var(--nachtblau-titel, #e7ecf3)",
  label: "var(--nachtblau-label, #b4c0cf)",
  sek: "var(--nachtblau-text-sekundaer, #8794a5)",
  kachel: "var(--nachtblau-unterkachel, rgba(255, 255, 255, 0.028))",
  rand: "var(--nachtblau-unterkachel-rand, rgba(255, 255, 255, 0.06))",
  spur: "var(--nachtblau-neutral-kachel, rgba(255, 255, 255, 0.05))",
  huelleOben: "var(--nachtblau-huelle-oben, #1b2231)",
  huelleUnten: "var(--nachtblau-huelle-unten, #171d29)",
  huelleRand: "var(--nachtblau-huelle-rand, rgba(255, 255, 255, 0.05))",
  schatten: "var(--nachtblau-schatten, rgba(0, 0, 0, 0.7))",
  vertieft: "var(--nachtblau-flaeche-vertieft, #10151d)",
  gruen: "var(--nachtblau-gruen, #a6d49e)",
  amber: "var(--nachtblau-amber, #e6b566)",
  rot: "var(--nachtblau-rot, #f0736a)",
  blau: "var(--nachtblau-blau, #7fb3d5)",
  violett: "var(--nachtblau-violett, #b399d4)",
  tuerkis: "var(--nachtblau-tuerkis, #7fd0d5)",
};

// Titel und Labels brechen in bis zu zwei Zeilen um (DESIGN.md, "Text").
export const ZWEIZEILIG =
  "overflow: hidden; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; text-wrap: balance;";

// Lichtrand um Waffen- und Fahrzeugbilder (seit 0.6.4), nur im dunklen Modus:
// Die Bilder vom CDN sind ueberwiegend dunkel und hoben sich von der dunklen
// Huelle kaum ab (am 02.11.2026 bei 7 Bildern 22-86 % der Bildpunkte unter
// 1,5:1). Der Rand nimmt die Farbe des Primaertexts (90 % und 50 % Deckkraft);
// der Schalter nachtblau-dunkel-anteil macht ihn im hellen Modus durchsichtig,
// dort stehen die Bilder ohnehin gut (0-4 % unter 1,5:1).
const NUR_DUNKEL = (farbe) => `color-mix(in srgb, ${farbe} var(--nachtblau-dunkel-anteil, 100%), transparent)`;
export const LICHTRAND = [
  `drop-shadow(0 0 0.6px ${NUR_DUNKEL(`color-mix(in srgb, ${FARBEN.text} 90%, transparent)`)})`,
  `drop-shadow(0 0 2px ${NUR_DUNKEL(`color-mix(in srgb, ${FARBEN.text} 50%, transparent)`)})`,
].join(" ");

export const STYLE = `
  :host { display: block; container-type: inline-size; }
  ha-card {
    display: block; padding: 14px 16px 16px; border-radius: 22px; cursor: default;
    border: 1px solid ${FARBEN.huelleRand};
    background: linear-gradient(180deg, ${FARBEN.huelleOben} 0%, ${FARBEN.huelleUnten} 55%);
    box-shadow: 0 18px 44px -22px ${FARBEN.schatten};
    color: ${FARBEN.text};
    font-family: var(--ha-font-family-body, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, system-ui, sans-serif);
  }
  .kopf { display: grid; grid-template-columns: auto minmax(0, 1fr); grid-template-areas: "i n" "i l"; align-items: center; }
  .symbol {
    grid-area: i; display: flex; align-items: center; justify-content: center; align-self: center;
    width: 44px; height: 44px; margin-right: 14px; box-sizing: border-box; border-radius: 13px; overflow: hidden;
    background: color-mix(in srgb, ${FARBEN.akzent} 16%, transparent);
    border: 1px solid color-mix(in srgb, ${FARBEN.akzent} 24%, transparent);
    color: ${FARBEN.akzent}; font-weight: 750; font-size: 16px; font-variant-numeric: tabular-nums;
  }
  .symbol ha-icon { --mdc-icon-size: 23px; --ha-icon-display: block; }
  .symbol img { display: block; width: 100%; height: 100%; object-fit: contain; }
  .name { grid-area: n; align-self: end; min-width: 0; font-size: 17px; line-height: 1.25; font-weight: 700; letter-spacing: -0.02em; color: ${FARBEN.titel}; ${ZWEIZEILIG} }
  .label { grid-area: l; align-self: start; min-width: 0; margin-top: 1px; font-size: 12.5px; line-height: 1.35; color: ${FARBEN.sek}; ${ZWEIZEILIG} }
  .label ha-icon { --mdc-icon-size: 14px; vertical-align: 0.09em; color: ${FARBEN.label}; }
  .body { display: grid; gap: 10px; padding-top: 12px; min-width: 0; }
  .hinweis { font-size: 12.5px; line-height: 1.4; color: ${FARBEN.sek}; }
  .uk { background: ${FARBEN.kachel}; border: 1px solid ${FARBEN.rand}; border-radius: 13px; padding: 8px 10px; min-width: 0; }
  .kz { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .kz .uk { display: flex; flex-direction: column; gap: 1px; }
  .kz .l { font-size: 12px; line-height: 1.3; color: ${FARBEN.sek}; ${ZWEIZEILIG} }
  .kz .n { font-size: 18px; font-weight: 750; color: ${FARBEN.text}; font-variant-numeric: tabular-nums; letter-spacing: -0.01em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  /* Kennzahl-Kacheln: Inhalt S25 306 px, iPhone 348 px -> Schwelle 327 px */
  @container (max-width: 327px) { .kz .n { font-size: 16.5px; } }
  .gruppe { background: ${FARBEN.kachel}; border: 1px solid ${FARBEN.rand}; border-radius: 14px; overflow: hidden; }
  .gkopf { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; padding: 9px 12px 8px; border-bottom: 1px solid ${FARBEN.rand}; }
  .gname { min-width: 0; font-size: 13px; line-height: 1.3; font-weight: 700; color: ${FARBEN.titel}; ${ZWEIZEILIG} }
  .ganz { font-size: 12px; color: ${FARBEN.sek}; white-space: nowrap; }
  .zeile { padding: 8px 12px; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 3px 10px; align-items: center; }
  .zeile + .zeile { border-top: 1px solid ${FARBEN.rand}; }
  .zeile.bild { grid-template-columns: 44px minmax(0, 1fr) auto; }
  .zeile.bild .spur { grid-column: 2 / -1; }
  .thumb { grid-row: 1 / span 3; width: 44px; height: 28px; object-fit: contain; filter: ${LICHTRAND}; }
  .zn { min-width: 0; font-size: 14px; line-height: 1.3; font-weight: 700; color: ${FARBEN.titel}; ${ZWEIZEILIG} }
  .zw { justify-self: end; font-size: 14px; font-weight: 750; color: ${FARBEN.text}; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .zi { min-width: 0; font-size: 12px; line-height: 1.3; color: ${FARBEN.sek}; ${ZWEIZEILIG} }
  .zr { justify-self: end; font-size: 12px; color: ${FARBEN.sek}; white-space: nowrap; font-variant-numeric: tabular-nums; }
  .spur { grid-column: 1 / -1; height: 6px; border-radius: 3px; background: ${FARBEN.spur}; overflow: hidden; }
  .spur i { display: block; height: 100%; border-radius: 3px; background: ${FARBEN.akzent}; }
  .stapel { display: flex; height: 10px; border-radius: 5px; overflow: hidden; gap: 2px; }
  .stapel span { display: block; height: 100%; }
  .leg { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 12px; line-height: 1.4; color: ${FARBEN.sek}; }
  .punkt { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; vertical-align: 0; }
  .pill { display: inline-block; font-size: 12px; font-weight: 600; padding: 2px 9px; border-radius: 999px; white-space: nowrap; line-height: 1.5;
    color: ${FARBEN.label}; background: color-mix(in srgb, ${FARBEN.blau} 12%, transparent); border: 1px solid color-mix(in srgb, ${FARBEN.blau} 24%, transparent); }
  .pill.gruen { color: ${FARBEN.gruen}; background: color-mix(in srgb, ${FARBEN.gruen} 12%, transparent); border-color: color-mix(in srgb, ${FARBEN.gruen} 24%, transparent); }
  .pill.rot { color: ${FARBEN.rot}; background: color-mix(in srgb, ${FARBEN.rot} 12%, transparent); border-color: color-mix(in srgb, ${FARBEN.rot} 24%, transparent); }
  .fort { height: 8px; border-radius: 4px; background: ${FARBEN.spur}; overflow: hidden; }
  .fort i { display: block; height: 100%; background: ${FARBEN.akzent}; border-radius: 4px; }
  .best { color: ${FARBEN.akzent}; }
`;

// Symbole je Plattform (Zustand des Sensors "Plattform"), wie icons.json
export const PLATTFORM_SYMBOL = {
  steam: "mdi:steam",
  psn: "mdi:sony-playstation",
  ps4: "mdi:sony-playstation",
  ps5: "mdi:sony-playstation",
  xbox: "mdi:microsoft-xbox",
  xboxone: "mdi:microsoft-xbox",
  xboxseries: "mdi:microsoft-xbox",
  pc: "mdi:microsoft-windows",
  ea: "mdi:gamepad-variant",
  epic: "mdi:gamepad-variant",
};

export const PLATTFORM_NAME = {
  ea: "EA app",
  steam: "Steam",
  epic: "Epic Games",
  psn: "PlayStation",
  xbox: "Xbox",
  pc: "PC",
  ps4: "PlayStation 4",
  ps5: "PlayStation 5",
  xboxone: "Xbox One",
  xboxseries: "Xbox Series",
};

export function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Nur Bilder von cdn.gametools.network ueber https, sonst null
export function bild(url) {
  try {
    const u = new URL(url);
    return u.protocol === "https:" && u.hostname === "cdn.gametools.network" && !u.username && !u.port
      ? u.href
      : null;
  } catch (err) {
    return null;
  }
}

export function leer(stateObj) {
  return !stateObj || ["unavailable", "unknown", ""].includes(stateObj.state);
}

export function zahl(stateObj) {
  if (leer(stateObj)) {
    return null;
  }
  const n = parseFloat(stateObj.state);
  return Number.isNaN(n) ? null : n;
}

export function sprache(hass) {
  return (hass?.locale?.language || hass?.language || "en").slice(0, 2);
}

// Zahl in der Sprache der Oberflaeche; null -> "–"
export function fmt(n, lang, stellen = 0) {
  if (n === null || n === undefined || Number.isNaN(n)) {
    return "–";
  }
  return Number(n).toLocaleString(lang, { minimumFractionDigits: stellen, maximumFractionDigits: stellen });
}

export function prozent(n, lang, stellen = 1) {
  return n === null || n === undefined ? "–" : `${fmt(n, lang, stellen)}\u00a0%`;
}

// Spielzeit-Sensor in Stunden, gleich welche Einheit eingestellt ist
export function stunden(stateObj) {
  const n = zahl(stateObj);
  if (n === null) {
    return null;
  }
  const faktor = { s: 1 / 3600, min: 1 / 60, h: 1, d: 24 }[stateObj.attributes?.unit_of_measurement];
  return faktor === undefined ? null : n * faktor;
}

// Liste aus einem Attribut, sonst leer
export function attrListe(stateObj, key) {
  const wert = stateObj?.attributes?.[key];
  return Array.isArray(wert) ? wert.filter((x) => x && typeof x === "object") : [];
}

// Reihenfolge der Farben fuer Anteile (Klassen, Stapelbalken)
export const SERIEN = [FARBEN.akzent, FARBEN.blau, FARBEN.violett, FARBEN.tuerkis, FARBEN.amber, FARBEN.gruen];

// Zahl aus einer Konfiguration, begrenzt; sonst Vorgabe
export function grenze(wert, vorgabe, min, max) {
  const n = parseInt(wert, 10);
  return Number.isNaN(n) ? vorgabe : Math.min(max, Math.max(min, n));
}

// Siegquote -> Statusfarbe (Stufen wie im Entwurf: ab 55 % Gruen, 45-55 %
// Amber, darunter Rot); der Wert steht immer als Text daneben
export function quotenFarbe(rate) {
  if (rate === null || rate === undefined) {
    return FARBEN.sek;
  }
  return rate >= 55 ? FARBEN.gruen : rate >= 45 ? FARBEN.amber : FARBEN.rot;
}

// Geraete der Integration aus hass.entities und hass.devices, einmal je Stand
// der Registries (seit 0.6.10). Der Setter "hass" laeuft bei jeder
// Zustandsaenderung irgendeiner Entitaet; bis 0.6.9 durchlief jede Karte dabei
// alle Entitaeten (gemessen: 1,5 ms je Karte bei 5.000 Entitaeten). Home
// Assistant ersetzt hass.entities und hass.devices bei jeder Aenderung der
// Registries durch neue Objekte; deren Identitaet reicht als Schluessel.
// Die Listen sind eingefroren, weil alle Karten sie teilen.
const INDEX = new WeakMap();
const LEER = Object.freeze({ spieler: Object.freeze([]), welt: null });

function index(hass) {
  const entities = hass?.entities;
  if (!entities) {
    return LEER;
  }
  const treffer = INDEX.get(entities);
  if (treffer && treffer.devices === hass.devices) {
    return treffer;
  }
  const geraete = {};
  for (const e of Object.values(entities)) {
    if (e.platform === "bf6_player" && e.device_id && e.translation_key) {
      (geraete[e.device_id] = geraete[e.device_id] || {})[e.translation_key] = e.entity_id;
    }
  }
  const devices = hass.devices || {};
  // Spieler: Geraete mit Kills-Sensor, sortiert nach Name; ids: {translation_key: entity_id}
  const spieler = Object.entries(geraete)
    .filter(([, ids]) => ids.kills)
    .map(([device, ids]) => {
      const g = devices[device] || {};
      return Object.freeze({ device, ids: Object.freeze(ids), name: g.name_by_user || g.name || ids.kills, modell: g.model || "" });
    })
    .sort((a, b) => a.name.localeCompare(b.name));
  // Spielwelt: Geraet mit Saisonende oder Portal-Servern
  let welt = null;
  const eintrag = Object.entries(geraete).find(([, ids]) => ids.season_end || ids.portal_servers);
  if (eintrag) {
    const [device, ids] = eintrag;
    const g = devices[device] || {};
    welt = Object.freeze({ device, ids: Object.freeze(ids), name: g.name_by_user || g.name || "BF6" });
  }
  const wert = Object.freeze({ devices: hass.devices, spieler: Object.freeze(spieler), welt });
  INDEX.set(entities, wert);
  return wert;
}

export function spieler(hass) {
  return index(hass).spieler;
}

export function welt(hass) {
  return index(hass).welt;
}

// Spieler aus der Konfiguration: entity (beliebige Entitaet des Spielers);
// ohne entity der erste Spieler
export function gewaehlt(hass, entity) {
  const liste = spieler(hass);
  if (!entity) {
    return liste[0] || null;
  }
  const device = hass?.entities?.[entity]?.device_id;
  return liste.find((s) => s.device === device || Object.values(s.ids).includes(entity)) || null;
}

const TEXT_BASIS = {
  de: { keinSpieler: "Kein Spieler gefunden. Integration „BF6 Spieler“ einrichten oder entity prüfen." },
  en: { keinSpieler: "No player found. Set up the integration “BF6 Spieler” or check entity." },
};

/*
 * Basisklasse: Konfiguration, Neuzeichnen nur bei geaenderten Zustaenden,
 * Huelle mit Kopf. Unterklassen setzen static TEXT ({de, en}), static
 * EDITOR (Optionen des Editors) und implementieren _ids() (beobachtete
 * Entitaeten) und _inhalt() ({symbol, name, label, body}).
 */
export class Bf6Card extends HTMLElement {
  setConfig(config) {
    this._config = { ...(config || {}) };
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    this._signatur = undefined;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const signatur = [...this._ids().map((id) => hass.states[id]), hass.locale?.language, hass.entities, hass.devices];
    if (this._signatur && signatur.length === this._signatur.length && signatur.every((s, i) => s === this._signatur[i])) {
      return;
    }
    this._signatur = signatur;
    this._render();
  }

  getCardSize() {
    return 4;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  static async getConfigElement() {
    const url = new URL(`bf6-card-editor.js${new URL(import.meta.url).search}`, import.meta.url);
    const { editor } = await import(url);
    return editor(this.EDITOR || {});
  }

  static getStubConfig() {
    return {};
  }

  _lang() {
    return sprache(this._hass);
  }

  _t(key) {
    const texte = { ...(TEXT_BASIS[this._lang()] || TEXT_BASIS.en), ...((this.constructor.TEXT || {})[this._lang()] || this.constructor.TEXT?.en || {}) };
    return texte[key];
  }

  _st(id) {
    return id ? this._hass?.states?.[id] : undefined;
  }

  _spieler() {
    return gewaehlt(this._hass, this._config?.entity);
  }

  _ids() {
    const s = this._spieler();
    return s ? Object.values(s.ids) : [];
  }

  // Kopf: Symbol (Rang-Abzeichen des Spielers oder Icon), Name, Label
  _kopf({ symbol, name, label }) {
    return `
      <div class="kopf">
        <div class="symbol">${symbol}</div>
        <div class="name">${esc(name)}</div>
        <div class="label">${label || ""}</div>
      </div>`;
  }

  _plattform(s) {
    const key = this._st(s.ids.platform)?.state;
    const name = PLATTFORM_NAME[key] || (s.modell.split(" · ")[1] ?? "");
    const icon = PLATTFORM_SYMBOL[key] || "mdi:gamepad-variant";
    return `<ha-icon icon="${esc(icon)}"></ha-icon> ${esc(name)}`;
  }

  // Kopf fuer Karten eines Spielers: Rang-Abzeichen (sonst icon), Name,
  // Plattform mit Symbol und optional ein Zusatz (z. B. Titel der Karte)
  _spielerKopf(s, icon, zusatz) {
    const abzeichen = bild(this._st(s.ids.rank)?.attributes?.rank_image);
    return {
      symbol: abzeichen ? `<img src="${esc(abzeichen)}" alt="">` : `<ha-icon icon="${esc(icon)}"></ha-icon>`,
      name: s.name,
      label: zusatz ? `${this._plattform(s)} · ${esc(zusatz)}` : this._plattform(s),
    };
  }

  _render() {
    if (!this.shadowRoot || !this._hass || !this._config) {
      return;
    }
    let inhalt;
    try {
      inhalt = this._inhalt();
    } catch (err) {
      inhalt = { symbol: `<ha-icon icon="mdi:alert"></ha-icon>`, name: "BF6", label: "", body: `<div class="hinweis">${esc(err)}</div>` };
    }
    this.shadowRoot.innerHTML = `
      <style>${STYLE}${this.constructor.STYLE || ""}</style>
      <ha-card>
        ${this._kopf(inhalt)}
        <div class="body">${inhalt.body}</div>
      </ha-card>`;
  }

  _keinSpieler(icon) {
    return {
      symbol: `<ha-icon icon="${icon}"></ha-icon>`,
      name: this._t("title"),
      label: "",
      body: `<div class="hinweis">${esc(this._t("keinSpieler"))}</div>`,
    };
  }
}

// Karte einmal registrieren und im Kartenwaehler anbieten
export function registrieren(element, klasse, name, description) {
  if (!customElements.get(element)) {
    customElements.define(element, klasse);
    window.customCards = window.customCards || [];
    window.customCards.push({ type: element, name, description, preview: true });
  }
}
