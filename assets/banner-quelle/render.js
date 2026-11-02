// Rendert die Bilder unter assets/ aus den Seiten in diesem Ordner:
//   banner.png (2560 x 512), social-preview.png (1280 x 640) aus index.html,
//   vorschau-karten.png (2480 x 1660) aus vorschau.html.
//
//   python3 -m http.server 8000 --bind 127.0.0.1   (im Wurzelverzeichnis des Repos)
//   node assets/banner-quelle/render.js             (Playwright mit Chromium)
//
// Braucht Netz fuer Google Fonts und jsDelivr. Prueft, dass die Schriften
// geladen sind, damit kein Ersatz in den Bildern landet.
const { chromium } = require("playwright");
const path = require("path");

const BASIS = process.env.BASIS || "http://127.0.0.1:8000/assets/banner-quelle";
const ZIEL = path.resolve(__dirname, "..");
const BILDER = [
  { seite: "index.html?f=banner", breite: 1280, hoehe: 256, dichte: 2, datei: "banner.png", schriften: ["Saira Condensed", "Inter"] },
  { seite: "index.html?f=social", breite: 1280, hoehe: 640, dichte: 1, datei: "social-preview.png", schriften: ["Saira Condensed", "Inter"] },
  { seite: "vorschau.html", breite: 1240, hoehe: 830, dichte: 2, datei: "vorschau-karten.png", schriften: ["Inter"] },
];

(async () => {
  const nur = process.argv[2];
  const browser = await chromium.launch();
  const fehler = [];
  for (const b of BILDER) {
    if (nur && b.datei !== nur) continue;
    // Dichte ueber CSS-zoom statt deviceScaleFactor: Mit emulierter Dichte
    // setzt Chromium Symbole (SVG) nur auf ganze CSS-Pixel, Text aber feiner;
    // die Anhebung der Plattform-Symbole (0,09 em) ginge so verloren. Mit zoom
    // wird wie auf einem echten Display auf Bildpunkte gerundet.
    const seite = await browser.newPage({ viewport: { width: b.breite * b.dichte, height: b.hoehe * b.dichte }, deviceScaleFactor: 1 });
    seite.on("pageerror", (e) => fehler.push(`${b.datei}: ${e.message}`));
    await seite.goto(`${BASIS}/${b.seite}`);
    await seite.evaluate((z) => { document.documentElement.style.zoom = z; }, b.dichte);
    await seite.waitForFunction(() => window.fertig, null, { timeout: 30000 });
    await seite.waitForTimeout(300);
    const geladen = await seite.evaluate(() => [...document.fonts].filter((x) => x.status === "loaded").map((x) => x.family.replace(/"/g, "")));
    for (const s of b.schriften) {
      if (!geladen.includes(s)) fehler.push(`${b.datei}: Schrift ${s} nicht geladen`);
    }
    await seite.locator(".rahmen").screenshot({ path: path.join(ZIEL, b.datei), omitBackground: true });
    console.log(`${b.datei}: ${b.breite * b.dichte} x ${b.hoehe * b.dichte}`);
    await seite.close();
  }
  await browser.close();
  if (fehler.length) {
    console.error(fehler.join("\n"));
    process.exit(1);
  }
})();
