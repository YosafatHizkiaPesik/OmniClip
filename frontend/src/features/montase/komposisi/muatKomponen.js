/**
 * Memuat komponen animasi hasil kompilasi Mesin Montase.
 *
 * Mesin mengubah sumber TSX/JSX menjadi CommonJS (`require(...)`, sucrase),
 * lalu di sini kode itu dijalankan dengan `require` buatan sendiri yang HANYA
 * mengembalikan modul yang diizinkan kontrak (JOB-4.md bagian 21). Tiga alasan
 * memilih cara ini daripada `import()` dari URL:
 *
 *   - komponen memakai React dan Remotion yang SAMA dengan komposisinya. Dua
 *     salinan React di satu pohon membuat hook gagal;
 *   - cara yang sama bekerja di Player dan di bundel render, tanpa penyusun
 *     modul tambahan di salah satunya;
 *   - impor yang tidak diizinkan gagal saat dimuat, bukan diam-diam berhasil.
 *
 * Pemeriksaan keamanan yang sebenarnya ada di mesin (kompilasi.mjs) dan di
 * kotak pasir pratinjau; `require` di sini adalah lapis terakhir.
 */
import React from 'react';
import * as jsxRuntime from 'react/jsx-runtime';
import * as Remotion from 'remotion';
import { cancelRender, continueRender, delayRender } from 'remotion';
import * as zod from 'zod';
import * as Shapes from '@remotion/shapes';
import * as Paths from '@remotion/paths';
import * as Noise from '@remotion/noise';
import * as ZodTypes from '@remotion/zod-types';
import * as Transitions from '@remotion/transitions';

// Sama dengan IMPOR_DIIZINKAN di montase-mesin/src/kompilasi.mjs (dijaga
// test_montase_batas.py): yang lolos pemeriksa mesin harus bisa dimuat di sini.
export const MODUL_DIIZINKAN = Object.freeze({
  'react': React,
  'react/jsx-runtime': jsxRuntime,
  'remotion': Remotion,
  'zod': zod,
  '@remotion/shapes': Shapes,
  '@remotion/paths': Paths,
  '@remotion/noise': Noise,
  '@remotion/zod-types': ZodTypes,
  '@remotion/transitions': Transitions,
});

/** Menjalankan kode CommonJS hasil kompilasi dan mengembalikan `exports`-nya. */
export function jalankanModul(kode) {
  const module = { exports: {} };
  const requireTerbatas = (nama) => {
    if (!Object.prototype.hasOwnProperty.call(MODUL_DIIZINKAN, nama)) {
      throw new Error(`Impor tidak diizinkan di komponen animasi: ${nama}`);
    }
    return MODUL_DIIZINKAN[nama];
  };
  // eslint-disable-next-line no-new-func
  const fungsi = new Function('require', 'module', 'exports', kode);
  fungsi(requireTerbatas, module, module.exports);
  return module.exports;
}

const _simpanan = new Map();

/** Satu unduhan per alamat, dipakai bersama semua item yang memakai komponen itu. */
export function muatModul(url) {
  if (!_simpanan.has(url)) {
    const janji = fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`Komponen tidak bisa dimuat (${r.status}): ${url}`);
        return r.text();
      })
      .then(jalankanModul);
    janji.catch(() => _simpanan.delete(url));
    _simpanan.set(url, janji);
  }
  return _simpanan.get(url);
}

/**
 * Hook: modul komponen untuk `url`, atau null selama dimuat.
 *
 * `delayRender` dipanggil di penginisialisasi `useState`, yaitu sebelum
 * bingkai pertama selesai. Kalau dipanggil di `useEffect`, mesin render bisa
 * memotret bingkainya lebih dulu dan animasinya hilang dari bingkai awal.
 */
export function useKomponen(url) {
  const [modul, setModul] = React.useState(null);
  const [tahan] = React.useState(() => (url ? delayRender(`Memuat komponen ${url}`) : null));
  React.useEffect(() => {
    if (!url) return undefined;
    let hidup = true;
    muatModul(url)
      .then((m) => {
        if (hidup) setModul(m);
        if (tahan !== null) continueRender(tahan);
      })
      .catch((e) => cancelRender(e));
    return () => { hidup = false; };
  }, [url, tahan]);
  return modul;
}
