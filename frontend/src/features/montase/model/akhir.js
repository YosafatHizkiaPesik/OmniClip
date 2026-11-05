/**
 * Akhir video (JOB-5 O6): Shorts diputar berulang, dan tontonan ulang ikut
 * dihitung dalam persentase yang ditonton. Dua hal yang merusaknya dan bisa
 * dinilai dari dokumen saja:
 *
 *   - EKOR MATI: suara (narasi, musik) yang lebih panjang dari gambar terakhir
 *     meninggalkan layar hitam di ujung video, dan banyak penonton menggeser di
 *     situ, bukan menonton ulang;
 *   - AKHIR YANG TIDAK MENYAMBUNG: lompatan keras dari akhir ke awal membuat
 *     putaran ulang terasa sebagai video baru yang belum tentu ingin ditonton.
 *
 * Usulannya berupa operasi (model/usulan.js): potong ekor tanpa gambar, lalu
 * sambungkan dengan SAMBUNG_DETIK pertama gambar video ditaruh lagi di ujung,
 * sehingga bingkai terakhir sama dengan bingkai pertama saat diputar ulang.
 */

export const SAMBUNG_DETIK = 1;
export const SHORTS_MAKS_DETIK = 180;
const EKOR_DETIK = 0.3;

function visual(dokumen) {
  return dokumen.lajur.filter((l) => !l.sembunyi && l.jenis === 'video')
    .flatMap((l) => l.item.map((i) => ({ ...i, lajurId: l.id })));
}

export function periksaAkhir(dokumen) {
  const fps = dokumen.kanvas.fps;
  const gambar = visual(dokumen);
  const ujungGambar = gambar.reduce((m, i) => Math.max(m, i.mulai + i.durasi), 0);
  const ekor = Math.max(0, (dokumen.durasi || 0) - ujungGambar) / fps;
  const tegak = dokumen.kanvas.tinggi > dokumen.kanvas.lebar;
  const detik = (dokumen.durasi || 0) / fps;
  const pertama = [...gambar].sort((a, b) => a.mulai - b.mulai)[0];
  const terakhir = [...gambar].sort((a, b) => (b.mulai + b.durasi) - (a.mulai + a.durasi))[0];
  // Sudah menyambung: item terakhir adalah potongan awal bahan yang sama dengan item pertama.
  const menyambung = Boolean(pertama && terakhir && pertama !== terakhir && terakhir.bahan === pertama.bahan
    && Math.abs((terakhir.potong_awal || 0) - (pertama.potong_awal || 0)) <= 1);
  return {
    ekorMati: ekor > EKOR_DETIK ? ekor : 0,
    shortsTerlaluPanjang: tegak && detik > SHORTS_MAKS_DETIK,
    menyambung,
    adaGambar: gambar.length > 0,
    baik: ekor <= EKOR_DETIK && !(tegak && detik > SHORTS_MAKS_DETIK) && menyambung,
    ujungGambar,
  };
}

/**
 * Operasi usulan akhir menyambung. `label(kunci)` menerjemahkan label (t dari
 * useT), supaya model tetap murni.
 */
export function usulanAkhir(dokumen, label = (k) => k) {
  const fps = dokumen.kanvas.fps;
  const cek = periksaAkhir(dokumen);
  const ops = [];
  if (!cek.adaGambar) return ops;
  let ujung = cek.ujungGambar;
  if (cek.ekorMati) {
    for (const l of dokumen.lajur) {
      if (l.kunci || l.jenis === 'video') continue;
      for (const i of l.item) {
        if (i.mulai + i.durasi > ujung && i.mulai < ujung) {
          ops.push({ id: `a${ops.length + 1}`, jenis: 'potong', kelompok: 'akhir', item: i.id, dari: ujung,
            sampai: i.mulai + i.durasi, label: label('ekor'), alasan: label('ekor_alasan') });
        }
      }
    }
  }
  if (!cek.menyambung) {
    const pertama = [...visual(dokumen)].sort((a, b) => a.mulai - b.mulai)[0];
    const panjang = Math.min(Math.round(SAMBUNG_DETIK * fps), pertama.durasi);
    const meta = dokumen.bahan?.[pertama.bahan] ?? {};
    ops.push({
      id: `a${ops.length + 1}`, jenis: 'klip', kelompok: 'akhir', label: label('sambung'),
      alasan: label('sambung_alasan'), bahan: pertama.bahan, bahan_info: { ...meta, jenis: meta.jenis || 'video' },
      mulai: ujung, potong_awal: pertama.potong_awal || 0, durasi: panjang,
    });
    ujung += panjang;
  }
  return ops;
}
