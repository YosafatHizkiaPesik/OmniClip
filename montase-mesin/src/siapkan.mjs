/**
 * Memastikan Chrome Headless Shell ada, mengunduhnya bila belum.
 *
 * Keluaran: { "siap": true, "browser": jalur atau null, "detik": ... }
 *
 * Remotion menyimpannya di dalam node_modules mesin ini (folder `.remotion`),
 * dan karena mesinnya sendiri dipasang di folder data OmniClip, browsernya
 * ikut tinggal di sana, bukan di folder aplikasi yang tidak bisa ditulis.
 */
import { ensureBrowser } from '@remotion/renderer';
import { jalankan, tulis } from './alat.mjs';

await jalankan(async (m) => {
  const mulai = Date.now();
  let persenTerakhir = -1;
  const status = await ensureBrowser({
    browserExecutable: m.browser ?? null,
    logLevel: 'error',
    onBrowserDownload: () => ({
      version: null,
      onProgress: ({ percent }) => {
        const persen = Math.floor(percent * 100);
        if (persen !== persenTerakhir) {
          persenTerakhir = persen;
          tulis({ unduh: percent });
        }
      },
    }),
  });
  tulis({
    siap: true,
    browser: status?.path ?? null,
    jenis: status?.type ?? null,
    detik: (Date.now() - mulai) / 1000,
  });
});
