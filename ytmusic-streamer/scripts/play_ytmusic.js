const puppeteer = require('puppeteer-core');

(async () => {
  const browser = await puppeteer.connect({
    browserWSEndpoint: 'ws://ytmusic_headless:3000'
  });

  const page = await browser.newPage();
  await page.goto('https://music.youtube.com');

  console.log('YouTube Music geladen.');

  // Optional: manuelles Login durchführen, Cookies speichern

  // Beispiel: nach Chillout Music suchen
  await page.type('input[placeholder="Suchen"]', 'Chillout Music');
  await page.keyboard.press('Enter');

  console.log('Suchanfrage abgeschickt.');

  // Warte, bis Ergebnisse erscheinen
  await page.waitForTimeout(5000);

  // Play-Button klicken (du musst evtl. den genauen Selektor anpassen)
  const playButton = await page.$('ytmusic-play-button-renderer');
  if (playButton) {
    await playButton.click();
    console.log('Song gestartet!');
  } else {
    console.log('Kein Play-Button gefunden.');
  }
})();

