/**
 * Preset caption subtitle Montase (JOB-5 P1).
 *
 * Satu preset = `gaya` lengkap untuk item teks subtitle. Diterapkan ke SELURUH
 * lajur subtitle sekaligus (`terapkanCaption`), dan disimpan di lajurnya
 * (`gaya_caption`) supaya subtitle yang dibuat ulang memakai gaya yang sama.
 *
 * `sorot` = cara kata yang sedang diucapkan ditandai (ItemTeks):
 *   warna  kata aktif berganti warna (`warna_sorot`);
 *   kotak  kotak berwarna di belakang kata aktif;
 *   besar  kata aktif membesar sesaat dan berganti warna.
 * Preset tanpa `warna_sorot` tidak menyorot apa pun (sinema, minimal).
 *
 * Wujudnya meniru keluarga tema subtitle Studio Klip (services/tema.py) tetapi
 * dibuat dengan kemampuan ItemTeks; definisi Studio ada di features/studio
 * yang tidak boleh diimpor Montase (JOB-4 bagian 15).
 */
const DASAR = {
  ukuran: 76, kapital: true, letak: 'bawah', perataan: 'tengah', latar: 'tanpa',
  warna_latar: '#000000', alfa_latar: 1, garis: 0, warna_garis: '#000000', bayang: 0, kabur: 0,
  gerak: 'muncul', sorot: 'warna', warna_sorot: null,
};

export const PRESET_CAPTION = [
  { id: 'sorot_kuning', gaya: { font: 'Montserrat', warna: '#ffffff', garis: 7, warna_sorot: '#FFE500' } },
  { id: 'kotak_ungu', gaya: { font: 'Montserrat', warna: '#ffffff', bayang: 4, sorot: 'kotak', warna_sorot: '#7C3AED' } },
  { id: 'kotak_hijau', gaya: { font: 'Archivo Black', ukuran: 70, warna: '#ffffff', garis: 5, sorot: 'kotak', warna_sorot: '#16A34A' } },
  { id: 'pantul', gaya: { font: 'Luckiest Guy', ukuran: 82, warna: '#ffffff', garis: 8, sorot: 'besar', warna_sorot: '#FFE500', gerak: 'pop' } },
  { id: 'tebal_bayang', gaya: { font: 'Anton', ukuran: 88, warna: '#ffffff', bayang: 8, warna_sorot: '#FF3355' } },
  { id: 'neon', gaya: { font: 'Bebas Neue', ukuran: 96, warna: '#E0F7FF', kabur: 6, warna_garis: '#00E5FF', warna_sorot: '#00E5FF' } },
  { id: 'stiker', gaya: { font: 'Lilita One', ukuran: 72, kapital: false, warna: '#111111', latar: 'pelat', warna_latar: '#FFE500', warna_sorot: '#E11D2E', radius: 0.3 } },
  { id: 'berita', gaya: { font: 'Oswald', ukuran: 64, warna: '#ffffff', latar: 'pita', warna_latar: '#E11D2E', warna_sorot: '#FFE500' } },
  { id: 'sinema', gaya: { font: 'Poppins', ukuran: 56, kapital: false, warna: '#ffffff', latar: 'sorot', warna_latar: '#000000', alfa_latar: 0.65 } },
  { id: 'minimal', gaya: { font: 'Poppins', ukuran: 62, kapital: false, warna: '#ffffff', garis: 4 } },
].map((p) => ({ ...p, gaya: { ...DASAR, ...p.gaya } }));

export function presetCaption(id) {
  return PRESET_CAPTION.find((p) => p.id === id) ?? null;
}

/**
 * Gaya preset ke setiap item teks di lajur subtitle; teks, kata berwaktu,
 * dan posisi (`ubah`) tidak disentuh. Satu langkah batal.
 */
export function terapkanCaption(dokumen, lajurId, presetId) {
  const p = presetCaption(presetId);
  const lajur = dokumen.lajur.find((l) => l.id === lajurId);
  if (!p || !lajur || lajur.kunci) return dokumen;
  return {
    ...dokumen,
    lajur: dokumen.lajur.map((l) => (l.id !== lajurId ? l : {
      ...l,
      gaya_caption: presetId,
      item: l.item.map((i) => (i.jenis === 'teks' ? { ...i, gaya: { ...p.gaya } } : i)),
    })),
  };
}
