/**
 * Garis putar (posisi bingkai) sebagai penyimpan kecil di luar state React.
 *
 * Pratinjau melaporkan bingkai sekitar 30 kali per detik saat diputar. Kalau
 * bingkai itu state editor, seluruh editor (linimasa 50 item, panel bahan,
 * panel properti) digambar ulang 30 kali per detik dan pemutaran tersendat.
 * Dengan penyimpan ini hanya yang memang menampilkan bingkai (garis di
 * linimasa, penunjuk waktu) yang ikut digambar ulang; operasi seperti "belah
 * di garis putar" cukup membaca `garis.get()`.
 */
import { useSyncExternalStore } from 'react';

export function buatGaris(awal = 0) {
  let nilai = awal;
  const pendengar = new Set();
  return {
    get: () => nilai,
    set: (v) => {
      if (v === nilai) return;
      nilai = v;
      pendengar.forEach((f) => f());
    },
    subscribe: (f) => {
      pendengar.add(f);
      return () => pendengar.delete(f);
    },
  };
}

export function useGaris(garis) {
  return useSyncExternalStore(garis.subscribe, garis.get);
}

/** Kode waktu mm:ss:bb (bb = bingkai), seperti penunjuk waktu Premiere. */
export function kodeWaktu(bingkai, fps) {
  const b = Math.max(0, Math.round(bingkai));
  const detik = Math.floor(b / fps);
  const sisa = b % fps;
  const m = Math.floor(detik / 60);
  const s = detik % 60;
  const dua = (n) => String(n).padStart(2, '0');
  return `${dua(m)}:${dua(s)}:${dua(sisa)}`;
}

/** Jenis data seret dari panel Bahan ke linimasa. */
export const JENIS_SERET_BAHAN = 'application/x-omniclip-bahan';
