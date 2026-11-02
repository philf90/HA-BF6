/*
 * Karte "BF6 Arsenal": meistgenutzte Waffen und Fahrzeuge eines Spielers.
 *
 *   type: custom:bf6-arsenal-card
 *   entity: sensor.<spieler>_kills   # leer: erster Spieler
 *   limit: 5                         # Eintraege je Gruppe, 1 bis 5
 *   show: [weapons, vehicles]        # Gruppen, Vorgabe beide
 *
 * Daten: Attribut "top" der Sensoren "Meiste Kills mit Waffe" und "Meiste
 * Kills mit Fahrzeug" (die fuenf Eintraege mit den meisten Kills). Bilder nur
 * von https://cdn.gametools.network.
 */

const C = await import(new URL(`bf6-common.js${new URL(import.meta.url).search}`, import.meta.url));
const { esc, fmt, prozent, bild, attrListe, grenze } = C;

const GRUPPEN = { weapons: "top_weapon", vehicles: "top_vehicle" };

class Bf6ArsenalCard extends C.Bf6Card {
  static TEXT = {
    de: {
      title: "BF6 Arsenal",
      weapons: "Waffen",
      vehicles: "Fahrzeuge",
      kills: "Kills",
      accuracy: "Genauigkeit",
      headshots: "Headshots",
      kpm: "KPM",
      hours: "h",
      none: "Noch keine Kills.",
    },
    en: {
      title: "BF6 Arsenal",
      weapons: "Weapons",
      vehicles: "Vehicles",
      kills: "Kills",
      accuracy: "Accuracy",
      headshots: "Headshots",
      kpm: "KPM",
      hours: "h",
      none: "No kills yet.",
    },
  };

  static EDITOR = {
    extra: (lang) => [
      { name: "limit", selector: { number: { min: 1, max: 5, mode: "box" } } },
      {
        name: "show",
        selector: {
          select: {
            multiple: true,
            options: ["weapons", "vehicles"].map((value) => ({
              value,
              label: (Bf6ArsenalCard.TEXT[lang] || Bf6ArsenalCard.TEXT.en)[value],
            })),
          },
        },
      },
    ],
    labels: {
      limit: { de: "Einträge je Gruppe (1–5)", en: "Entries per group (1–5)" },
      show: { de: "Gruppen", en: "Groups" },
    },
  };

  _inhalt() {
    const s = this._spieler();
    if (!s) {
      return this._keinSpieler("mdi:pistol");
    }
    const lang = this._lang();
    const limit = grenze(this._config.limit, 5, 1, 5);
    const zeigen = Array.isArray(this._config.show) && this._config.show.length ? this._config.show : Object.keys(GRUPPEN);
    const gruppen = zeigen
      .filter((g) => GRUPPEN[g])
      .map((g) => this._gruppe(g, attrListe(this._st(s.ids[GRUPPEN[g]]), "top").slice(0, limit), lang))
      .join("");
    return { ...this._spielerKopf(s, "mdi:pistol", this._t("title")), body: gruppen };
  }

  _gruppe(gruppe, eintraege, lang) {
    const max = Math.max(1, ...eintraege.map((e) => e.kills || 0));
    const zeilen = eintraege.length
      ? eintraege.map((e) => this._zeile(gruppe, e, max, lang)).join("")
      : `<div class="zeile"><span class="zi">${esc(this._t("none"))}</span></div>`;
    return `<div class="gruppe"><div class="gkopf"><span class="gname">${esc(this._t(gruppe))}</span><span class="ganz">${esc(this._t("kills"))}</span></div>${zeilen}</div>`;
  }

  _zeile(gruppe, e, max, lang) {
    const url = bild(e.image);
    const info =
      gruppe === "weapons"
        ? [
            e.type,
            `${this._t("accuracy")} ${prozent(e.accuracy, lang)}`,
            `${this._t("headshots")} ${prozent(e.headshot_rate, lang)}`,
            `${this._t("kpm")} ${fmt(e.kpm, lang, 2)}`,
          ]
        : [e.type, typeof e.seconds === "number" ? `${fmt(e.seconds / 3600, lang, 1)}\u00a0${this._t("hours")}` : null];
    const breite = Math.round(((e.kills || 0) / max) * 100);
    return `
      <div class="zeile${url ? " bild" : ""}">
        ${url ? `<img class="thumb" src="${esc(url)}" alt="" loading="lazy">` : ""}
        <span class="zn">${esc(e.name || "–")}</span><span class="zw">${esc(fmt(e.kills, lang))}</span>
        <span class="zi" style="grid-column: ${url ? "2" : "1"} / -1">${esc(info.filter(Boolean).join(" · "))}</span>
        <div class="spur"><i style="width:${breite}%"></i></div>
      </div>`;
  }
}

C.registrieren("bf6-arsenal-card", Bf6ArsenalCard, "BF6 Arsenal", "Waffen und Fahrzeuge mit den meisten Kills eines Battlefield-6-Spielers.");
