/**
 * Meter orisinalitas langsung (JOB-5 O1), dihitung dari dokumen proyek tanpa
 * server, supaya terlihat SAAT menyunting, bukan baru sesudah ekspor.
 *
 * Skornya rumus yang sama dengan `nilai_tambah.py` (lapisan ekspor M6.2):
 * narasi/rekaman dihitung penuh, teks/animasi/sisipan setengah, subtitle tidak
 * dihitung; dibagi panjang video. "Cukup" juga sama dengan gerbang tinjau:
 * dengan video orang lain wajib ada narasi atau rekaman paling sedikit 2 detik
 * (keputusan T-3); tanpa video orang lain selalu cukup.
 *
 * Yang ditambahkan di sini dan tidak ada di skor: CELAH. Kebijakan konten
 * yang digunakan ulang YouTube menolak "klip yang disambung dengan sedikit
 * atau tanpa narasi". Skor rata-rata bisa terlihat cukup sementara satu klip
 * panjang di tengah tetap potongan polos. Celah = rentang video orang lain
 * lebih dari CELAH_DETIK tanpa tambahan apa pun di dalamnya, dan tanpa narasi
 * yang baru selesai (KONTEKS_DETIK) sebelumnya: narasi yang memperkenalkan
 * klip tepat sebelum klip itu diputar (susunan Top 5 asisten) memang
 * komentar atas klip itu.
 */

export const CELAH_DETIK = 12;
export const KONTEKS_DETIK = 3;
export const KOMENTAR_MIN = 2;
export const SKOR_MIN = 0.08;
const BOBOT_SISIPAN = 0.5;
const ASAL_LAIN = new Set(['unduhan', 'klip_jadi']);

/** Panjang gabungan rentang [a, b) yang mungkin bertumpuk. */
export function gabung(rentang) {
  const urut = rentang.filter(([a, b]) => b > a).sort((x, y) => x[0] - y[0]);
  const hasil = [];
  for (const [a, b] of urut) {
    const akhir = hasil.at(-1);
    if (akhir && a <= akhir[1]) akhir[1] = Math.max(akhir[1], b);
    else hasil.push([a, b]);
  }
  return hasil;
}
const panjang = (rentang) => gabung(rentang).reduce((n, [a, b]) => n + (b - a), 0);

/** Rentang `utuh` dikurangi rentang `lubang`. */
function kurangi(utuh, lubang) {
  let sisa = gabung(utuh);
  for (const [a, b] of gabung(lubang)) {
    sisa = sisa.flatMap(([x, y]) => {
      if (b <= x || a >= y) return [[x, y]];
      const potong = [];
      if (a > x) potong.push([x, a]);
      if (b < y) potong.push([b, y]);
      return potong;
    });
  }
  return sisa;
}

/**
 * `asalBahan`: Map id bahan -> asal ('unduhan', 'klip_jadi', 'impor', 'tts',
 * 'rekam', ...), dari daftar Bahan saya. Bahan yang asalnya tidak diketahui
 * dianggap milik sendiri, supaya meter tidak menuduh tanpa bukti.
 */
export function hitungOrisinalitas(dokumen, asalBahan = new Map()) {
  const fps = dokumen.kanvas.fps;
  const durasi = Math.max(1, dokumen.durasi || 1);
  const lain = [];
  const suaraTts = [];
  const suaraSendiri = [];
  const tambahan = [];
  const lajurVideo = dokumen.lajur.filter((l) => l.jenis === 'video');
  const utama = lajurVideo[0]?.id;
  for (const l of dokumen.lajur) {
    if (l.sembunyi || l.subtitle) continue;
    for (const i of l.item) {
      const r = [i.mulai, i.mulai + i.durasi];
      const asal = i.bahan ? asalBahan.get(i.bahan) : null;
      if ((i.jenis === 'video' || i.jenis === 'gambar') && ASAL_LAIN.has(asal)) {
        lain.push(r);
        if (l.id !== utama) tambahan.push(r);      // gambar-dalam-gambar tetap suntingan
      } else if (i.jenis === 'audio' && !l.bisu) {
        if (asal === 'rekam' || i.narasi?.direkam) suaraSendiri.push(r);
        else if (i.narasi || asal === 'tts') suaraTts.push(r);
      } else if (i.jenis === 'teks' || i.jenis === 'motion') {
        tambahan.push(r);
      } else if ((i.jenis === 'gambar' || i.jenis === 'video') && l.id !== utama) {
        tambahan.push(r);
      }
    }
  }
  const suara = [...suaraTts, ...suaraSendiri];
  const detikSuara = panjang(suara) / fps;
  const detikTambahan = panjang(tambahan) / fps;
  const detikLain = panjang(lain) / fps;
  const skor = Math.min(1, (detikSuara + BOBOT_SISIPAN * detikTambahan) / (durasi / fps));
  const adaLain = lain.length > 0;
  const cukup = adaLain ? detikSuara >= KOMENTAR_MIN : true;

  // Celah: video orang lain tanpa tambahan di dalamnya dan tanpa narasi yang
  // baru selesai sebelumnya.
  const pengantar = suara.map(([a, b]) => [a, b + KONTEKS_DETIK * fps]);
  const celah = kurangi(lain, [...suara, ...tambahan, ...pengantar])
    .filter(([a, b]) => b - a > CELAH_DETIK * fps)
    .map(([dari, sampai]) => ({ dari, sampai, mulai: dari / fps, detik: (sampai - dari) / fps }));

  const saran = [];
  if (adaLain && detikSuara < KOMENTAR_MIN) saran.push({ kunci: 'wajib_narasi' });
  if (adaLain && suaraSendiri.length === 0 && suaraTts.length > 0) saran.push({ kunci: 'suara_sendiri' });
  if (celah.length) saran.push({ kunci: 'celah', n: celah.length });
  if (adaLain && detikLain / (durasi / fps) > 0.85 && skor < 0.15) saran.push({ kunci: 'dominan_lain' });

  let tingkat = 'baik';
  if (!cukup) tingkat = 'kurang';
  else if (adaLain && (celah.length || skor < 0.15)) tingkat = 'sedang';

  return {
    persen: Math.round(skor * 100),
    cukup,
    tingkat,
    adaLain,
    detik: {
      suara: detikSuara, sendiri: panjang(suaraSendiri) / fps, tambahan: detikTambahan,
      lain: detikLain, total: durasi / fps,
    },
    celah,
    saran,
  };
}
