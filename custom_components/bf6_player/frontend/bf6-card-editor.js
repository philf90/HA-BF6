/*
 * Editor der Karten der Integration BF6 Spieler (seit 0.6.0), aufgebaut wie
 * der Editor der Integration WoW Charakter.
 *
 * Statt aller Sensoren bietet er nur die Spieler an ("Name · Plattform").
 * Gespeichert wird der Kills-Sensor des Spielers; die Karten finden die
 * uebrigen Entitaeten ueber dessen Geraet. Steht in der Konfiguration eine
 * andere Entitaet des Spielers, zeigt der Editor trotzdem den Spieler.
 *
 * Die Karten laden diese Datei in getConfigElement() selbst nach und setzen
 * die Optionen des Editors (static EDITOR):
 *   name      Schluessel in der Konfiguration ("entity" oder "entities")
 *   multiple  mehrere Spieler (leer: alle)
 *   welt      keine Spielerauswahl (Karte "BF6 Spielwelt")
 *   extra     weitere ha-form-Felder, als Liste oder als Funktion (lang)
 *             fuer uebersetzte Auswahltexte
 *   labels    Beschriftungen der weiteren Felder: {name: {de, en}}
 */

const C = await import(new URL(`bf6-common.js${new URL(import.meta.url).search}`, import.meta.url));

const TEXT = {
  de: {
    entity: "Spieler",
    entities: "Spieler (leer: alle)",
    unknown: "nicht gefunden",
    none: "Keine Spieler der Integration „BF6 Spieler“ gefunden.",
  },
  en: {
    entity: "Player",
    entities: "Players (empty: all)",
    unknown: "not found",
    none: "No players of the integration “BF6 Spieler” found.",
  },
};

// Spieler fuer die Auswahl: Wert ist der Kills-Sensor
function liste(hass) {
  return C.spieler(hass).map((s) => {
    const plattform = s.modell.split(" · ")[1];
    return { device: s.device, entity: s.ids.kills, label: plattform ? `${s.name} · ${plattform}` : s.name };
  });
}

class Bf6CardEditor extends HTMLElement {
  constructor() {
    super();
    this.optionen = { name: "entity" };
  }

  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _t(key) {
    return (TEXT[C.sprache(this._hass)] || TEXT.en)[key];
  }

  // Konfigurierte Entitaet -> Kills-Sensor desselben Geraets
  _zuKills(id, eintraege) {
    const device = (this._hass?.entities || {})[id]?.device_id;
    return eintraege.find((s) => s.entity === id || (device && s.device === device))?.entity || id;
  }

  _render() {
    if (!this._hass || !this._config) {
      return;
    }
    const o = this.optionen;
    const lang = C.sprache(this._hass);
    const daten = { ...this._config };
    const schema = [];
    let eintraege = [];
    if (!o.welt) {
      eintraege = liste(this._hass);
      const optionen = eintraege.map((s) => ({ value: s.entity, label: s.label }));
      const werte = o.multiple ? this._config[o.name] || [] : [this._config[o.name]].filter(Boolean);
      const gezeigt = werte.map((id) => this._zuKills(id, eintraege));
      // Unbekannte Entitaet sichtbar lassen statt still zu verwerfen
      for (const id of gezeigt) {
        if (!optionen.some((x) => x.value === id)) {
          optionen.push({ value: id, label: `${id} (${this._t("unknown")})` });
        }
      }
      daten[o.name] = o.multiple ? gezeigt : gezeigt[0];
      schema.push({
        name: o.name,
        required: false,
        selector: { select: { mode: o.multiple ? "list" : "dropdown", multiple: !!o.multiple, options: optionen } },
      });
    }
    schema.push(...(typeof o.extra === "function" ? o.extra(lang) : o.extra || []));
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (ev) => this._geaendert(ev.detail.value));
      this.appendChild(this._form);
    }
    if (!o.welt && !eintraege.length) {
      this._hinweis = this._hinweis || this.insertBefore(document.createElement("p"), this._form);
      this._hinweis.textContent = this._t("none");
    } else if (this._hinweis) {
      this._hinweis.remove();
      this._hinweis = undefined;
    }
    this._form.hass = this._hass;
    this._form.data = daten;
    this._form.schema = schema;
    this._form.computeLabel = (s) => {
      if (s.name === o.name && !o.welt) {
        return this._t(o.multiple ? "entities" : "entity");
      }
      const label = (o.labels || {})[s.name];
      return label ? label[lang] || label.en : undefined;
    };
  }

  _geaendert(value) {
    const config = { ...this._config, ...value };
    // Leere optionale Felder nicht als null speichern
    for (const [k, v] of Object.entries(config)) {
      if (v === undefined || v === null || v === "" || (Array.isArray(v) && !v.length && k !== "type")) {
        delete config[k];
      }
    }
    this._config = config;
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
  }
}

if (!customElements.get("bf6-card-editor")) {
  customElements.define("bf6-card-editor", Bf6CardEditor);
}

// ha-form laedt Home Assistant erst mit dem ersten eingebauten Karten-Editor.
// Fehlt es noch, den Editor der Karte "entities" anfordern, der es mitbringt.
async function haFormLaden() {
  if (customElements.get("ha-form")) {
    return;
  }
  try {
    const helpers = await window.loadCardHelpers?.();
    const karte = helpers?.createCardElement({ type: "entities", entities: [] });
    await karte?.constructor?.getConfigElement?.();
  } catch (err) {
    // Ohne ha-form bleibt der Editor leer; YAML-Modus geht weiterhin.
  }
}

export async function editor(optionen) {
  await haFormLaden();
  const el = document.createElement("bf6-card-editor");
  el.optionen = { name: "entity", ...optionen };
  return el;
}
