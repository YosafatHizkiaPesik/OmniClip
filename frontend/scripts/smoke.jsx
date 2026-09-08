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
import { TrimPanel, SubtitlePanel, StylePanel } from '../src/features/studio/EditorPanels.jsx';
import ClipPreview from '../src/features/studio/ClipPreview.jsx';

const video = {
  id: 'dQw4w9WgXcQ',
  title: 'Contoh judul video yang cukup panjang untuk membungkus dua baris',
  channel: 'Kanal Uji',
  duration: 4127,
  views: 1234567,
  thumbnail: 'https://example.invalid/t.jpg',
  upload_date: '20240101',
};

const style = {
  size: 96, primary: '#FFFFFF', highlight: '#FFE500',
  speaker_colors: ['#FFFFFF', '#7CFFB2', '#FFB3C7', '#B39DFF'],
  position: 'bottom', margin_v: 300, outline_px: 7, pos_x: 50, box_w: 84,
  uppercase: true, animation: 'karaoke_pop', font: 'Montserrat',
};

const clip = {
  clip_id: 'c1',
  index: 1,
  segments: [{ start: 15, end: 61.2 }],
  start_seconds: 15,
  end_seconds: 61.2,
  duration: 46.2,
  score: 85,
  hook_text: 'CONTOH HOOK KLIP',
  subtitles: [
    { start: 0.4, end: 2.1, text: 'Halo semuanya', speaker: 0,
      words: [{ w: 'Halo', s: 0.4, e: 1.2 }, { w: 'semuanya', s: 1.2, e: 2.1 }] },
    { start: 2.3, end: 4.0, text: 'Apa kabar', speaker: 1,
      words: [{ w: 'Apa', s: 2.3, e: 3.0 }, { w: 'kabar', s: 3.0, e: 4.0 }] },
  ],
};

const noop = () => {};

const cases = [
  ['VideoCard', <VideoCard video={video} onSelect={noop} />],
  ['VideoCard tanpa durasi/views', <VideoCard video={{ ...video, duration: 0, views: 0 }} onSelect={noop} />],
  ['RelatedVideoCard', <RelatedVideoCard video={video} onSelect={noop} />],
  ['TrimPanel', <TrimPanel clip={clip} videoDuration={4127} busy={false}
                           onNudge={noop} onSetBounds={noop}
                           onAddSegment={noop} onRemoveSegment={noop} />],
  ['SubtitlePanel', <SubtitlePanel clip={clip} onUpdate={noop} onRemove={noop}
                                   style={style} onAutoSpeakers={noop}
                                   speakerCount={3} speakerConfident
                                   onRedetect={noop} redetecting={false} />],
  ['SubtitlePanel tanpa subtitle', <SubtitlePanel clip={{ ...clip, subtitles: [] }}
                                                  onUpdate={noop} onRemove={noop} style={style} />],
  // Tiap bagian dirender terbuka satu per satu: isi bagian yang tertutup tidak
  // pernah dijalankan, jadi kesalahan di dalamnya lolos dari uji ini.
  ...['preset', 'warna', 'font', 'posisi', 'judul', 'rasio'].map((section) => [
    `StylePanel bagian "${section}"`,
    <StylePanel style={style} onChange={noop} speakerCount={4}
                aspectRatio="9:16" onAspectChange={noop}
                showHook={section === 'judul'} onShowHookChange={noop}
                hookText="Judul contoh" onHookTextChange={noop}
                defaultSection={section} />,
  ]),
  ['ClipPreview', <ClipPreview src="/x.mp4" clip={clip} aspectRatio="9:16"
                               style={style} frameMode="blur" onStyleChange={noop} />],
  ['ClipPreview tanpa klip', <ClipPreview src={null} clip={null} style={style} />],
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
