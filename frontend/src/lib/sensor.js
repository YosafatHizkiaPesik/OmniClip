/**
 * Menyensor kata kasar di subtitle pratinjau: "anjing" jadi "anj*ng".
 *
 * Kembaran dari `backend/app/services/sensor.py`, dan HARUS sama persis
 * dengannya: pratinjau yang menampilkan kata utuh sementara hasil render
 * menyensornya adalah kebohongan yang baru ketahuan sesudah merender.
 * Uji `test_sensor_kata.py` membandingkan kedua daftar ini dan gagal bila
 * salah satunya berubah sendiri.
 *
 * Daftar ini diturunkan dari sisi Python, jangan disunting langsung di sini.
 */

export const DAFTAR_KASAR = [
  'anjing',
  'anjeng',
  'asu',
  'asw',
  'bangsat',
  'bajingan',
  'brengsek',
  'keparat',
  'bedebah',
  'goblok',
  'tolol',
  'sialan',
  'kampret',
  'bacot',
  'kontol',
  'memek',
  'pepek',
  'peler',
  'titit',
  'jembut',
  'itil',
  'silit',
  'toket',
  'ngentot',
  'entot',
  'kentot',
  'ngewe',
  'coli',
  'colmek',
  'bokep',
  'perek',
  'pelacur',
  'lonte',
  'sundal',
  'jalang',
  'bispak',
  'gigolo',
  'jancok',
  'jancuk',
  'diancuk',
  'kimak',
  'pukimak',
  'puki',
  'bangke',
  'tai',
  'taik',
  'telek',
  'fuck',
  'fucking',
  'fucker',
  'motherfucker',
  'shit',
  'bullshit',
  'bitch',
  'asshole',
  'bastard',
  'cunt',
  'whore',
  'slut',
  'nigga',
  'dickhead',
  'wanker',
  'twat',
  'pussy',
];

const AKHIRAN = ['nya', 'lah', 'mu', 'ku', 'an', 'in'];

const POLA = new RegExp(
  `\\b(${[...DAFTAR_KASAR].sort((a, b) => b.length - a.length).join('|')})(${AKHIRAN.join('|')})?\\b`,
  'gi',
);

/** Menutup satu huruf di tengah kata, bentuk besar-kecilnya dipertahankan. */
function tutup(kata) {
  const n = kata.length;
  if (n < 3) return kata;
  const i = n >= 4 ? Math.floor(n / 2) : 1;
  return kata.slice(0, i) + '*' + kata.slice(i + 1);
}

/** Mengganti kata kasar di sebuah kalimat. Kata lain tidak disentuh. */
export function sensorTeks(teks) {
  if (!teks) return teks;
  return String(teks).replace(POLA, (_, dasar, akhiran) => tutup(dasar) + (akhiran || ''));
}
