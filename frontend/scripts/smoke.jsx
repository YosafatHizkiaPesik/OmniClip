/**
 * Uji asap render: memastikan komponen tampilan benar-benar BISA dirender,
 * bukan sekadar bisa dibundel.
 *
 * Bug yang memicu berkas ini: VideoCards.jsx memanggil formatTime tanpa
 * meng-import-nya. Bundelnya sukses (pengenal bebas baru gagal saat dijalankan),
 * rutenya menjawab HTTP 200 (server mengirim index.html apa pun isinya), dan
 * halamannya jadi putih kosong di browser. Dua pemeriksaan yang saya andalkan
 * dulu keduanya lolos — jadi keduanya memang tidak menguji hal yang benar.
 *
 * Merender ke string di Node menjalankan badan komponennya sungguhan, dan itu
 * yang menangkapnya.
 */
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { VideoCard, RelatedVideoCard } from '../src/components/VideoCards.jsx';

const video = {
  id: 'dQw4w9WgXcQ',
  title: 'Contoh judul video yang cukup panjang untuk membungkus dua baris',
  channel: 'Kanal Uji',
  duration: 4127,
  views: 1234567,
  thumbnail: 'https://example.invalid/t.jpg',
  upload_date: '20240101',
};

const cases = [
  ['VideoCard', <VideoCard video={video} onSelect={() => {}} />],
  ['VideoCard tanpa durasi/views', <VideoCard video={{ ...video, duration: 0, views: 0 }} onSelect={() => {}} />],
  ['RelatedVideoCard', <RelatedVideoCard video={video} onSelect={() => {}} />],
];

let failed = 0;
for (const [name, element] of cases) {
  try {
    const html = renderToStaticMarkup(element);
    if (!html || html.length < 40) throw new Error('keluaran kosong');
    console.log(`  ok    ${name} (${html.length} karakter)`);
  } catch (err) {
    failed += 1;
    console.error(`  GAGAL ${name}: ${err.message}`);
  }
}
console.log(failed ? `\n${failed} komponen gagal dirender` : '\nSemua komponen berhasil dirender');
process.exit(failed ? 1 : 0);
