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
import ClipPreview, { CaptionOverlay } from '../src/features/studio/ClipPreview.jsx';
import UploadModal from '../src/components/UploadModal.jsx';
import GoogleAccountCard from '../src/components/GoogleAccountCard.jsx';
import FrameStage from '../src/features/studio/FrameStage.jsx';
import FramePanel from '../src/features/studio/FramePanel.jsx';
import { presetLayout, serializeLayout, coverPercent } from '../src/features/studio/frames.js';

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

const layout = presetLayout('reaction-stack');
const pip = presetLayout('pip-corner');

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
  // Overlay diuji sendiri: di dalam ClipPreview ia baru muncul setelah
  // ResizeObserver mengisi tinggi kotak, yang tidak pernah terjadi di sini.
  ['CaptionOverlay + gagang', <CaptionOverlay line={clip.subtitles[0]} activeWordIndex={0}
                                              style={style} clipTime={1} boxH={533}
                                              ghost={false} draggable dragging={null}
                                              onMoveStart={noop} onSizeStart={noop}
                                              onWidthLeftStart={noop} onWidthRightStart={noop} />],
  ['CaptionOverlay tanpa gagang', <CaptionOverlay line={clip.subtitles[1]} activeWordIndex={-1}
                                                  style={style} clipTime={3} boxH={533}
                                                  ghost draggable={false} dragging={null} />],
  ['ClipPreview susunan bingkai', <ClipPreview src="/x.mp4" clip={clip} aspectRatio="9:16"
                                               style={style} frameMode="layout" layout={layout}
                                               onLayoutChange={noop} onStyleChange={noop}
                                               frameEditing selectedFrameId={layout.frames[0].id}
                                               onSelectFrame={noop} />],
  ['ClipPreview sisipan pojok latar hitam',
    <ClipPreview src="/x.mp4" clip={clip} aspectRatio="9:16" style={style}
                 frameMode="layout" layout={{ ...pip, background: 'black' }}
                 onLayoutChange={noop} onStyleChange={noop} />],
  ['FrameStage susun sendiri', <FrameStage src="/x.mp4" frameMode="layout" layout={layout}
                                           onLayoutChange={noop} onSelectFrame={noop}
                                           selectedFrameId={layout.frames[1].id} />],
  ['FrameStage ikut wajah', <FrameStage src="/x.mp4" frameMode="smart"
                                        reframe={{ available: true, crop_w: 405, source_w: 1280,
                                                   keyframes: [[0, 100], [1, 140]] }} />],
  ['FrameStage potong tengah', <FrameStage src="/x.mp4" frameMode="center" aspectRatio="9:16" />],
  ['FrameStage tanpa sumber', <FrameStage src={null} frameMode="original" />],
  ['FramePanel susun sendiri', <FramePanel frameMode="layout" onFrameModeChange={noop}
                                           layout={layout} onLayoutChange={noop}
                                           selectedFrameId={layout.frames[0].id}
                                           onSelectFrame={noop} />],
  ['FramePanel ikut wajah', <FramePanel frameMode="smart" onFrameModeChange={noop}
                                        layout={layout} onLayoutChange={noop}
                                        selectedFrameId={null} onSelectFrame={noop} />],
  ['UploadModal', <UploadModal clip={{ file_name: 'Klip-Uji_klip-01_00m15s.mp4',
                                       metadata: { hook_text: 'CONTOH HOOK' } }}
                               onClose={noop} onDone={noop} />],
  ['GoogleAccountCard', <GoogleAccountCard card={{ padding: 16 }}
                                           sectionTitle={{ fontWeight: 700 }}
                                           helpText={{ fontSize: '.8rem' }} />],
];

// Geometri 'cover' harus cocok dengan `scale=…:increase,crop=…` di ffmpeg.
// Kalau tidak, pratinjaunya berbohong tentang hasil rendernya.
//
// Diuji sifatnya, bukan angka yang saya ketik sendiri: potongan sumber harus
// MENUTUPI kotak tujuan di kedua sisi, menyentuhnya persis di sisi yang
// mengikat, memakai rasio video aslinya, dan kelebihannya terpotong rata.
// Angka harapan yang ditulis tangan hanya menguji apakah saya bisa berhitung.
//
// Satuannya persen kotak tujuan, jadi "menutupi" berarti >= 100.
const geoCases = [
  ['sumber utuh ke kanvas tegak', { x: 0, y: 0, w: 100, h: 100 }, { x: 0, y: 0, w: 100, h: 100 }, 16 / 9, 9 / 16],
  ['pojok 30% ke pita atas', { x: 0, y: 0, w: 30, h: 30 }, { x: 0, y: 0, w: 100, h: 38 }, 16 / 9, 9 / 16],
  ['pita tengah ke sisipan pojok', { x: 25, y: 20, w: 50, h: 60 }, { x: 4, y: 64, w: 40, h: 24 }, 4 / 3, 9 / 16],
  ['sumber tegak ke kanvas lebar', { x: 0, y: 10, w: 100, h: 40 }, { x: 10, y: 10, w: 60, h: 80 }, 9 / 16, 16 / 9],
];
for (const [name, src, dst, srcAspect, canvasAspect] of geoCases) {
  const g = coverPercent(src, dst, srcAspect, canvasAspect);
  const rw = (g.width * src.w) / 100;      // lebar potongan, % kotak tujuan
  const rh = (g.height * src.h) / 100;
  const boxAspect = (dst.w / dst.h) * canvasAspect;
  const covers = rw >= 99.99 && rh >= 99.99;
  const touches = Math.abs(rw - 100) < 0.01 || Math.abs(rh - 100) < 0.01;
  // Rasio video utuh di layar = (lebar% x lebar kotak) / (tinggi% x tinggi kotak)
  const shownAspect = (g.width / g.height) * boxAspect;
  const keepsAspect = Math.abs(shownAspect - srcAspect) < 0.001;
  const left = g.left + (src.x / 100) * g.width;
  const top = g.top + (src.y / 100) * g.height;
  const centred = Math.abs(left - (100 - rw) / 2) < 0.01
    && Math.abs(top - (100 - rh) / 2) < 0.01;
  const ok = covers && touches && keepsAspect && centred;
  console.log(`  ${ok ? 'ok   ' : 'GAGAL'} geometri ${name}: potongan ${rw.toFixed(1)}%x${rh.toFixed(1)}%`
    + (ok ? '' : ` (menutupi=${covers} menyentuh=${touches} rasio=${keepsAspect} terpusat=${centred})`));
  if (!ok) process.exitCode = 1;
}

// Bentuk yang dikirim ke server tidak boleh membawa kunci yang tak dikenal ffmpeg.
const wire = serializeLayout(layout);
const keys = Object.keys(wire.frames[0]).sort().join(',');
console.log(`  ${keys === 'dst,fit,label,src' ? 'ok   ' : 'GAGAL'} muatan bingkai: ${keys}`);
if (keys !== 'dst,fit,label,src') process.exitCode = 1;

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
