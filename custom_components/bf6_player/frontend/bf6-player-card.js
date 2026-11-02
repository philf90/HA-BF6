/*
 * Karte "BF6 Spieler": Kennzahlen eines Spielers (Integration BF6 Spieler).
 *
 *   type: custom:bf6-player-card
 *   entity: sensor.<spieler>_kills   # beliebige Entitaet des Spielers; leer: erster Spieler
 *
 * Kopf: Rang-Abzeichen, Name, Plattform mit Symbol, Rang. Darunter Kills,
 * K/D, KPM, Matches, Siegquote, Spielzeit, der Balken Siege/Niederlagen,
 * Treffergenauigkeit, Headshot-Quote, Kills gegen Menschen und die Favoriten.
 */

const C = await import(new URL(`bf6-common.js${new URL(import.meta.url).search}`, import.meta.url));
const { esc, fmt, prozent, zahl, leer, stunden, quotenFarbe, FARBEN } = C;

class Bf6PlayerCard extends C.Bf6Card {
  static TEXT = {
    de: {
      title: "BF6 Spieler",
      rank: "Rang",
      kills: "Kills",
      kd: "K/D",
      kpm: "KPM",
      matches: "Matches",
      win_rate: "Siegquote",
      time: "Spielzeit",
      wins: "Siege",
      losses: "Niederlagen",
      other: "sonstige",
      accuracy: "Treffer\u00adgenauigkeit",
      headshot_rate: "Headshot-Quote",
      human_kill_rate: "Kills gegen Menschen",
      favorites: "Favoriten",
      favorite_class: "Klasse",
      top_weapon: "Waffe",
      top_vehicle: "Fahrzeug",
      hours: "h",
    },
    en: {
      title: "BF6 Player",
      rank: "Rank",
      kills: "Kills",
      kd: "K/D",
      kpm: "KPM",
      matches: "Matches",
      win_rate: "Win rate",
      time: "Time played",
      wins: "Wins",
      losses: "Losses",
      other: "other",
      accuracy: "Accuracy",
      headshot_rate: "Headshot rate",
      human_kill_rate: "Kills vs. humans",
      favorites: "Favorites",
      favorite_class: "Class",
      top_weapon: "Weapon",
      top_vehicle: "Vehicle",
      hours: "h",
    },
  };

  _kachel(label, wert, farbe) {
    const stil = farbe ? ` style="color:${farbe}"` : "";
    return `<div class="uk"><span class="l">${esc(this._t(label))}</span><span class="n"${stil}>${esc(wert)}</span></div>`;
  }

  _inhalt() {
    const s = this._spieler();
    if (!s) {
      return this._keinSpieler("mdi:account-question");
    }
    const lang = this._lang();
    const st = (key) => this._st(s.ids[key]);
    const rang = zahl(st("rank"));
    const rangName = st("rank")?.attributes?.rank_name;
    const kopf = this._spielerKopf(
      s,
      "mdi:account",
      rang === null ? "" : `${this._t("rank")} ${fmt(rang, lang)}${rangName && rangName !== String(rang) ? ` (${rangName})` : ""}`
    );
    const quote = zahl(st("win_rate"));
    const kz = [
      this._kachel("kills", fmt(zahl(st("kills")), lang)),
      this._kachel("kd", fmt(zahl(st("kd")), lang, 2)),
      this._kachel("kpm", fmt(zahl(st("kpm")), lang, 2)),
      this._kachel("matches", fmt(zahl(st("matches")), lang)),
      this._kachel("win_rate", prozent(quote, lang), quotenFarbe(quote)),
      this._kachel("time", `${fmt(stunden(st("time_played")), lang)}\u00a0${this._t("hours")}`),
    ].join("");
    const genau = [
      this._kachel("accuracy", prozent(zahl(st("accuracy")), lang)),
      this._kachel("headshot_rate", prozent(zahl(st("headshot_rate")), lang)),
      this._kachel("human_kill_rate", prozent(zahl(st("human_kill_rate")), lang)),
    ].join("");
    return { ...kopf, body: `<div class="kz">${kz}</div>${this._bilanz(st, lang)}<div class="kz">${genau}</div>${this._favoriten(st)}` };
  }

  // Balken Siege / Niederlagen / sonstige (Matches - Siege - Niederlagen;
  // live am 02.11.2026 747 - 346 - 400 = 1, die API sagt nicht, warum)
  _bilanz(st, lang) {
    const matches = zahl(st("matches"));
    const siege = zahl(st("wins"));
    const niederlagen = zahl(st("losses"));
    if (!matches || siege === null || niederlagen === null) {
      return "";
    }
    const rest = Math.max(0, matches - siege - niederlagen);
    const teile = [
      ["wins", siege, FARBEN.gruen],
      ["losses", niederlagen, FARBEN.rot],
      ["other", rest, FARBEN.sek],
    ].filter(([, n]) => n > 0);
    const balken = teile.map(([, n, farbe]) => `<span style="flex:${n};background:${farbe}"></span>`).join("");
    const legende = teile
      .map(([key, n, farbe]) => `<span><span class="punkt" style="background:${farbe}"></span>${esc(fmt(n, lang))}\u00a0${esc(this._t(key))}</span>`)
      .join("");
    return `<div class="stapel">${balken}</div><div class="leg">${legende}</div>`;
  }

  _favoriten(st) {
    const zeilen = ["favorite_class", "top_weapon", "top_vehicle"]
      .filter((key) => !leer(st(key)))
      .map((key) => `<div class="zeile"><span class="zi">${esc(this._t(key))}</span><span class="zw">${esc(st(key).state)}</span></div>`)
      .join("");
    return zeilen ? `<div class="gruppe"><div class="gkopf"><span class="gname">${esc(this._t("favorites"))}</span></div>${zeilen}</div>` : "";
  }
}

C.registrieren("bf6-player-card", Bf6PlayerCard, "BF6 Spieler", "Kennzahlen eines Battlefield-6-Spielers: K/D, KPM, Siegquote, Spielzeit, Favoriten.");
