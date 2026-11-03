/**
 * Riwayat batal/ulang (JOB-4 M2.1): sampai 100 langkah, fungsi murni.
 *
 * Dokumen proyek kecil dan setiap operasi menghasilkan objek baru yang
 * berbagi bagian yang tidak berubah, jadi menyimpan seluruh dokumen per
 * langkah murah dan jauh lebih sederhana daripada menyimpan kebalikan setiap
 * operasi.
 *
 * Mengetik di panel Properti menghasilkan satu perubahan per huruf. Perubahan
 * dengan `gabung` yang sama dalam GABUNG_MS digabung jadi satu langkah, jadi
 * Ctrl+Z membatalkan satu kata, bukan satu huruf. Menyeret item menghasilkan
 * satu perubahan per bingkai layar; seretan memakai `gabung` unik per seretan
 * dengan `jendela: Infinity`, jadi satu seretan = satu langkah walau tangan
 * berhenti sebentar di tengahnya.
 */
export const BATAS_LANGKAH = 100;
export const GABUNG_MS = 900;

export function buatRiwayat(kini) {
  return { lalu: [], kini, nanti: [], gabung: null, waktu: 0 };
}

export function catat(r, baru, { gabung = null, waktu = Date.now(), jendela = GABUNG_MS } = {}) {
  if (baru === r.kini) return r;
  if (gabung && r.gabung === gabung && waktu - r.waktu < jendela && r.lalu.length) {
    // Seretan yang kembali persis ke keadaan sebelum seretan dimulai tidak
    // meninggalkan langkah kosong di riwayat.
    if (baru === r.lalu[r.lalu.length - 1]) {
      return { ...r, lalu: r.lalu.slice(0, -1), kini: baru, nanti: [], gabung: null, waktu };
    }
    return { ...r, kini: baru, nanti: [], waktu };
  }
  const lalu = [...r.lalu, r.kini].slice(-BATAS_LANGKAH);
  return { lalu, kini: baru, nanti: [], gabung, waktu };
}

export function batal(r) {
  if (!r.lalu.length) return r;
  return {
    lalu: r.lalu.slice(0, -1), kini: r.lalu[r.lalu.length - 1],
    nanti: [r.kini, ...r.nanti], gabung: null, waktu: 0,
  };
}

export const bisaBatal = (r) => Boolean(r?.lalu.length);
export const bisaUlang = (r) => Boolean(r?.nanti.length);

export function ulang(r) {
  if (!r.nanti.length) return r;
  return {
    lalu: [...r.lalu, r.kini].slice(-BATAS_LANGKAH), kini: r.nanti[0],
    nanti: r.nanti.slice(1), gabung: null, waktu: 0,
  };
}
