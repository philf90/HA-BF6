/*
 * Karte "BF6 Klassen": Spielzeit und Werte je Klasse eines Spielers.
 *
 *   type: custom:bf6-classes-card
 *   entity: sensor.<spieler>_kills   # leer: erster Spieler
 *
 * Daten: Attribut "classes" des Sensors "Lieblingsklasse" (ohne den
 * Sammeleintrag der API, nach Spielzeit absteigend). Oben der Anteil an der
 * Spielzeit als Balken, darunter je Klasse Spielzeit, K/D, KPM und Kills.
 */

const C = await import(new URL(`bf6-common.js${new URL(import.meta.url).search}`, import.meta.url));
const { esc, fmt, attrListe, SERIEN } = C;

class Bf6ClassesCard extends C.Bf6Card {
  static TEXT = {
    de: { title: "BF6 Klassen", share: "Anteil an der Spielzeit", kills: "Kills", hours: "h", none: "Keine Klassen in der Statistik." },
    en: { title: "BF6 Classes", share: "Share of time played", kills: "Kills", hours: "h", none: "No classes in the statistics." },
  };

  _inhalt() {
    const s = this._spieler();
    if (!s) {
      return this._keinSpieler("mdi:account-tie");
    }
    const lang = this._lang();
    const kopf = this._spielerKopf(s, "mdi:account-tie", this._t("title"));
    // Spielzeit nur als endliche Zahl >= 0 (seit 0.6.10): Sie steht unten in
    // style="flex:…". Bis 0.6.9 kam der Attributwert ungeprueft dorthin; ein
    // Text mit " (z. B. ueber customize gesetzt) haette das Attribut beendet.
    const sekunden = (k) => {
      const n = Number(k.seconds);
      return Number.isFinite(n) && n > 0 ? n : 0;
    };
    const klassen = attrListe(this._st(s.ids.favorite_class), "classes");
    const summe = klassen.reduce((n, k) => n + sekunden(k), 0);
    if (!klassen.length || !summe) {
      return { ...kopf, body: `<div class="hinweis">${esc(this._t("none"))}</div>` };
    }
    const farbe = (i) => SERIEN[i % SERIEN.length];
    const balken = klassen
      .map((k, i) => (sekunden(k) ? `<span style="flex:${sekunden(k)};background:${farbe(i)}"></span>` : ""))
      .join("");
    const zeilen = klassen
      .map((k, i) => {
        const anteil = (sekunden(k) / summe) * 100;
        const info = [`K/D\u00a0${fmt(k.kd, lang, 2)}`, `KPM\u00a0${fmt(k.kpm, lang, 2)}`, `${fmt(k.kills, lang)}\u00a0${this._t("kills")}`];
        return `
          <div class="zeile">
            <span class="zn"><span class="punkt" style="background:${farbe(i)}"></span>${esc(k.name || "–")}</span>
            <span class="zw">${esc(fmt(sekunden(k) / 3600, lang, 1))}\u00a0${esc(this._t("hours"))}</span>
            <span class="zi">${esc(info.join(" · "))}</span><span class="zr">${esc(fmt(anteil, lang))}\u00a0%</span>
            <div class="spur"><i style="width:${anteil.toFixed(1)}%;background:${farbe(i)}"></i></div>
          </div>`;
      })
      .join("");
    return {
      ...kopf,
      body: `
        <div class="stapel" title="${esc(this._t("share"))}">${balken}</div>
        <div class="gruppe">${zeilen}</div>`,
    };
  }
}

C.registrieren("bf6-classes-card", Bf6ClassesCard, "BF6 Klassen", "Spielzeit, K/D und KPM je Klasse eines Battlefield-6-Spielers.");
