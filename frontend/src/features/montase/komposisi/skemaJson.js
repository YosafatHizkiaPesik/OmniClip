/**
 * Skema props komponen animasi -> JSON Schema (JOB-4 M4.5).
 *
 * Panel properti di editor dibangun dari JSON Schema, bukan dari objek zod,
 * karena komponen buatan AI hanya boleh DIJALANKAN di dalam iframe kotak
 * pasir: iframe menghitung skemanya dengan fungsi ini lalu mengirim hasilnya
 * (data biasa) ke editor lewat postMessage. Animasi bawaan memakai fungsi
 * yang sama langsung di editor.
 */
import { z } from 'zod';

const BATAS = 50000;

export function skemaJson(modul) {
  if (!modul?.skema) return null;
  try {
    const hasil = z.toJSONSchema(modul.skema, { unrepresentable: 'any', io: 'input' });
    return JSON.stringify(hasil).length > BATAS ? null : hasil;
  } catch {
    return null;
  }
}

/** Salinan contohProps yang aman dikirim lewat postMessage (data biasa saja). */
export function contohAman(modul) {
  try {
    const teks = JSON.stringify(modul?.contohProps ?? {});
    return teks.length > BATAS ? {} : JSON.parse(teks);
  } catch {
    return {};
  }
}
