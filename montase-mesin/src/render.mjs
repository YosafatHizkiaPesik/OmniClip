/**
 * Merender satu dokumen proyek menjadi MP4.
 *
 * Masukan (stdin):
 *   { "serve_url": folder bundel, "dokumen": {...}, "sumber": {...},
 *     "keluar": jalur .mp4, "crf": 18, "concurrency": null,
 *     "browser": jalur Chrome Headless Shell atau null }
 * Keluaran (stdout, satu JSON per baris):
 *   { "tahap": "menyiapkan" }
 *   { "kemajuan": 0.42, "bingkai": 380, "total": 900 }
 *   { "selesai": true, "berkas": "...", "detik": 143.2, "bingkai": 900 }
 *   atau { "galat": "..." }
 *
 * SIGTERM membatalkan render dengan rapi (cancelSignal), supaya Chrome ikut
 * ditutup. Python tetap mematikan seluruh pohon prosesnya sesudah tenggat
 * kalau itu tidak terjadi.
 */
import process from 'node:process';
import { makeCancelSignal, renderMedia, selectComposition } from '@remotion/renderer';
import { jalankan, tulis } from './alat.mjs';

const ID_KOMPOSISI = 'Montase';

await jalankan(async (m) => {
  const { cancelSignal, cancel } = makeCancelSignal();
  process.on('SIGTERM', () => cancel());
  process.on('SIGINT', () => cancel());

  const inputProps = { dokumen: m.dokumen, sumber: m.sumber ?? {} };
  const bersama = {
    serveUrl: m.serve_url,
    inputProps,
    browserExecutable: m.browser ?? null,
    logLevel: 'error',
    chromiumOptions: { gl: m.gl ?? null },
    timeoutInMilliseconds: m.batas_ms ?? 60000,
  };
  tulis({ tahap: 'menyiapkan' });
  const mulai = Date.now();
  const komposisi = await selectComposition({ ...bersama, id: ID_KOMPOSISI });
  let terakhir = -1;
  await renderMedia({
    ...bersama,
    composition: komposisi,
    codec: 'h264',
    crf: m.crf ?? 18,
    outputLocation: m.keluar,
    concurrency: m.concurrency ?? null,
    overwrite: true,
    cancelSignal,
    onProgress: ({ progress, renderedFrames }) => {
      // Satu baris per persen sudah cukup; ribuan baris per detik hanya
      // membebani pembaca di sisi Python.
      const persen = Math.floor(progress * 100);
      if (persen === terakhir) return;
      terakhir = persen;
      tulis({ kemajuan: progress, bingkai: renderedFrames, total: komposisi.durationInFrames });
    },
  });
  tulis({
    selesai: true,
    berkas: m.keluar,
    detik: (Date.now() - mulai) / 1000,
    bingkai: komposisi.durationInFrames,
    lebar: komposisi.width,
    tinggi: komposisi.height,
    fps: komposisi.fps,
  });
});
