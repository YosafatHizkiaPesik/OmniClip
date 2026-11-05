/**
 * Pemeriksaan lengkap satu komponen animasi (JOB-4 M4.4).
 *
 * Masukan (stdin):
 *   { "serve_url": folder bundel, "sumber": "<TSX>", "kanvas": {lebar, tinggi, fps},
 *     "durasi": bingkai | null, "props": {...} | null, "keluar": folder PNG,
 *     "browser": jalur Chrome | null }
 * Keluaran (stdout, satu JSON):
 *   { "lolos": false, "tahap_gagal": "kompilasi"|"ekspor"|"render", "masalah": [...] }
 *   atau { "lolos": true, "js": "...", "ekspor": [...], "peringatan": [...],
 *          "bingkai": [{"bingkai": n, "berkas": "...png", "ms": 812}], "durasi": n }
 *
 * Komponen dirender LEWAT KOMPOSISI YANG SAMA dengan proyek (satu item motion
 * di dokumen sementara), jadi yang diperiksa persis jalur yang nanti dipakai
 * pratinjau dan ekspor. Kodenya diberikan sebagai alamat `data:` sehingga
 * tidak ada server tambahan. `periksa: true` di item membuat komposisi
 * MELEMPAR galat (bukan menggambar kotak merah) bila props tidak sah, supaya
 * pemeriksaan gagal dengan pesan yang bisa dikembalikan ke AI.
 *
 * Lima bingkai di 10/30/50/70/90% durasi. Bingkai kosong atau lima bingkai
 * yang sama persis dinilai di sisi Python (montase/periksa.py), yang membaca
 * berkas PNG ini.
 */
import path from 'node:path';
import { openBrowser, renderStill, selectComposition } from '@remotion/renderer';
import { jalankan, tulis } from './alat.mjs';
import { kompilasi } from './kompilasi.mjs';

const ID_KOMPOSISI = 'Montase';
const BATAS_MS_BINGKAI = 5000;
const EKSPOR_WAJIB = ['skema', 'contohProps'];

await jalankan(async (m) => {
  const hasil = kompilasi(m.sumber ?? '');
  if (!hasil.lolos) {
    tulis({ lolos: false, tahap_gagal: 'kompilasi', masalah: hasil.masalah, peringatan: hasil.peringatan ?? [] });
    return;
  }
  const kurang = EKSPOR_WAJIB.filter((n) => !hasil.ekspor.includes(n));
  if (kurang.length) {
    tulis({
      lolos: false, tahap_gagal: 'ekspor', peringatan: hasil.peringatan,
      masalah: kurang.map((n) => `Ekspor "${n}" wajib ada: panel properti dibuat dari situ.`),
    });
    return;
  }
  const k = m.kanvas ?? {};
  const fps = k.fps ?? 30;
  const durasi = Math.max(10, Math.round(m.durasi ?? 2 * fps));
  const dokumen = {
    versi: 1, id: 'periksa', nama: 'periksa', durasi,
    kanvas: { lebar: k.lebar ?? 1080, tinggi: k.tinggi ?? 1920, fps, latar: '#000000' },
    bahan: {}, penanda: [], ekspor: {},
    lajur: [{
      id: 'L1', jenis: 'motion', nama: 'Animasi',
      item: [{ id: 'm1', jenis: 'motion', komponen: 'periksa', versi: 1, mulai: 0, durasi, props: m.props ?? {}, periksa: true }],
    }],
  };
  const sumber = {
    bahan: {}, font: m.font ?? {},
    komponen: { 'periksa@1': `data:text/javascript;base64,${Buffer.from(hasil.js).toString('base64')}` },
  };
  const bersama = {
    serveUrl: m.serve_url,
    inputProps: { dokumen, sumber },
    browserExecutable: m.browser ?? null,
    logLevel: 'error',
    timeoutInMilliseconds: 30000,
  };
  const bingkai = [];
  // Satu Chrome untuk pemilihan komposisi dan kelima bingkai; tanpa ini
  // setiap renderStill membuka Chrome baru (beberapa detik per bingkai).
  const browser = await openBrowser('chrome', {
    browserExecutable: m.browser ?? null, chromiumOptions: {}, logLevel: 'error',
  });
  bersama.puppeteerInstance = browser;
  try {
    const komposisi = await selectComposition({ ...bersama, id: ID_KOMPOSISI });
    for (const p of [0.1, 0.3, 0.5, 0.7, 0.9]) {
      const f = Math.min(durasi - 1, Math.round(durasi * p));
      const berkas = path.join(m.keluar, `bingkai_${f}.png`);
      const mulai = Date.now();
      await renderStill({ ...bersama, composition: komposisi, frame: f, output: berkas, imageFormat: 'png', overwrite: true });
      bingkai.push({ bingkai: f, berkas, ms: Date.now() - mulai });
    }
  } catch (e) {
    const pesan = String(e?.message ?? e).split('\n').slice(0, 6).join('\n');
    tulis({ lolos: false, tahap_gagal: 'render', masalah: [`Render gagal: ${pesan}`], peringatan: hasil.peringatan });
    return;
  } finally {
    await browser.close({ silent: true }).catch(() => {});
  }
  // Bingkai pertama ikut memuat Chrome dan komponen; yang dinilai sisanya.
  const lambat = bingkai.slice(1).filter((b) => b.ms > BATAS_MS_BINGKAI);
  if (lambat.length) {
    tulis({
      lolos: false, tahap_gagal: 'render', peringatan: hasil.peringatan, bingkai,
      masalah: [`Satu bingkai butuh lebih dari ${BATAS_MS_BINGKAI / 1000} detik (${Math.max(...lambat.map((b) => b.ms))} ms). Sederhanakan animasinya.`],
    });
    return;
  }
  tulis({ lolos: true, js: hasil.js, ekspor: hasil.ekspor, peringatan: hasil.peringatan, bingkai, durasi });
});
