/**
 * Pembantu bersama semua perintah mesin.
 *
 * Antarmuka Python -> Node sengaja sederhana: masukan SATU objek JSON di stdin,
 * keluaran satu objek JSON PER BARIS di stdout. Python membaca baris demi baris,
 * jadi kemajuan sampai saat itu juga, dan satu baris rusak tidak merusak sisanya.
 * Pesan lain (log Remotion, peringatan Node) pergi ke stderr dan tidak pernah
 * dibaca sebagai hasil.
 */
import process from 'node:process';

export async function bacaMasukan() {
  const potongan = [];
  for await (const p of process.stdin) potongan.push(p);
  const teks = Buffer.concat(potongan).toString('utf8').trim();
  return teks ? JSON.parse(teks) : {};
}

export function tulis(objek) {
  process.stdout.write(`${JSON.stringify(objek)}\n`);
}

/** Menjalankan `kerja`, dan galat apa pun menjadi satu baris `{galat}` + kode keluar 1. */
export async function jalankan(kerja) {
  try {
    await kerja(await bacaMasukan());
  } catch (e) {
    tulis({ galat: String(e?.message ?? e).slice(0, 2000) });
    process.exitCode = 1;
  }
}
