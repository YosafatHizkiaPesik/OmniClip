import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowLeft, Menu, X, Scissors, Type, Palette, Download, Loader2, CheckCircle2,
  AlertTriangle, Crop, Plus, Trash2, Play, Save, Tag, Undo2, Redo2, Clapperboard, RefreshCw, Wand2,
  FolderOpen,
} from 'lucide-react';
import { apiGet, apiPost, dijalankanDiKomputerIni, downloadToDisk, kategoriKlip } from '../../lib/api';
import { loadFonts } from '../../lib/fonts';
import { formatTime } from '../../utils/timeFormat';
import { useClipEditor } from './useClipEditor';
import ClipPreview from './ClipPreview';
import StaveSystem, { rehearsalLetter } from './StaveSystem';
import { TrimPanel, SubtitlePanel, StylePanel } from './EditorPanels';
import FrameStage from './FrameStage';
import ClipTimeline from './ClipTimeline';
import FramePanel from './FramePanel';
import TitlePanel from './TitlePanel';
import SutradaraPanel from './SutradaraPanel';
import VideoHilang from './VideoHilang';
import MediaPanel from './MediaPanel';
import TerjemahPanel, { buatKedua } from './TerjemahPanel';

/** Sama dengan sidikUtama di TerjemahPanel: penanda terjemahan usang. */
function sidikUtamaKlip(lines) {
  return (lines ?? []).map((l) => `${(+l.start).toFixed(2)}|${(+l.end).toFixed(2)}|${l.text}`).join('\n');
}
import CariUlangDialog from './CariUlangDialog';
import {
  loadFraming, saveFraming, serializeLayout, clipTimeFor, sourceTimeFor,
  personKeyAt, withPersonKey,
  presentPeople,
  GAMING_WAJAH_BAWAAN, gamingPadaWaktu, newFrameId, reaksiAktif, selaraskanBentuk, rasioKeluaran,
  susunanDariServer,
  susunGaming,
  CANVAS_ASPECT, layoutDariCrop, pusatWajahPada,
} from './frames';

const DEFAULT_STYLE = {
  size: 96, primary: '#FFFFFF', highlight: '#FFE500',
  // Diindeks langsung: [0] orang pertama. Putih di depan supaya video satu
  // narasumber tampil persis seperti sebelum warna per orang ada.
  speaker_colors: ['#FFFFFF', '#7CFFB2', '#FFB3C7', '#B39DFF',
                   '#FFD166', '#5BC8FF', '#FF9F1C', '#B8FF3A'],
  // false = satu warna sepanjang klip. Bawaannya mati sejak 24 September 2026:
  // pemisahan penutur baru benar 62% pada uji terakhir, dan empat dari sepuluh
  // kalimat berwarna salah lebih mengganggu daripada satu warna yang tidak
  // pernah salah. Palet di atas tetap tersimpan, menunggu sakelar di
  // Pengaturan dinyalakan lagi.
  per_speaker_colors: false,
  // Jarak antar kata dalam satuan em. Cermin dari JARAK_KATA di backend.
  jarak_kata: 0.46,
  position: 'bottom', margin_v: 300, outline_px: 7,
  // Penempatan mendatar dalam persen lebar kanvas: titik tengah kotak teks dan
  // lebarnya. Keduanya diubah dengan menyeret subtitle di pratinjau.
  pos_x: 50, box_w: 84,
  uppercase: true, animation: 'karaoke_pop', font: 'Montserrat',
  // Tanda air. Ikut gaya, bukan ikut klip: ini nama kanal, dan menuliskannya
  // ulang di tiap klip adalah pekerjaan yang tidak ada gunanya.
  watermark: '',
  // Tanda air punya gaya sendiri, tidak meminjam dari subtitle. Font kosong
  // berarti "ikut font subtitle"; posisinya persen kanvas dan menunjuk titik
  // TENGAH teksnya, sama seperti pos_x subtitle.
  wm_font: '', wm_size: 34, wm_color: '#FFFFFF', wm_opacity: 0.62,
  wm_x: 92, wm_y: 95, wm_outline: 2,
};

const STYLE_KEY = 'omniclip_caption_style';

/**
 * Gaya teks bertahan antar sesi.
 *
 * Menyetel font, warna, dan ukuran adalah pekerjaan sekali untuk sebuah kanal,
 * bukan sekali per klip. Tanpa ini, tiap kali editor dibuka semuanya kembali ke
 * bawaan dan seluruh penyetelan harus diulang.
 */
const HEX = /^#[0-9A-Fa-f]{6}$/;

/**
 * Membuang warna yang tidak bisa dipakai ffmpeg dari gaya tersimpan.
 *
 * Sebuah preset pernah menyimpan `var(--danger)` sebagai warna sorotan. Nilai
 * itu ikut tersimpan di peramban dan bertahan di sana meski presetnya sudah
 * dibetulkan. Sejak server menolak warna yang bukan heksadesimal — dan memang
 * harus menolaknya, supaya kekeliruan begini tidak lagi lolos jadi "putih
 * diam-diam" — gaya lama itu akan membuat render GAGAL, bukan sekadar salah
 * warna. Jadi dibersihkan saat dimuat, sekali, tanpa pengguna perlu tahu.
 */
function bersihkanWarna(gaya) {
  const out = { ...gaya };
  for (const k of ['primary', 'highlight', 'wm_color']) {
    if (typeof out[k] === 'string' && !HEX.test(out[k].trim())) out[k] = DEFAULT_STYLE[k];
  }
  if (Array.isArray(out.speaker_colors)) {
    out.speaker_colors = out.speaker_colors.map(
      (c, i) => (typeof c === 'string' && HEX.test(c.trim())
        ? c.trim() : (DEFAULT_STYLE.speaker_colors[i] ?? '#FFFFFF')),
    );
  }
  return out;
}

function loadStoredStyle() {
  try {
    const raw = JSON.parse(localStorage.getItem(STYLE_KEY) || 'null');
    return raw && typeof raw === 'object'
      ? bersihkanWarna({ ...DEFAULT_STYLE, ...raw }) : DEFAULT_STYLE;
  } catch {
    return DEFAULT_STYLE;
  }
}

// Di bawah ini dok berhenti berguna: penggaris dan lajur potongan saja sudah
// memakan sekitar seratus piksel.
const DOCK_MIN = 132;

const TABS = [
  { id: 'trim', label: 'Batas', Icon: Scissors },
  { id: 'subtitle', label: 'Subtitle', Icon: Type },
  { id: 'style', label: 'Gaya', Icon: Palette },
  { id: 'frame', label: 'Bingkai', Icon: Crop },
  { id: 'title', label: 'Judul', Icon: Tag },
  // Berkas dari luar video sumber.
  { id: 'media', label: 'Sisipan', Icon: Clapperboard },
  // Sutradara berdiri sendiri: ia menyusun SELURUH klip, bukan menambahkan
  // satu benda ke dalamnya, dan akan tumbuh ke gaya subtitle juga.
  { id: 'sutradara', label: 'Sutradara', Icon: Wand2 },
];

/**
 * Editor klip: video sumber panjang di timeline, hasil klip di kiri.
 *
 * Bentuknya sengaja mengikuti editor video pada umumnya — pratinjau di tengah,
 * timeline membentang di bawah, daftar hasil di samping — supaya batas klip
 * bisa digeser sambil melihat gelombang suara dan posisi klip lain sekaligus.
 */
export default function Editor({ project, onBack }) {
  const videoId = project?.video_id;
  const editor = useClipEditor();
  const videoRef = useRef(null);

  const [data, setData] = useState(null);
  // Dialog "Cari ulang klip": mesin/model lain tanpa mengunduh ulang.
  const [cariUlang, setCariUlang] = useState(false);
  const [error, setError] = useState(null);
  const [peaks, setPeaks] = useState([]);
  // Dibuka pada baris lirik: itulah isi bidang pandang pertama yang
  // dijanjikan, dan itu pula pekerjaan yang paling sering dilakukan di sini.
  // Panel alat mulai TERTUTUP. Studio ini dipakai untuk melihat gambarnya dan
  // memegang linimasa; panel yang berdiri terbuka sejak detik pertama memakan
  // sepertiga lebar untuk sesuatu yang belum tentu dibutuhkan.
  const [tab, setTab] = useState(null);
  // Sisipan yang sedang dipegang — disorot bersamaan di linimasa dan panel.
  const [sisipanTerpilih, setSisipanTerpilih] = useState(null);
  const [railOpen, setRailOpen] = useState(true);
  const [dockView, setDockView] = useState('clip');

  /**
   * Tinggi dok, ditentukan pengguna dengan menyeret tepi atasnya.
   *
   * Pembagian antara panggung dan linimasa tidak punya jawaban yang benar
   * untuk semua orang: layar 690 piksel tidak bisa memberi keduanya ruang
   * lapang sekaligus, dan siapa yang harus mengalah bergantung pada apa yang
   * sedang dikerjakan. Menyetel subtitle butuh linimasa tinggi; membingkai
   * wajah butuh gambar besar. Jadi angkanya diserahkan, bukan ditebak — dan
   * diingat, karena orang yang sudah memilih tidak mau memilih lagi tiap kali
   * membuka klip.
   */
  const [dockH, setDockH] = useState(() => {
    const tersimpan = Number(localStorage.getItem('omniclip.dockH'));
    if (tersimpan >= DOCK_MIN) return tersimpan;
    // Bawaannya 30% layar, dijepit di 190-300 piksel.
    //
    // Diturunkan dari 34% setelah diukur: pada layar 690 piksel, panggung dan
    // kanvas sama-sama terbatas TINGGI, bukan lebar — sumurnya 745 piksel
    // untuk video selebar 439, jadi 306 piksel menganggur di sisi yang tidak
    // mengikat. Di keadaan itu satu-satunya cara membesarkan gambar adalah
    // memberinya tinggi, dan tinggi itu hanya bisa datang dari dok. 190 piksel
    // masih memuat penggaris, lajur potongan, dan lajur arah bingkai — bagian
    // yang paling sering dipegang; sisanya digulir, dan siapa pun yang ingin
    // linimasa lebih tinggi tinggal menariknya sekali.
    return Math.round(Math.min(300, Math.max(190, window.innerHeight * 0.30)));
  });

  const dragDock = useCallback((e) => {
    e.preventDefault();
    const y0 = e.clientY;
    const h0 = dockH;
    const move = (ev) => {
      const max = Math.max(DOCK_MIN, window.innerHeight * 0.72);
      setDockH(Math.round(Math.min(max, Math.max(DOCK_MIN, h0 + (y0 - ev.clientY)))));
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      setDockH((h) => { localStorage.setItem('omniclip.dockH', String(h)); return h; });
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  }, [dockH]);
  const [style, setStyle] = useState(loadStoredStyle);
  const patchStyle = useCallback((patch) => setStyle((prev) => ({ ...prev, ...patch })), []);
  // Sakelar induk warna per penutur. Dibaca di sini, bukan di panel gayanya,
  // karena pratinjau dan muatan render membaca `style` yang sama: kalau hanya
  // panelnya yang tahu, pratinjau akan menampilkan warna yang tidak ikut
  // dirender. Gaya lama di peramban masih menyimpan `true`, jadi nilainya
  // diturunkan sekali di sini supaya keduanya sepakat.
  const [warnaPenutur, setWarnaPenutur] = useState(false);
  useEffect(() => {
    apiGet('/settings')
      .then((r) => {
        const boleh = r?.warna_penutur === true;
        setWarnaPenutur(boleh);
        if (!boleh) patchStyle({ per_speaker_colors: false });
      })
      .catch(() => {});
  }, [patchStyle]);
  const [aspectRatio, setAspectRatio] = useState('9:16');
  // Cara membingkai dan susunannya dipulihkan bersama-sama untuk video ini.
  // Susunan hidup di sini, bukan di dalam pratinjau, karena tiga tempat
  // membacanya sekaligus: meja bingkai, kanvas hasil, dan muatan render.
  const [framing] = useState(() => loadFraming(videoId));
  const [frameMode, setFrameMode] = useState(framing.mode);
  const [frameMotion, setFrameMotion] = useState('smooth');
  // Perbesaran bingkai wajah dan geseran tegaknya, per klip. Disimpan di
  // klipnya sendiri, bukan di sini: dua klip dari video yang sama boleh
  // membutuhkan bingkai yang berbeda, dan setelan yang ikut berpindah klip
  // adalah setelan yang salah di klip berikutnya.
  const [layout, setLayout] = useState(framing.layout);
  const [selectedFrameId, setSelectedFrameId] = useState(null);
  const [selectedLine, setSelectedLine] = useState(null);
  useEffect(() => { saveFraming(videoId, frameMode, layout); },
    [videoId, frameMode, layout]);
  const [constrained, setConstrained] = useState(true);
  // Judul mati secara bawaan: hasilnya lebih bersih, dan hook otomatis sering
  // kalah bagus dari klipnya sendiri.
  const [showHook, setShowHook] = useState(false);
  const [exporting, setExporting] = useState(false);
  // Unggah ke Drive tepat setelah klipnya jadi. Mati secara bawaan: mengirim
  // berkas keluar dari komputer harus jadi pilihan yang diambil, bukan yang
  // kebetulan terjadi karena tombol render ditekan.
  // Unggah sesudah render: {youtube, drive, privasi}. Nilai awalnya dari
  // setelan unggah otomatis profil aktif; mengubahnya berlaku untuk render
  // dari layar ini saja. Unggahannya diantrekan SERVER (services/unggah.py),
  // jadi tetap jalan walau halaman ini ditutup sebelum render selesai.
  const [unggahSetelah, setUnggahSetelah] = useState({ youtube: false, drive: false, privasi: 'private' });
  const [googleReady, setGoogleReady] = useState(null);
  const [exportLog, setExportLog] = useState([]);
  // Rencana crop untuk pratinjau — sama persis dengan yang dipakai render.
  const [reframe, setReframe] = useState(null);
  const [reframeLoading, setReframeLoading] = useState(false);
  // Penanda masuk/keluar untuk memotong klip sendiri.
  const [mark, setMark] = useState({ in: null, out: null });
  const [redetecting, setRedetecting] = useState(false);
  const [retitling, setRetitling] = useState(false);
  const [saving, setSaving] = useState(null);
  const [sourceTime, setSourceTime] = useState(0);

  const { clips, selected, checked } = editor;

  /**
   * Tanda linimasa untuk mode ikut-wajah: [{t, person}] dalam waktu KLIP.
   *
   * Disimpan PADA KLIPNYA, bukan di state layar ini. Dua akibatnya keduanya
   * penting: tandanya ikut tersimpan bersama susunan, jadi tidak hilang saat
   * halaman ditutup; dan tiap klip membawa tandanya sendiri, jadi berpindah
   * huruf tidak lagi membuang pekerjaan — yang perlu, karena nomor orang
   * ditentukan per klip dan "orang 2" di klip lain belum tentu orang yang sama.
   */
  const personKeys = useMemo(() => selected?.person_keys ?? [], [selected]);

  /**
   * Linimasa pembingkaian klip ini. Disimpan bersama klipnya, bukan di tingkat
   * proyek: cara membingkai yang benar ditentukan isi klipnya sendiri, dan dua
   * klip dari video yang sama sering menuntut perlakuan yang berbeda.
   */
  const frameKeys = useMemo(() => selected?.frame_keys ?? [], [selected]);

  /**
   * Potongan lajur Bingkai tempat garis main sedang berada.
   *
   * Dipakai supaya PRATINJAU mengikuti linimasa, bukan hanya hasil render.
   * Tanpa ini memilih "Kotak tetap" di linimasa tidak mengubah apa pun di
   * layar — pratinjaunya tetap memperlihatkan bingkai yang mengikuti wajah,
   * dan pilihannya terasa seperti tombol yang tidak tersambung ke mana-mana.
   */
  const kunciBingkaiAktif = useMemo(() => {
    if (!selected || !frameKeys.length) return null;
    const t = clipTimeFor(selected.segments, sourceTime);
    let aktif = null;
    for (const k of [...frameKeys].sort((a, b) => (a.t ?? 0) - (b.t ?? 0))) {
      if ((k.t ?? 0) <= t + 1e-6) aktif = k;
    }
    return aktif;
  }, [frameKeys, selected, sourceTime]);

  // Mode yang benar-benar berlaku sekarang: linimasa menang atas mode tunggal,
  // sama seperti aturan di server.
  const frameModeEfektif = kunciBingkaiAktif?.mode || frameMode;


  const setFrameKeys = useCallback((next) => {
    if (!selected) return;
    const value = typeof next === 'function' ? next(selected.frame_keys ?? []) : next;
    // Setiap potongan "Susun sendiri" memegang SALINAN susunannya sendiri.
    //
    // Potongan tanpa susunan dulu meminjam susunan milik klip — dan semua
    // potongan peminjam menampilkan hal yang sama. Terlapor: menata potongan
    // pertama, membelah, menata ulang yang kedua, lalu kembali ke awal — yang
    // pertama ikut berubah menjadi tataan terbaru.
    const salin = (l) => (l?.frames?.length
      ? { ...l, frames: l.frames.map((f) => ({ ...f, id: newFrameId() })) } : l);
    const milikSendiri = (value ?? []).map((k) => (
      k.mode === 'layout' && !k.layout?.frames?.length && layout?.frames?.length
        ? { ...k, layout: salin(layout) } : k));
    editor.updateClip(selected.clip_id, { frame_keys: milikSendiri });
  }, [selected, editor, layout]);

  /**
   * Satu pintu untuk mengganti cara membingkai, dipakai panel Bingkai maupun
   * lajur linimasa.
   *
   * Sebelumnya keduanya menulis ke tempat yang berbeda — panel ke `frameMode`,
   * lajur ke `frame_keys` — dan tidak ada yang membaca tulisan yang lain.
   * Akibatnya persis seperti yang dilaporkan: memilih "Susun sendiri" di panel
   * lalu menggambar dua bingkai, sementara lajurnya tetap menyala di "Wajah".
   * Dua tempat yang menjawab pertanyaan yang sama harus punya satu jawaban.
   */
  const pilihCaraBingkai = useCallback((mode) => {
    const kunci = selected?.frame_keys ?? [];
    if (kunci.length >= 2) {
      // Sudah ada linimasa: yang diganti adalah potongan tempat garis main
      // berdiri. Mengganti seluruh klip di sini akan menghapus pekerjaan
      // memotong yang sudah dilakukan.
      const t = clipTimeFor(selected.segments, sourceTime);
      let sasaran = kunci[0];
      for (const k of [...kunci].sort((a, b) => (a.t ?? 0) - (b.t ?? 0))) {
        if ((k.t ?? 0) <= t + 1e-6) sasaran = k;
      }
      setFrameKeys(kunci.map((k) => (k === sasaran
        ? { ...k, mode, layout: mode === 'layout' ? (k.layout ?? layout) : k.layout }
        : k)));
    } else {
      // Belum ada linimasa: satu cara untuk seluruh klip. Kunci sisa dibuang
      // supaya lajurnya tidak menampilkan potongan yang tidak berarti apa-apa.
      // Pilihannya dicatat PADA KLIP: membukanya lagi tidak ditimpa tebakan
      // isi klip, dan klip lain tetap memakai bingkai yang cocok untuk isinya.
      editor.updateClip(selected.clip_id, kunci.length
        ? { frame_keys: [], cara_bingkai: mode } : { cara_bingkai: mode });
      // Berpindah dari "Main game" ke "Susun sendiri" MEWARISI kedua bingkai
      // yang barusan dicari sistem. Tanpa ini keduanya hilang dan pengguna
      // kembali ke satu bingkai kosong — padahal justru di sinilah susunan
      // otomatis itu seharusnya bisa disesuaikan: geser sedikit, lalu pakai.
      //
      // Dengan id BARU per bingkai. Susunan dari server dulu datang tanpa id,
      // dan dua bingkai tanpa id adalah "bingkai yang sama" bagi penyeretnya:
      // terlapor, menyeret kotak hijau ikut memindahkan dan mengecilkan yang
      // biru.
      if (mode === 'layout' && frameModeEfektif === 'gaming' && layoutGamingRef.current) {
        const { gaming, reaksi, ...asal } = gamingPadaWaktu(   // eslint-disable-line no-unused-vars
          layoutGamingRef.current, clipTimeFor(selected.segments, sourceTime));
        setLayout({ ...asal,
                    frames: asal.frames.map((f) => ({ ...f, id: newFrameId() })) });
      } else if (mode === 'layout'
                 && (frameModeEfektif === 'smart' || frameModeEfektif === 'motion')) {
        // Berpindah dari bingkai yang mengikuti wajah: kotak pertamanya
        // diletakkan PERSIS di tempat kotak itu berdiri sekarang. Tanpa ini
        // susunannya mulai dari kotak bawaan yang tidak ada hubungannya dengan
        // apa yang barusan di layar, dan yang terlihat adalah gambar melompat
        // lalu berkedip hitam sesaat.
        const t = clipTimeFor(selected.segments, sourceTime);
        setLayout(layoutDariCrop(
          (reframe?.source_w && reframe?.source_h)
            ? reframe.source_w / reframe.source_h : 16 / 9,
          CANVAS_ASPECT[aspectRatio] ?? 9 / 16,
          pusatWajahPada(reframe, t)));
      }
      setFrameMode(mode);
    }
  }, [selected, sourceTime, setFrameKeys, frameModeEfektif, setLayout, editor,
      reframe, aspectRatio, layout]);

  /**
   * Susunan bingkai yang sedang berlaku.
   *
   * Tiap potongan waktu bisa punya susunannya sendiri — itulah yang membuat
   * "reaksi + gameplay" di satu bagian dan "reaksi penuh" di bagian lain bisa
   * hidup dalam satu klip. Selama linimasanya kosong, yang berlaku adalah
   * susunan milik klip seperti sebelumnya.
   */
  const layoutEfektif = (kunciBingkaiAktif?.mode === 'layout' && kunciBingkaiAktif.layout)
    ? kunciBingkaiAktif.layout
    : layout;

  /**
   * Menulis balik kotak yang baru diseret ke kunci yang sedang berlaku.
   *
   * Harus berada SESUDAH `setFrameKeys`: ia masuk daftar kebergantungan
   * useCallback, dan daftar itu dibaca saat render — bukan saat dipanggil.
   */
  const setKotakBingkai = useCallback((rect) => {
    if (!kunciBingkaiAktif) return;
    setFrameKeys((lama) => (lama ?? []).map((k) => (
      Math.abs((k.t ?? 0) - (kunciBingkaiAktif.t ?? 0)) < 1e-6 ? { ...k, rect } : k
    )));
  }, [kunciBingkaiAktif, setFrameKeys]);

  /**
   * Susunan dua bidang untuk mode "Main game", dicari dari videonya sendiri.
   *
   * Mode gaming memang sudah otomatis saat merender — server mencari letak
   * facecam-nya sendiri. Tapi sampai render selesai, pengguna tidak punya cara
   * melihat apa yang akan terjadi, dan "otomatis tapi tak terlihat" sulit
   * dibedakan dari "tidak bekerja". Susunannya diambil lebih awal supaya
   * pratinjaunya benar sejak sebelum dirender.
   */
  // Milik KLIP, bukan video: streamer memindahkan kamera wajahnya di tengah
  // siaran, jadi letak yang benar untuk satu klip bisa salah untuk klip lain.
  // Terlapor: klip M dibingkai di kiri atas karena memakai setelan klip lain.
  //
  // Yang disetel pengguna disimpan di klipnya (`susunan_game`, ikut Simpan).
  // Hasil pencarian otomatis cukup diingat di sini — menyimpannya ke klip akan
  // membuat "Simpan" menyala hanya karena sebuah klip dibuka.
  const [cacheGaming, setCacheGaming] = useState({});
  const layoutGaming = selected
    ? (selected.susunan_game ?? cacheGaming[selected.clip_id] ?? null) : null;
  // Dibaca oleh `pilihCaraBingkai`, yang dideklarasikan lebih dulu. Lewat ref,
  // bukan lewat daftar kebergantungan — itu yang dua kali membuat seluruh
  // Studio gagal dirender karena dipakai sebelum dideklarasikan.
  const layoutGamingRef = useRef(layoutGaming);
  layoutGamingRef.current = layoutGaming;
  const setLayoutGaming = useCallback((next) => {
    if (!selected) return;
    layoutGamingRef.current = next;
    editor.updateClip(selected.clip_id, { susunan_game: next });
  }, [selected, editor]);
  const [deteksiUlang, setDeteksiUlang] = useState(0);
  const [gamingSibuk, setGamingSibuk] = useState(false);
  const tKlip = selected ? clipTimeFor(selected.segments, sourceTime) : 0;

  useEffect(() => {
    if (frameModeEfektif !== 'gaming' || !selected?.segments?.length) return undefined;
    // Sudah disetel atau sudah dicari untuk klip ini: jangan ditimpa tebakan.
    if (layoutGamingRef.current?.frames?.length) return undefined;
    const idKlip = selected.clip_id;
    let batal = false;
    setGamingSibuk(true);
    apiPost('/clip-facecam', { video_id: videoId, segments: selected.segments })
      .then((r) => {
        if (batal) return;
        const l = susunanDariServer(r?.layout);
        const srcAspek = (r?.src_w && r?.src_h) ? r.src_w / r.src_h : 16 / 9;
        // Dihitung ulang untuk rasio keluaran yang sedang dipilih — server
        // menyusunnya untuk 9:16.
        const jadi = l && susunGaming(l, {
          wajah: l.gaming?.wajah ?? GAMING_WAJAH_BAWAAN,
          permainan: l.gaming?.permainan ?? 'isi',
          srcAspek, outAspek: rasioKeluaran(aspectRatio),
        });
        setCacheGaming((c) => ({ ...c, [idKlip]: jadi || null }));
      })
      .catch(() => { /* tanpa susunan: render mencari facecam sendiri */ })
      .finally(() => { if (!batal) setGamingSibuk(false); });
    return () => { batal = true; };
  }, [frameModeEfektif, selected?.clip_id, videoId, deteksiUlang]);   // eslint-disable-line

  /** Mengubah setelan Main game: tinggi wajah dan titik berangkat permainan. */
  const setelGaming = useCallback((ubah) => {
    const lama = layoutGamingRef.current;
    if (!lama?.frames?.length) return;
    setLayoutGaming(susunGaming(lama, {
      wajah: ubah.wajah ?? lama.gaming?.wajah ?? GAMING_WAJAH_BAWAAN,
      permainan: ubah.permainan ?? lama.gaming?.permainan ?? 'isi',
      srcAspek: lama.gaming?.sumber ?? 16 / 9,
      outAspek: rasioKeluaran(aspectRatio),
    }));
  }, [aspectRatio, setLayoutGaming]);

  /** Membuang setelan klip ini dan mencari letak facecam dari awal. */
  const ulangiGaming = useCallback(() => {
    if (!selected) return;
    layoutGamingRef.current = null;
    editor.updateClip(selected.clip_id, { susunan_game: null });
    setCacheGaming((c) => { const n = { ...c }; delete n[selected.clip_id]; return n; });
    setDeteksiUlang((n) => n + 1);
  }, [selected, editor]);

  // Rasio keluaran berubah (9:16 -> 1:1): bidangnya dihitung ulang; tebakan
  // yang belum disentuh dicari lagi untuk rasio baru.
  useEffect(() => {
    setCacheGaming({});
    if (selected?.susunan_game?.frames?.length) setelGaming({});
  }, [aspectRatio]);   // eslint-disable-line react-hooks/exhaustive-deps

  // Susunan yang dipakai pratinjau: milik gaming saat modenya gaming — dengan
  // kotak wajah yang berlaku pada detik ini.
  // Kunci game dari sutradara membawa susunannya sendiri (letak facecam pada
  // potongan itu); yang itu yang ditampilkan dan disunting.
  const kunciGamePunyaSusunan = frameModeEfektif === 'gaming'
    && !!kunciBingkaiAktif?.layout?.frames?.length;
  const susunanTampil = kunciGamePunyaSusunan ? kunciBingkaiAktif.layout
    : frameModeEfektif === 'gaming' ? gamingPadaWaktu(layoutGaming, tKlip) : layoutEfektif;

  /** Menulis susunan bingkai ke potongan yang berlaku, atau ke klip. */
  const setSusunanEfektif = useCallback((next) => {
    if (kunciGamePunyaSusunan) {
      setFrameKeys((lama) => (lama ?? []).map((k) => (
        Math.abs((k.t ?? 0) - (kunciBingkaiAktif.t ?? 0)) < 1e-6 ? { ...k, layout: next } : k
      )));
      return;
    }
    if (frameModeEfektif === 'gaming') {
      // `next` adalah susunan yang TAMPIL: kotak wajahnya milik letak yang
      // berlaku di detik ini, jadi hanya letak itu yang diubah.
      const lama = layoutGamingRef.current;
      if (!lama?.frames?.length) return;
      // Bebas seperti Susun sendiri: kotak sumber DAN bidang di kanvas
      // disimpan apa adanya. Hanya kotak wajah yang punya letak per waktu.
      const i = reaksiAktif(lama, tKlip);
      const reaksi = (lama.reaksi?.length ? lama.reaksi : [{ t: 0, src: lama.frames[1].src }])
        .map((r, j) => (j === i
          ? { ...r, src: next.frames[1].src, kotak: next.frames[1].src } : r));
      setLayoutGaming({ ...lama, reaksi, frames: next.frames });
      return;
    }
    const v = videoRef.current;
    const bentuk = {
      srcAspek: (v?.videoWidth && v?.videoHeight) ? v.videoWidth / v.videoHeight : 16 / 9,
      outAspek: rasioKeluaran(aspectRatio),
    };
    if (kunciBingkaiAktif?.mode === 'layout') {
      setFrameKeys((lama) => (lama ?? []).map((k) => (
        Math.abs((k.t ?? 0) - (kunciBingkaiAktif.t ?? 0)) < 1e-6
          ? { ...k, layout: selaraskanBentuk(k.layout, next, bentuk) } : k
      )));
      return;
    }
    setLayout((lama) => selaraskanBentuk(lama, next, bentuk));
  }, [kunciBingkaiAktif, frameModeEfektif, setLayoutGaming, setFrameKeys, setLayout,
      aspectRatio, tKlip, kunciGamePunyaSusunan]);
  const setPersonKeys = useCallback((next) => {
    if (!selected) return;
    const value = typeof next === 'function' ? next(selected.person_keys ?? []) : next;
    editor.updateClip(selected.clip_id, { person_keys: value });
  }, [selected, editor]);

  /**
   * Menyunting kartu judul dari mana pun — panel setelan maupun seretan
   * langsung di atas pratinjau.
   *
   * Satu jalan masuk untuk keduanya. Dua jalan berbeda akan berarti dua
   * gabungan yang sedikit berbeda, dan posisinya akan melompat tiap kali
   * pengguna berpindah antara menyeret dan mengetik angka.
   */
  const patchCard = useCallback((patch) => {
    if (!selected) return;
    editor.updateClip(selected.clip_id, {
      title_card: { ...selected.title_card, ...patch },
    });
  }, [selected, editor]);

  /**
   * Menandai bahwa studio sedang terbuka, di `body`.
   *
   * Tata letak berlabuh perlu mematikan gulir halaman dan padding kolom utama —
   * keduanya milik kerangka aplikasi, bukan milik komponen ini. Menandainya di
   * body membuat aturan CSS-nya bisa ditulis sebagai keturunan biasa alih-alih
   * bergantung pada `:has()`, yang dukungannya lebih baru daripada sisa
   * stylesheet ini dan akan gagal DIAM-DIAM: halamannya tetap tergambar, hanya
   * saja bisa digulir lagi — persis keluhan yang sedang dibetulkan.
   */
  useEffect(() => {
    document.body.classList.add('is-studio');
    return () => document.body.classList.remove('is-studio');
  }, []);

  /**
   * Menghapus satu klip, dengan konfirmasi.
   *
   * Konfirmasinya bukan basa-basi: klik kanan adalah gerakan yang mudah
   * terjadi tanpa sengaja, dan yang dihapus bisa jadi klip yang subtitlenya
   * sudah disunting berjam-jam.
   */
  const hapusKlip = useCallback((clipId, huruf) => {
    const klip = clips.find((c) => c.clip_id === clipId);
    if (!klip) return;
    const nama = (klip.title || klip.hook_text || '').trim().slice(0, 48);
    // eslint-disable-next-line no-alert
    if (!window.confirm(
      `Hapus klip ${huruf}${nama ? ` "${nama}"` : ''}?\n\n`
      + `${formatTime(klip.segments[0].start)} · ${Math.round(klip.duration || 0)} detik`)) {
      return;
    }
    editor.removeClip(clipId);
  }, [clips, editor]);

  useEffect(() => { loadFonts(); }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet('/uploads/google/status')
      .then((r) => { if (!cancelled) setGoogleReady(!!r.connected); })
      .catch(() => { if (!cancelled) setGoogleReady(false); });
    apiGet('/profil')
      .then((r) => {
        if (cancelled) return;
        const p = (r.profil ?? []).find((x) => x.id === r.aktif);
        const u = p?.unggah;
        if (u) {
          setUnggahSetelah({ youtube: !!(u.otomatis && u.youtube), drive: !!(u.otomatis && u.drive),
                             privasi: u.privasi || 'private' });
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  // Penyimpanan ditunda: menyeret subtitle memanggil patchStyle tiap frame, dan
  // menulis ke localStorage 60 kali per detik akan tersendat di perangkat lambat.
  useEffect(() => {
    const t = setTimeout(() => {
      try {
        localStorage.setItem(STYLE_KEY, JSON.stringify(style));
      } catch { /* mode privat: gaya tetap berlaku, hanya tidak diingat */ }
    }, 400);
    return () => clearTimeout(t);
  }, [style]);

  // Muat analisis tersimpan. Halaman ini hanya dibuka untuk project yang sudah
  // selesai, jadi tidak ada pekerjaan berat yang dimulai di sini.
  useEffect(() => {
    let cancelled = false;
    if (!videoId) return undefined;
    (async () => {
      try {
        const res = await apiGet(`/projects/${videoId}`);
        if (cancelled) return;
        setData(res);
        editor.load(videoId, res.clips || []);
      } catch (err) {
        if (!cancelled) setError(err);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId]);

  /**
   * Berkas yang DIPUTAR Studio: salinan ringan untuk sumber besar.
   *
   * Firefox memutar sumber 4K VP9 pada 0,44x kecepatan (terukur) — terlihat
   * macet atau hitam. Selama salinannya disiapkan, sumber asli yang diputar;
   * begitu siap, pemutar berpindah di detik yang sama tanpa menunggu F5.
   */
  const srcPutar = data?.preview_url || data?.local_url || null;
  // Bidang terbanyak di potongan Susun/game klip ini: pratinjau menyiapkan
  // pemutar sebanyak itu lebih dulu, supaya masuk ke potongannya tidak hitam.
  const cerminSiap = useMemo(() => {
    let n = 0;
    for (const k of selected?.frame_keys ?? []) {
      if (k.mode === 'layout') n = Math.max(n, k.layout?.frames?.length ?? 1);
      if (k.mode === 'gaming') n = Math.max(n, 2);
    }
    if ((selected?.frame_keys ?? []).length < 2) n = 0;   // satu kunci = satu cara, tidak ada pergantian
    return n;
  }, [selected?.frame_keys]);
  const posisiTukarRef = useRef(null);
  useEffect(() => {
    if (!videoId || !data?.pratinjau_disiapkan) return undefined;
    let batal = false;
    const id = setInterval(async () => {
      try {
        const segar = await apiGet(`/projects/${videoId}`);
        if (batal) return;
        if (segar.pratinjau_disiapkan) {
          // Persentasenya saja yang diperbarui. Tanpa ini angkanya beku di
          // nilai pertama dan kembali terbaca seperti macet.
          setData((d) => (d.pratinjau_kemajuan === segar.pratinjau_kemajuan
            ? d : { ...d, pratinjau_kemajuan: segar.pratinjau_kemajuan }));
          return;
        }
        const v = videoRef.current;
        posisiTukarRef.current = v ? { t: v.currentTime, main: !v.paused } : null;
        setData((d) => ({ ...d, preview_url: segar.preview_url, pratinjau_disiapkan: false }));
      } catch { /* dicoba lagi di putaran berikutnya */ }
    }, 8000);
    return () => { batal = true; clearInterval(id); };
  }, [videoId, data?.pratinjau_disiapkan]);
  useEffect(() => {
    const v = videoRef.current;
    const pos = posisiTukarRef.current;
    if (!v || !pos) return undefined;
    const pulihkan = () => {
      v.currentTime = pos.t;
      if (pos.main) v.play().catch(() => {});
      posisiTukarRef.current = null;
    };
    v.addEventListener('loadedmetadata', pulihkan, { once: true });
    return () => v.removeEventListener('loadedmetadata', pulihkan);
  }, [srcPutar]);

  // Gelombang suara dihitung terpisah: pada video panjang butuh belasan detik
  // pada pemanggilan pertama, dan editor tidak perlu menunggunya untuk tampil.
  useEffect(() => {
    let cancelled = false;
    if (!videoId) return undefined;
    apiGet(`/videos/${videoId}/waveform?bins=1200`)
      .then((res) => { if (!cancelled) setPeaks(res.peaks || []); })
      .catch(() => { /* timeline tetap berguna tanpa gelombang */ });
    return () => { cancelled = true; };
  }, [videoId]);

  const duration = data?.duration || project?.duration || 0;

  // Ambil rencana reframe setiap kali klip, rasio, atau mode bingkai berubah.
  // Dikunci pada susunan segmen, jadi menggeser batas ikut memperbarui bingkai.
  const segmentKey = selected
    ? selected.segments.map((s) => `${s.start.toFixed(2)}-${s.end.toFixed(2)}`).join(',')
    : '';

  /**
   * Bingkai bawaan klip ini, dibaca dari ISINYA.
   *
   * Dulu setiap klip dibuka dengan cara bingkai terakhir untuk videonya —
   * hampir selalu "ikut wajah" — sehingga klip game jadi close-up wajah di
   * kamera pojok. Sekarang server menggolongkan klipnya: permainan + facecam
   * → Main game; tanpa wajah → ikuti gerakan; wajah jelas → ikut wajah.
   * Cara yang DIPILIH pengguna untuk klip ini (`cara_bingkai`) selalu menang
   * dan ikut tersimpan bersama klipnya.
   */
  const [jenisKlip, setJenisKlip] = useState({});   // `${clip_id}|${segmen}` -> hasil | 'memuat'
  const jenisRef = useRef(jenisKlip);
  jenisRef.current = jenisKlip;
  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  const kunciJenis = (clip) => `${clip.clip_id}|${(clip.segments ?? [])
    .map((s) => `${s.start.toFixed(2)}-${s.end.toFixed(2)}`).join(',')}`;
  const jenisSekarang = selected ? jenisKlip[kunciJenis(selected)] : null;
  useEffect(() => {
    if (!selected?.segments?.length) return;
    if (selected.cara_bingkai) { setFrameMode(selected.cara_bingkai); return; }
    if (data?.downloaded === false) return;
    const kunci = kunciJenis(selected);
    const ada = jenisRef.current[kunci];
    if (ada?.mode) { setFrameMode(ada.mode); return; }
    if (ada === 'memuat') return;
    setJenisKlip((j) => ({ ...j, [kunci]: 'memuat' }));
    apiPost('/clip-jenis', { video_id: videoId, segments: selected.segments })
      .then((r) => {
        setJenisKlip((j) => ({ ...j, [kunci]: r }));
        // Diterapkan hanya bila klip itu masih yang terbuka dan pengguna
        // belum memilih sendiri selama menunggu.
        const kini = selectedRef.current;
        if (r?.mode && kini && kunciJenis(kini) === kunci && !kini.cara_bingkai) {
          setFrameMode(r.mode);
        }
      })
      .catch(() => setJenisKlip((j) => { const n = { ...j }; delete n[kunci]; return n; }));
  }, [selected?.clip_id, segmentKey, selected?.cara_bingkai, data?.downloaded, videoId]);   // eslint-disable-line react-hooks/exhaustive-deps
  const followKey = (layout?.frames ?? []).map((f) => (f.follow ? '1' : '0')).join('');
  // Lajur Bingkai yang berisi kunci ikut-wajah atau bingkai pengikut (reaksi
  // dari sutradara) butuh jejak wajah sepanjang klip — bukan hanya saat garis
  // main kebetulan berada di potongan ikut-wajah. Tanpa ini, jejaknya dibuang
  // setiap kali garis main masuk ke bidikan reaksi, dan bidikan itu diam.
  const kunciButuhJejak = (frameKeys ?? []).some((k) => (k.mode ?? 'smart') === 'smart'
    || (k.layout?.frames ?? []).some((f) => f.follow));
  // Apa yang menentukan WAJAH-WAJAHNYA — beda dari apa yang menentukan ke mana
  // bingkai diarahkan. Hanya perubahan yang pertama yang boleh mengosongkan
  // linimasa bingkai.
  // Orang yang benar-benar ada di klip ini. Panel bingkai dan linimasa harus
  // menawarkan daftar yang sama; dua daftar berbeda untuk hal yang sama adalah
  // cara tercepat membuat nomor orang berhenti berarti apa-apa.
  const orangHadir = useMemo(
    () => presentPeople(reframe, selected?.duration
      ?? (selected?.segments ?? []).reduce((a, x) => a + Math.max(0, x.end - x.start), 0)),
    [reframe, selected],
  );

  // Yang dijejak mengikuti cara membingkai yang SEDANG berlaku, termasuk yang
  // datang dari kunci di lajur Bingkai — kalau tidak, potongan "Gerak" di
  // tengah klip ber-mode wajah akan dipratinjau dengan jejak wajah.
  const subjekLacak = frameModeEfektif === 'motion' ? 'gerak' : 'wajah';
  // Jejak yang dibutuhkan klip ini SEPANJANG linimasanya — bukan hanya potongan
  // yang sedang diputar. Klip hasil sutradara berganti antara ikut wajah,
  // ikuti gerakan, dan game tiap beberapa detik.
  const subjekDibutuhkan = useMemo(() => {
    const set = new Set();
    if (frameMode === 'smart' || kunciButuhJejak
        || (frameMode === 'layout' && (layout?.frames ?? []).some((f) => f.follow))) set.add('wajah');
    if (frameMode === 'motion' || (frameKeys ?? []).some((k) => k.mode === 'motion')) set.add('gerak');
    return [...set].sort().join(',');
  }, [frameMode, kunciButuhJejak, layout, frameKeys]);
  const wantsTrack = frameModeEfektif === 'smart' || frameModeEfektif === 'motion'
    || (frameMode === 'layout' && (layout?.frames ?? []).some((f) => f.follow))
    || kunciButuhJejak;
  const penuturKlip = (selected?.subtitles ?? []).map((l) => l.speaker ?? '-').join('');
  /** Kunci simpanan jejak: semua yang menentukan hasilnya, tidak lebih. */
  const kunciJejak = (subjek) => [videoId, segmentKey, aspectRatio, frameMotion, subjek,
    subjek === 'wajah' ? JSON.stringify(personKeys ?? []) : '', penuturKlip].join('|');
  // Jejak yang sudah dihitung, per klip dan jenisnya.
  //
  // Dulu jejak dibuang dan diminta ulang setiap kali cara membingkai yang
  // BERLAKU berganti — dan pada klip hasil sutradara itu terjadi di setiap
  // batas potongan. Terlapor: pratinjau "memuat deteksi" terus-menerus, bahkan
  // saat klip yang sama diputar ulang sesudah selesai ditonton.
  const cacheJejakRef = useRef(new Map());
  const jalanJejakRef = useRef(new Map());
  const sceneKey = `${videoId}|${segmentKey}|${aspectRatio}`;
  const sceneKeyRef = useRef(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setSelectedLine(null); }, [segmentKey]);

  /** Mengambil satu jejak (sekali saja per kunci), mengembalikan janji hasilnya. */
  const ambilJejak = useCallback((subjek) => {
    const kunci = kunciJejak(subjek);
    if (cacheJejakRef.current.has(kunci)) return Promise.resolve(cacheJejakRef.current.get(kunci));
    if (jalanJejakRef.current.has(kunci)) return jalanJejakRef.current.get(kunci);
    const janji = apiPost('/clip-reframe', {
      video_id: videoId,
      segments: selected.segments,
      aspect_ratio: aspectRatio,
      frame_motion: frameMotion,
      subjek,
      person_keys: subjek === 'wajah' ? personKeys : [],
      // Label penutur ikut dikirim: dengan itu server bisa mencocokkan wajah
      // dengan suara, dan crop mengikuti orang yang sedang bicara.
      subtitles: (selected.subtitles ?? []).map((l) => ({
        start: l.start, end: l.end, speaker: l.speaker,
      })),
    }).then((res) => {
      cacheJejakRef.current.set(kunci, res);
      // Simpanan dibatasi: tiap jejak berisi posisi per sampel untuk seluruh klip.
      if (cacheJejakRef.current.size > 40) {
        cacheJejakRef.current.delete(cacheJejakRef.current.keys().next().value);
      }
      return res;
    }).finally(() => { jalanJejakRef.current.delete(kunci); });
    jalanJejakRef.current.set(kunci, janji);
    return janji;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId, segmentKey, aspectRatio, frameMotion, personKeys, penuturKlip, selected]);

  useEffect(() => {
    let cancelled = false;
    // Jejak wajah juga dibutuhkan oleh susunan sendiri, begitu ada satu bingkai
    // yang diminta mengikuti orang. Dulu ia hanya diambil di mode ikut-wajah,
    // jadi kotak pengikut di susunan sendiri diam saja di pratinjau meski
    // hasil rendernya bergerak.
    if (!videoId || !selected || !wantsTrack || aspectRatio === '16:9') {
      setReframe(null);
      // Tanda sibuk WAJIB dimatikan di sini juga. Permintaan sebelumnya sudah
      // dibatalkan oleh pembersih efek, jadi `.finally`-nya tidak akan pernah
      // mematikannya — dan berpindah mode di tengah pelacakan membuat tanda
      // "melacak…" menggantung selamanya. Itulah loading yang tidak selesai.
      setReframeLoading(false);
      return undefined;
    }
    // Rencana klip SEBELUMNYA dibuang hanya bila yang berubah adalah KLIPNYA —
    // menahannya berarti menampilkan orang-orang klip yang barusan
    // ditinggalkan, dan lajurnya bisa diklik.
    if (sceneKeyRef.current !== sceneKey) {
      sceneKeyRef.current = sceneKey;
      setReframe(null);
    }
    const kunci = kunciJejak(subjekLacak);
    if (cacheJejakRef.current.has(kunci)) {
      setReframe(cacheJejakRef.current.get(kunci));
      setReframeLoading(false);
    } else {
      setReframeLoading(true);
      ambilJejak(subjekLacak)
        .then((res) => { if (!cancelled) setReframe(res); })
        .catch(() => { if (!cancelled) setReframe(null); })
        .finally(() => { if (!cancelled) setReframeLoading(false); });
    }
    // Jejak lain yang akan dibutuhkan linimasa ini diambil di latar sekarang,
    // supaya pratinjau tidak berhenti memuat saat sampai di potongannya.
    for (const subjek of subjekDibutuhkan.split(',').filter(Boolean)) {
      if (subjek !== subjekLacak) ambilJejak(subjek).catch(() => {});
    }
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId, segmentKey, subjekLacak, wantsTrack, aspectRatio, frameMotion, followKey,
      personKeys, penuturKlip, subjekDibutuhkan]);

  // Timecode dibaca dari elemen video pada ~10 Hz. `timeupdate` hanya menyala
  // sekitar 4 Hz dan angkanya terlihat tersendat; membacanya tiap frame dan
  // menaruhnya di state React akan me-render ulang pohon 60 kali per detik.
  useEffect(() => {
    let raf;
    let last = -1;
    const tick = () => {
      const v = videoRef.current;
      if (v && Math.abs(v.currentTime - last) > 0.09) {
        last = v.currentTime;
        setSourceTime(v.currentTime);
      }
      // Begitu videonya berjalan sendiri, sasaran lompatan tombol panah tidak
      // berlaku lagi — tekanan berikutnya harus menumpuk pada posisi nyata.
      if (v && !v.paused) seekTargetRef.current = null;
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  /**
   * Apakah sebuah detik masih berada DI DALAM klip yang sedang dipilih.
   *
   * Ini yang menentukan pratinjau menampilkan klipnya atau video sumbernya, dan
   * karena itu juga menentukan subtitle dan kotak ikut-wajah muncul atau tidak.
   */
  const insideClip = useCallback((t) => (
    (selected?.segments ?? []).some((sg) => t >= sg.start - 0.05 && t <= sg.end + 0.05)
  ), [selected]);

  // Sasaran lompatan terakhir. Menyetel `currentTime` bersifat asinkron: menekan
  // panah tiga kali cepat membaca `currentTime` yang MASIH LAMA pada tekanan
  // kedua dan ketiga, sehingga tiga tekanan hanya memundurkan satu langkah.
  // Itulah "mundurnya cuma sedikit". Dengan sasaran disimpan, tiap tekanan
  // menumpuk pada tekanan sebelumnya, bukan pada posisi pemutar yang tertinggal.
  const seekTargetRef = useRef(null);

  const seekSource = useCallback((time) => {
    const v = videoRef.current;
    if (!v) return;
    seekTargetRef.current = null;
    // Menjelajah keluar klip melepaskan pratinjau; masih di dalam klip tidak.
    setConstrained(insideClip(time));
    v.currentTime = time;
  }, [insideClip]);

  const selectClip = useCallback((clipId) => {
    editor.setSelectedId(clipId);
    seekTargetRef.current = null;
    setConstrained(true);
    const clip = clips.find((c) => c.clip_id === clipId);
    const v = videoRef.current;
    if (clip && v) v.currentTime = clip.segments[0].start;
  }, [clips, editor]);

  /**
   * Video selalu diparkir DI DALAM klip yang sedang dipilih.
   *
   * `selectClip` sudah melompat ke awal klip, tapi hanya saat klipnya diklik —
   * bukan saat editor pertama terbuka, dan bukan saat `videoRef` belum terisi
   * atau metadatanya belum termuat (menyetel `currentTime` pada elemen yang
   * belum siap tidak melakukan apa-apa, tanpa galat).
   *
   * Akibatnya terlihat sebagai layar hitam dan dilaporkan begitu: pemutar
   * berhenti di detik 0 SUMBER sementara klip yang dipilih mulai di menit 23.
   * Pada video ini detik 0 kebetulan gelap — jadi yang tampil memang hampir
   * hitam, dan tidak ada apa pun di layar yang menjelaskan kenapa.
   */
  useEffect(() => {
    const v = videoRef.current;
    const segs = selected?.segments;
    if (!v || !segs?.length) return undefined;
    const mulai = Number(segs[0].start) || 0;
    const akhir = Number(segs[segs.length - 1].end) || mulai;
    const parkir = () => {
      const t = v.currentTime;
      // Hanya dipindahkan bila memang berada DI LUAR klipnya: kalau tidak,
      // setiap penyuntingan kecil akan menyentak pemutar kembali ke awal.
      if (t < mulai - 0.5 || t > akhir + 0.5) {
        try { v.currentTime = mulai; } catch { /* elemen belum siap */ }
      }
    };
    parkir();
    v.addEventListener('loadedmetadata', parkir);
    v.addEventListener('loadeddata', parkir);
    return () => {
      v.removeEventListener('loadedmetadata', parkir);
      v.removeEventListener('loadeddata', parkir);
    };
    // Cara membingkai DAN jumlah bidangnya ikut jadi pemicu, dan keduanya
    // bukan kelebihan.
    //
    // Setiap kali susunan pratinjau berubah, elemen <video>-nya dibuat ulang
    // dan yang baru lahir di detik 0 — detik 0 SUMBER, bukan awal klipnya.
    // Terlacak langkah demi langkah: memilih klip yang mulai di 1126 detik
    // memang memarkir semuanya di 1127, dan tetap begitu saat tab Bingkai
    // dibuka maupun saat "Main game" ditekan; baru ketika deteksi facecam
    // SELESAI dan bidang keduanya muncul, keempat elemen video serentak
    // kembali ke 0. Pada video gelap itu terbaca sebagai dua kotak kosong.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.clip_id, videoRef, frameModeEfektif,
      susunanTampil?.frames?.length ?? 0]);

  /** Detik keberapa di dalam klip yang sedang dipilih, dari playhead. */
  const clipNow = useCallback(() => (
    selected ? clipTimeFor(selected.segments, videoRef.current?.currentTime ?? 0) : 0
  ), [selected]);

  /** Melompat ke detik tertentu DI DALAM klip. */
  const seekClip = useCallback((t) => {
    const v = videoRef.current;
    if (!v || !selected) return;
    seekTargetRef.current = null;
    // Melompat ke dalam klip, jadi pratinjaunya harus kembali menampilkan klip.
    setConstrained(true);
    v.currentTime = sourceTimeFor(selected.segments, t);
  }, [selected]);

  /**
   * Menunjuk siapa yang harus diikuti bingkai, mulai dari playhead.
   *
   * Inilah jawaban untuk klip yang mengambil orang yang sedang diam: pencocokan
   * otomatis membaca gerak mulut, dan mulut yang tertutup mikrofon hampir tidak
   * bergerak di gambar. Yang dibutuhkan bukan tebakan yang lebih pintar, tapi
   * cara membetulkannya — pada detik yang tepat, bukan untuk seluruh klip.
   */
  /**
   * Nomor di atas video sebagai SAKELAR, bukan sekadar tombol tekan.
   *
   * Menekan nomor 2 di detik ke-3 berarti "mulai dari sini, ambil wajah 2".
   * Menekannya lagi berarti "cukup" — dan yang benar untuk "cukup" bukan
   * menghapus tanda tadi (itu akan mengubah juga detik ke-3 sampai sekarang),
   * melainkan menaruh batas BARU di detik ini yang mengembalikannya ke
   * otomatis. Hasilnya: satu nomor, dua tekan, satu potongan yang punya awal
   * dan akhir — tanpa sekali pun menyentuh linimasa.
   *
   * Sebelum ini nomor yang sudah ditekan tidak bisa dibatalkan dari gambarnya
   * sama sekali; satu-satunya jalan keluar adalah mencari potongannya di lajur
   * Arah bingkai dan menekan A di sana.
   */
  const aimPerson = useCallback((person) => {
    setPersonKeys((keys) => {
      const t = clipNow();
      const sekarang = personKeyAt(keys, t);
      return withPersonKey(keys, t, sekarang === person ? null : person);
    });
  }, [clipNow]);

  // Siapa yang sedang dituju bingkai. Dibaca dari `sourceTime`, yang sudah
  // berdenyut ~10 Hz — cukup untuk menyorot tombolnya tanpa loop sendiri.
  const aimedPerson = useMemo(() => (
    selected ? personKeyAt(personKeys, clipTimeFor(selected.segments, sourceTime)) : null
  ), [personKeys, selected, sourceTime]);

  /**
   * Satu tindakan untuk menandai potongan, yang tahu sedang di langkah mana.
   *
   * Belum ada awal -> pasang awal. Sudah ada awal, belum ada akhir -> pasang
   * akhir, dan kalau playhead-nya justru di SEBELUM awal, keduanya ditukar
   * alih-alih menolak: yang dimaksud pengguna jelas, dan menolaknya hanya
   * memaksanya mengulang dari awal. Sudah lengkap -> mulai menandai lagi dari
   * sini.
   */
  const tandaiPotong = useCallback(() => {
    const t = videoRef.current?.currentTime ?? 0;
    setMark((m) => {
      if (m.in === null) return { in: t, out: null };
      if (m.out === null) {
        return t < m.in ? { in: t, out: m.in } : { in: m.in, out: t };
      }
      return { in: t, out: null };
    });
  }, []);

  /** Menambahkan potongan dari posisi playhead ke klip yang sedang dipilih. */
  const addSegmentAtPlayhead = () => {
    const v = videoRef.current;
    if (!v || !selected) return;
    const start = Math.max(0, v.currentTime);
    editor.addSegment(selected.clip_id, start, Math.min(duration || start + 20, start + 20));
    setConstrained(true);
  };

  /**
   * Melompat relatif terhadap posisi sekarang, dipakai panah kiri/kanan.
   *
   * Dua hal yang dulu salah di sini, dan keduanya terasa setiap kali dipakai.
   *
   * Pertama, ia SELALU melepaskan pratinjau dari klipnya. Maju satu detik di
   * tengah klip lalu kehilangan seluruh subtitle dan kotak ikut-wajahnya —
   * berganti jadi video sumber berbilah kabur — padahal playhead-nya tidak
   * pernah keluar dari klip itu. Sekarang yang menentukan adalah apakah
   * sasarannya benar-benar di luar klip.
   *
   * Kedua, ia menumpuk pada `v.currentTime`, yang belum berubah saat tombol
   * ditekan lagi sebelum pencarian sebelumnya selesai.
   */
  const nudgePlayhead = useCallback((delta) => {
    const v = videoRef.current;
    if (!v) return;
    const dur = duration || v.duration || 0;
    const base = seekTargetRef.current ?? v.currentTime;
    const t = Math.max(0, Math.min(dur, base + delta));
    seekTargetRef.current = t;
    setConstrained(insideClip(t));
    v.currentTime = t;
  }, [duration, insideClip]);

  const saveRef = useRef(null);

  const togglePlay = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) v.play().catch(() => { /* butuh interaksi pengguna */ });
    else v.pause();
  }, []);

  /**
   * Pintasan papan tik ala editor video.
   *
   * Menandai batas klip berarti bolak-balik antara memutar, mundur sedikit, dan
   * menandai — puluhan kali per klip. Dengan tetikus saja setiap putaran itu
   * berarti membidik tombol kecil, dan pekerjaan yang seharusnya mengalir jadi
   * tersendat.
   *
   * Dipasang di window, bukan pada satu elemen: playhead tidak punya fokus, dan
   * memaksa pengguna mengklik dulu sebelum spasi bekerja adalah persis
   * kejanggalan yang ingin dihilangkan. Yang perlu dijaga hanyalah tidak
   * membajak tombol saat pengguna sedang mengetik.
   */
  useEffect(() => {
    const onKey = (e) => {
      const el = e.target;
      const typing = el instanceof HTMLElement
        && (el.isContentEditable
          || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName));
      if (typing) return;

      // Ctrl/Cmd ditangani LEBIH DULU. Penjaga sebelumnya memulangkan setiap
      // kombinasi bertombol pengubah, yang berarti Ctrl+Z tidak pernah sampai
      // ke sini sama sekali — bukan urung yang gagal, melainkan urung yang
      // tidak pernah ada.
      if (e.ctrlKey || e.metaKey) {
        const k = e.key.toLowerCase();
        if (k === 'z' && !e.shiftKey) {
          e.preventDefault();
          editor.undo();
        } else if ((k === 'z' && e.shiftKey) || k === 'y') {
          e.preventDefault();
          editor.redo();
        } else if (k === 's') {
          e.preventDefault();
          // Lewat ref, bukan sebutan langsung: penangannya baru dibuat jauh di
          // bawah efek ini, dan menyebutnya di daftar dependensi akan menabrak
          // TDZ saat render pertama.
          if (editor.dirty) saveRef.current?.();
        }
        return;
      }
      if (e.altKey) return;

      const step = e.shiftKey ? 10 : 1;
      switch (e.key) {
        case ' ':
          e.preventDefault();
          togglePlay();
          break;
        case 'ArrowRight':
          e.preventDefault();
          nudgePlayhead(step);
          break;
        case 'ArrowLeft':
          e.preventDefault();
          nudgePlayhead(-step);
          break;
        case 'j': case 'J':
          e.preventDefault();
          nudgePlayhead(-5);
          break;
        case 'k': case 'K':
          e.preventDefault();
          togglePlay();
          break;
        case 'l': case 'L':
          e.preventDefault();
          nudgePlayhead(5);
          break;
        case 'i': case 'I':
          e.preventDefault();
          setMark((m) => ({ ...m, in: videoRef.current?.currentTime ?? 0 }));
          break;
        case 'o': case 'O':
          e.preventDefault();
          setMark((m) => ({ ...m, out: videoRef.current?.currentTime ?? 0 }));
          break;
        case 'Home':
          e.preventDefault();
          seekSource(selected?.segments[0].start ?? 0);
          break;
        default:
          break;
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [togglePlay, nudgePlayhead, seekSource, selected, editor]);

  /** Membuat klip dari penanda masuk/keluar, atau dari posisi playhead. */
  const createFromMarks = useCallback(async () => {
    const v = videoRef.current;
    const here = v?.currentTime ?? 0;
    const start = mark.in ?? here;
    const end = mark.out ?? Math.min(duration || start + 30, start + 30);
    if (end - start < 1.5) return;
    await editor.createClip(start, end);
    setMark({ in: null, out: null });
    setConstrained(true);
  }, [mark, duration, editor]);

  /** Menandai ulang penutur di seluruh klip, dengan jumlah dari pengguna. */
  const redetectSpeakers = useCallback(async (speakers) => {
    if (!videoId) return;
    setRedetecting(true);
    try {
      const { job_id: jobId } = await apiPost('/clip-speakers', {
        video_id: videoId, speakers,
      });
      setExportLog([{ name: 'Narasumber', status: 'running', progress: 0,
                      message: 'Menunggu giliran…' }]);
      const job = await waitForJob(jobId, {
        interval: 2000,
        onProgress: (j) => setExportLog([{
          name: 'Narasumber', status: 'running', progress: j.progress ?? 0,
          message: j.message || 'Menandai penutur…', eta: j.eta_seconds ?? null,
        }]),
      });
      if (job.status === 'done') {
        const fresh = await apiGet(`/projects/${videoId}`);
        setData(fresh);
        editor.load(videoId, fresh.clips || []);
        setExportLog([{ name: 'Narasumber', status: 'done', progress: 1,
                        message: 'Penutur ditandai ulang.' }]);
      } else {
        setExportLog([{ name: 'Narasumber', status: 'failed',
                        message: job.error || 'Deteksi ulang gagal.' }]);
      }
    } catch (err) {
      setExportLog([{ name: 'Narasumber', status: 'failed', message: err.message }]);
    } finally {
      setRedetecting(false);
    }
  }, [videoId, editor]);

  /** Meminta Gemini menulis ulang judul & tagar klip yang masih heuristik. */
  const handleRetitle = useCallback(async () => {
    if (!videoId) return;
    setRetitling(true);
    try {
      const { job_id: jobId } = await apiPost('/clip-titles', { video_id: videoId });
      setExportLog([{ name: 'Judul', status: 'running', progress: 0,
                      message: 'Menunggu giliran…' }]);
      const job = await waitForJob(jobId, {
        interval: 2000,
        onProgress: (j) => setExportLog([{
          name: 'Judul', status: 'running', progress: j.progress ?? 0,
          message: j.message || 'Menulis ulang judul…', eta: j.eta_seconds ?? null,
        }]),
      });
      if (job.status === 'done') {
        const fresh = await apiGet(`/projects/${videoId}`);
        setData(fresh);
        editor.load(videoId, fresh.clips || []);
        setExportLog([{ name: 'Judul', status: 'done', progress: 1,
                        message: 'Judul dan tagar diperbarui.' }]);
      } else {
        setExportLog([{ name: 'Judul', status: 'failed',
                        message: job.error || 'Gagal menulis ulang judul.' }]);
      }
    } catch (err) {
      setExportLog([{ name: 'Judul', status: 'failed', message: err.message }]);
    } finally {
      setRetitling(false);
    }
  }, [videoId, editor]);

  const handleSaveClips = useCallback(async () => {
    setSaving('running');
    try {
      await editor.saveClips();
      setSaving(null);
    } catch {
      setSaving('failed');
    }
  }, [editor]);
  saveRef.current = handleSaveClips;

  // Cara bingkai milik KLIP ITU: klip yang terbuka memakai yang tampil di
  // layar; klip lain memakai pilihannya sendiri, hasil baca isinya, atau
  // "otomatis" — server membacanya sendiri sebelum merender.
  const modeKlip = (clip) => {
    if (clip.clip_id === selectedRef.current?.clip_id) return frameMode;
    return clip.cara_bingkai || jenisRef.current[kunciJenis(clip)]?.mode || 'otomatis';
  };
  /**
   * Menerjemahkan SEMUA klip yang belum punya terjemahan (atau terjemahannya
   * usang). Untuk proyek yang dianalisis sebelum terjemahan otomatis ada —
   * satu tombol, bukan belasan klip satu per satu.
   */
  const terjemahSemua = useCallback(async (bahasa) => {
    const sasaran = clips.filter((c) => (c.subtitles ?? []).length
      && (!c.subtitle_kedua || (c.subtitle_kedua.sumber_sidik
        && c.subtitle_kedua.sumber_sidik !== sidikUtamaKlip(c.subtitles))));
    for (const c of sasaran) {
      // eslint-disable-next-line no-await-in-loop
      const r = await apiPost('/clip-terjemah', {
        video_id: videoId, bahasa, teks: c.subtitles.map((l) => l.text || ''),
      });
      editor.updateClip(c.clip_id, {
        subtitle_kedua: buatKedua(c, bahasa, r.teks, c.subtitle_kedua?.style),
      });
    }
  }, [clips, videoId, editor]);

  const renderPayload = useCallback((clip) => renderPayloadMode(clip, modeKlip(clip)),   // eslint-disable-line react-hooks/exhaustive-deps
    [videoId, aspectRatio, frameMode, frameMotion, layout, cacheGaming, style, showHook,
     unggahSetelah, googleReady]);
  const renderPayloadMode = (clip, frameMode) => ({
    source_path: videoId,
    clip_index: clip.index,
    segments: clip.segments,
    subtitles: clip.subtitles,
    hook_text: clip.hook_text,
    show_hook: showHook,
    // Judul klip, bukan judul video sumbernya: tanpa ini kelima belas klip
    // dari satu video keluar dengan nama berkas yang sama persis kecuali
    // nomornya.
    title: (clip.title || '').trim(),
    hashtags: clip.hashtags ?? [],
    aspect_ratio: aspectRatio,
    frame_mode: frameMode,
    frame_motion: frameMotion,
    // Dari KLIP yang sedang dirender, bukan dari klip yang kebetulan terbuka:
    // "Render semua" mengirim lima belas klip lewat fungsi ini, dan setelan
    // klip yang terbuka tidak berlaku untuk empat belas sisanya.
    frame_zoom: clip.frame_zoom ?? 1,
    frame_geser_y: clip.frame_geser_y ?? 0,
    frame_layout: frameMode === 'layout' ? serializeLayout(layout)
      // Main game yang sudah disetel dikirim sebagai susunan jadi; tanpanya
      // server mencari facecam sendiri seperti dulu.
      : frameMode === 'gaming'
        ? serializeLayout(clip.susunan_game ?? cacheGaming[clip.clip_id]) : null,
    // Dua kunci atau lebih MENANG atas frame_mode di server. Dikirim apa adanya
    // supaya aturan itu hanya hidup di satu tempat.
    // Susunan tiap potongan ikut dikirim dalam bentuk yang sama dengan
    // `frame_layout`, supaya server tidak perlu tahu dua bentuk yang berbeda.
    frame_keys: (clip.frame_keys ?? []).map((k) => (
      (k.mode === 'layout' || k.mode === 'gaming') && k.layout?.frames?.length
        ? { ...k, layout: serializeLayout(k.layout) }
        : k.mode === 'gaming' && !k.layout
            && (clip.susunan_game ?? cacheGaming[clip.clip_id])?.frames?.length
          ? { ...k, layout: serializeLayout(clip.susunan_game ?? cacheGaming[clip.clip_id]) }
          : k
    )),
    // Tanda milik KLIP INI, bukan klip yang sedang dibuka: ekspor berjalan
    // atas semua huruf yang dicentang, dan memakai tanda klip terpilih untuk
    // semuanya akan mengarahkan bingkai empat belas klip lain ke orang yang
    // tidak pernah ditunjuk untuk mereka.
    person_keys: ['smart', 'otomatis'].includes(frameMode) ? (clip.person_keys ?? []) : [],
    // Sisipan milik klip INI. `id` hanya pengenal di editor; server tidak perlu.
    media_layers: (clip.media_layers ?? []).map(({ id, ...l }) => l),
    // Subtitle kedua milik klip ini. `sumber_sidik` hanya penanda usang di editor.
    subtitle_kedua: clip.subtitle_kedua
      ? (({ sumber_sidik, ...k }) => k)(clip.subtitle_kedua) : null,
    // Kartu judul dikirim hanya bila pengguna menyalakannya untuk klip INI.
    // Teks kosong berarti memakai judul klipnya sendiri — dua judul yang sama
    // adalah kasus paling sering, dan mengetiknya dua kali tidak masuk akal.
    watermark: (style.watermark || '').trim(),
    title_card: clip.title_card?.enabled
      ? {
        ...clip.title_card,
        text: (clip.title_card.text || '').trim() || (clip.title || '').trim(),
      }
      : null,
    caption_style: style,
    unggah: googleReady ? unggahSetelah : { youtube: false, drive: false },
  });

  // Baris render yang sedang berjalan, untuk label tombol.
  const kerjaRender = exportLog.find((e) => e.status === 'running');

  const handleExportSelected = async () => {
    const targets = clips.filter((c) => checked.has(c.clip_id));
    if (!targets.length) return;
    setExporting(true);
    setExportLog([]);
    for (const [nomor, clip] of targets.entries()) {
      const name = `Klip #${clip.index}`;
      const urut = targets.length > 1 ? `${nomor + 1}/${targets.length} · ` : '';
      setExportLog((l) => [...l, {
        name, status: 'running', urut, progress: 0, message: 'Menunggu giliran…',
      }]);
      const kabar = (patch) => setExportLog((l) => l.map((e) => {
        if (e.name !== name) return e;
        // Kapan tahap ini dimulai: tahap tanpa angka kemajuan sendiri (melacak
        // wajah, belasan detik) ditampilkan dengan lama berjalannya.
        const pesanBaru = patch.message && bersihkanPesan(patch.message) !== bersihkanPesan(e.message);
        return { ...e, ...patch, sejak: pesanBaru || !e.sejak ? Date.now() : e.sejak };
      }));
      try {
        // eslint-disable-next-line no-await-in-loop
        const { job_id: jobId } = await apiPost('/render-clip', renderPayload(clip));
        // eslint-disable-next-line no-await-in-loop
        const job = await waitForJob(jobId, {
          // Render melaporkan kemajuannya per bingkai yang di-encode; tanpa
          // ditampilkan, satu-satunya tanda hidup adalah lingkaran berputar —
          // dan pada klip satu menit itu berputar berpuluh detik tanpa
          // mengatakan apa pun.
          onProgress: (j) => kabar({
            progress: j.progress ?? 0,
            message: j.message || 'Merender…',
            eta: j.eta_seconds ?? null,
          }),
        });
        if (job.status === 'done') {
          // Diunduh lewat peramban HANYA kalau OmniClip dibuka dari komputer
          // lain. Di komputer yang menjalankannya sendiri, berkasnya sudah ada
          // di folder klip yang dipilih pengguna, dan mengunduhnya lagi cuma
          // menaruh salinan kedua di folder Unduhan peramban.
          if (!dijalankanDiKomputerIni()) {
            // eslint-disable-next-line no-await-in-loop
            await downloadToDisk(kategoriKlip(), job.result.clip_name);
          }
          const mode = job.result.frame_mode === 'smart' ? 'ikut wajah' : job.result.frame_mode;
          kabar({ status: 'done', progress: 1, eta: null,
                  message: `Tersimpan di folder klip · bingkai ${mode}` });

          // Unggahan diantrekan SERVER sesudah render (services/unggah.py);
          // di sini hanya diberitakan.
          const antre = (job.result.unggahan ?? []).filter((u) => u.job_id)
            .map((u) => (u.target === 'youtube' ? 'YouTube' : 'Drive'));
          const galatUnggah = (job.result.unggahan ?? []).find((u) => u.galat);
          if (antre.length || galatUnggah) {
            setExportLog((l) => l.map((e) => (e.name === name
              ? { ...e, message: `${e.message} · ${antre.length ? `antre ke ${antre.join(' & ')}` : galatUnggah.galat}` }
              : e)));
          }
        } else {
          kabar({ status: 'failed', eta: null, message: job.error || 'Gagal' });
        }
      } catch (err) {
        kabar({ status: 'failed', eta: null, message: err.message });
      }
    }
    setExporting(false);
  };
  if (error) {
    return (
      <Centered>
        <AlertTriangle size={30} style={{ color: 'var(--danger)', marginBottom: '10px' }} />
        <h3 className="work-title" style={{ fontSize: '1.1rem', marginBottom: '7px' }}>
          Partitur ini tidak bisa dibuka
        </h3>
        <p style={{ fontSize: '.85rem', color: 'var(--ink-2)' }}>{error.message}</p>
        <button className="btn-secondary" onClick={onBack} style={{ marginTop: '16px' }}>
          <ArrowLeft size={14} /> Kembali
        </button>
      </Centered>
    );
  }

  if (!data) {
    return (
      <Centered>
        <Loader2 size={24} className="animate-spin" style={{ color: 'var(--reh)' }} />
        <p style={{ marginTop: '10px', fontSize: '.85rem', color: 'var(--ink-2)' }}>
          Membuka partitur…
        </p>
      </Centered>
    );
  }

  const letter = selected ? rehearsalLetter(clips.indexOf(selected)) : '·';

  return (
    /* ── Studio sebagai RUANG, bukan halaman ────────────────────────────────
       Sebelumnya seluruh studio adalah satu halaman yang digulir: panggung di
       atas, linimasa di tengah, panel di bawah. Akibatnya pekerjaan yang paling
       sering dilakukan, melihat gambarnya lalu menggeser sesuatu di linimasa,
       menuntut menggulir bolak-balik, dan keduanya tidak pernah terlihat
       bersamaan.

       Sekarang tingginya dikunci ke tinggi layar dan dibagi tiga: bilah di
       atas, panggung di tengah, linimasa berlabuh di bawah. Tidak ada yang
       menggulir kecuali isi kotaknya sendiri. Panel alat tidak lagi berdiri
       permanen memakan tempat, ia muncul dari rel ikon di kanan hanya ketika
       dipanggil, dan menutup lagi dengan menekan ikon yang sama. */
    <div className="studio" style={{ '--dock-h': `${dockH}px` }}>
      <header className="studio-bar">
        <button className="btn-secondary studio-icon" onClick={onBack} aria-label="Kembali">
          <ArrowLeft size={15} />
        </button>
        <button className={`btn-secondary studio-icon${railOpen ? ' is-on' : ''}`}
                onClick={() => setRailOpen((v) => !v)}
                title={railOpen ? 'Sembunyikan daftar klip' : 'Tampilkan daftar klip'}
                aria-label="Daftar klip">
          <Menu size={15} />
        </button>

        <div className="studio-title">
          <h1>{data.title}</h1>
          <div className="sub">
            {clips.length} klip · {formatTime(duration)} ·{' '}
            {data.speaker_count > 1
              ? `${data.speaker_confident ? '' : '± '}${data.speaker_count} narasumber`
              : 'satu narasumber'}
          </div>
        </div>

        <div className="studio-actions">
          <label className="studio-check" title="Pilih semua klip untuk dirender">
            <input type="checkbox"
                   checked={checked.size === clips.length && clips.length > 0}
                   onChange={(e) => editor.setAllChecked(e.target.checked)} />
            {checked.size}/{clips.length}
          </label>
          {googleReady && (
            <>
              <label className="studio-check"
                     title="Klip yang selesai dirender langsung diantrekan ke kanal YouTube akun profil ini">
                <input type="checkbox" checked={unggahSetelah.youtube}
                       onChange={(e) => setUnggahSetelah((u) => ({ ...u, youtube: e.target.checked }))} />
                YouTube
              </label>
              <label className="studio-check"
                     title="Klip yang selesai dirender langsung diantrekan ke Google Drive akun profil ini">
                <input type="checkbox" checked={unggahSetelah.drive}
                       onChange={(e) => setUnggahSetelah((u) => ({ ...u, drive: e.target.checked }))} />
                Drive
              </label>
            </>
          )}
          {/* Tombol simpan yang menyebut KEADAAN, bukan sekadar kejadian.
              
              Sebelumnya ia berkata "Tersimpan" selama 2,5 detik lalu kembali
              jadi "Simpan" dengan sendirinya, dan dibaca begitu, ia terlihat
              seperti sakelar yang membatalkan simpanannya sendiri. Padahal
              editor sudah tahu jawabannya sepanjang waktu lewat `dirty`; yang
              kurang cuma menampilkannya. Sekarang: ada yang belum tersimpan ->
              "Simpan" dan bisa ditekan; tidak ada -> "Tersimpan" dan mati,
              karena memang tidak ada yang perlu dikerjakan. */}
          {/* Urung dan ulang, terlihat sebagai tombol.
              
              Pintasannya sendiri sudah cukup bagi yang tahu pintasannya ada;
              tombolnya di sini untuk yang tidak. Judulnya menyebutkan
              pintasannya, jadi keduanya saling mengajarkan. */}
          <button className="btn-secondary" onClick={() => setCariUlang(true)}
                  title="Cari ulang rekomendasi klip, hook, dan judul dengan Gemini atau mesin lokal, tanpa mengunduh ulang">
            <RefreshCw size={14} />
            Cari ulang
          </button>
          {cariUlang && (
            <CariUlangDialog videoId={videoId} data={data} dirty={editor.dirty}
                             onSimpanDulu={() => editor.saveClips()}
                             onSelesai={(segar) => {
                               setData(segar);
                               editor.load(videoId, segar.clips || []);
                             }}
                             onTutup={() => setCariUlang(false)} />
          )}
          <button className="btn-secondary" onClick={editor.undo}
                  disabled={!editor.canUndo}
                  title="Urungkan suntingan terakhir (Ctrl+Z)">
            <Undo2 size={14} />
          </button>
          <button className="btn-secondary" onClick={editor.redo}
                  disabled={!editor.canRedo}
                  title="Ulangi yang diurungkan (Ctrl+Shift+Z)">
            <Redo2 size={14} />
          </button>
          <button className="btn-secondary" onClick={handleSaveClips}
                  disabled={saving === 'running' || (!editor.dirty && saving !== 'failed')}
                  title={editor.dirty
                    ? 'Menyimpan susunan klip, batas, subtitle, judul, dan tanda bingkai ke penyimpanan lokal'
                    : 'Semua perubahan sudah tersimpan'}>
            {saving === 'running' ? <Loader2 size={14} className="animate-spin" />
              : saving === 'failed' ? <AlertTriangle size={14} style={{ color: 'var(--danger)' }} />
                : editor.dirty ? <Save size={14} />
                  : <CheckCircle2 size={14} style={{ color: 'var(--entry)' }} />}
            {saving === 'failed' ? 'Gagal simpan' : editor.dirty ? 'Simpan' : 'Tersimpan'}
          </button>
          <button className="btn-primary" disabled={exporting || checked.size === 0}
                  onClick={handleExportSelected}>
            {exporting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            {/* Tombolnya sendiri menyebut sampai mana: saat panel catatan
                tergulir keluar layar, tombol inilah yang tetap terlihat. */}
            {exporting ? (kerjaRender
              ? `${kerjaRender.urut || ''}${Math.round((kerjaRender.progress ?? 0) * 100)}%`
              : 'Merender…') : 'Render'}
          </button>
        </div>
      </header>

      <div className="studio-body">
        {/* Daftar klip. Bisa ditutup, karena pada pekerjaan menyunting satu klip
            ia hanya perlu dilihat sesekali. */}
        {railOpen && (
          <aside className="studio-rail">
            <div className="plate-head">
              <span className="mark" style={{ color: 'var(--ink)' }}>Klip</span>
              <span className="tc" style={{ marginLeft: 'auto', fontSize: '.72rem', color: 'var(--ink-3)' }}>
                {clips.length}
              </span>
            </div>
            <div className="reh-index">
              {clips.map((clip, i) => {
                const on = clip.clip_id === editor.selectedId;
                return (
                  <div key={clip.clip_id} onClick={() => selectClip(clip.clip_id)}
                       className={`reh-row${on ? ' is-on' : ''}`}>
                    <input type="checkbox" checked={checked.has(clip.clip_id)}
                           onClick={(e) => e.stopPropagation()}
                           onChange={() => editor.toggleChecked(clip.clip_id)}
                           style={{ width: '14px', height: '14px', marginTop: '3px' }} />
                    <span className={`reh${clip.source === 'manual' ? ' reh--manual' : ''}`}>
                      {rehearsalLetter(i)}
                    </span>
                    <div style={{ minWidth: 0 }}>
                      <div className="tc" style={{ fontSize: '.7rem', color: 'var(--ink-3)' }}>
                        {formatTime(clip.segments[0].start)} · {Math.round(clip.duration || 0)}s
                        {clip.score != null && ` · ${Math.round(clip.score)}`}
                        {clip.source === 'manual' && ' · tangan'}
                      </div>
                      <div style={{
                        fontSize: '.76rem', color: 'var(--ink-2)', lineHeight: 1.35,
                        display: '-webkit-box', WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical', overflow: 'hidden',
                      }}>{clip.hook_text}</div>
                    </div>
                  </div>
                );
              })}
            </div>
            {/* Mesin pemilih pasti melewatkan momen: ia menilai dari pola bicara
                dan kosakata, bukan dari apa yang lucu. Pintu untuk menambah
                sendiri harus ada DI SINI, di daftar klip, karena di sinilah
                orang melihat bahwa yang dicarinya tidak ada. */}
            <button className="btn-secondary studio-rail-add" onClick={createFromMarks}
                    disabled={editor.busy}>
              {editor.busy ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
              {mark.in !== null || mark.out !== null
                ? 'Jadikan klip dari rentang bertanda'
                : 'Klip baru dari playhead'}
            </button>
          </aside>
        )}

        {/* Panggung. Satu-satunya bagian yang boleh melar. */}
        <main className="studio-stage">
          {data.model_requested && data.model && data.model_requested !== data.model && (
            <div className="plate studio-note" style={{ borderLeftColor: 'var(--warn)' }}>
              Model <b>{data.model_requested}</b> tidak bisa dipakai saat analisis ini
              berjalan, biasanya karena kuota hariannya habis. Sistem memakai{' '}
              <b>{data.model}</b> sebagai cadangan.
            </div>
          )}
          {data.pratinjau_disiapkan && (
            <div className="plate studio-note" style={{ fontSize: '.8rem', display: 'flex',
                                                         gap: '8px', alignItems: 'center' }}>
              <Loader2 size={14} className="animate-spin" style={{ flexShrink: 0 }} />
              <span>
                Video ini beresolusi besar dan bisa tersendat saat diputar di browser.
                Salinan pratinjau yang ringan sedang disiapkan
                {Number.isFinite(data.pratinjau_kemajuan)
                  ? ` (${Math.round(data.pratinjau_kemajuan * 100)}%)` : ''}.
                Studio akan berpindah sendiri begitu siap. Hasil render tetap memakai
                video asli, jadi menunggunya tidak wajib: batas klip, subtitle, dan
                bingkai semuanya sudah bisa disetel sekarang.
              </span>
            </div>
          )}
          {data.downloaded === false && (
            <VideoHilang videoId={videoId} onPulih={async () => {
              const fresh = await apiGet(`/projects/${videoId}`);
              setData(fresh);
            }} />
          )}
          {exportLog.length > 0 && (
            <div className="plate studio-note" style={{
              display: 'flex', flexDirection: 'column', gap: '6px',
            }}>
              {/* Jalan ke berkasnya. Sejak klip tidak lagi diunduh ulang lewat
                  peramban, satu-satunya tempatnya adalah folder klip, dan
                  tombol ini yang membukanya. */}
              {exportLog.some((e) => e.status === 'done') && dijalankanDiKomputerIni() && (
                <button className="btn-secondary"
                        style={{ alignSelf: 'flex-start', fontSize: '0.74rem',
                                 padding: '4px 9px', display: 'inline-flex',
                                 alignItems: 'center', gap: '6px' }}
                        onClick={() => apiPost('/settings/penyimpanan/folder/buka',
                                               { jenis: 'klip' }).catch(() => {})}>
                  <FolderOpen size={13} /> Buka folder klip
                </button>
              )}
              {exportLog.map((e) => (
                <div key={e.name} style={{ fontSize: '.8rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '9px' }}>
                    {e.status === 'running' && <Loader2 size={13} className="animate-spin" style={{ color: 'var(--reh)' }} />}
                    {e.status === 'done' && <CheckCircle2 size={13} style={{ color: 'var(--entry)' }} />}
                    {e.status === 'failed' && <AlertTriangle size={13} style={{ color: 'var(--danger)' }} />}
                    <b style={{ minWidth: '64px' }}>{e.urut}{e.name}</b>
                    <span style={{ color: 'var(--ink-2)' }}>
                      {e.status === 'running' ? bersihkanPesan(e.message) : e.message}
                    </span>
                    {e.status === 'running' && (
                      <span style={{ marginLeft: 'auto', color: 'var(--ink-2)',
                                     fontVariantNumeric: 'tabular-nums' }}>
                        {Math.round((e.progress ?? 0) * 100)}%
                        {e.eta > 1 && e.progress > 0.05
                          ? ` · sisa ${sisaWaktu(e.eta)}`
                          : e.sejak && Date.now() - e.sejak > 3000
                            ? ` · berjalan ${sisaWaktu((Date.now() - e.sejak) / 1000)}` : ''}
                      </span>
                    )}
                  </div>
                  {/* Bilah kemajuan, bukan cuma lingkaran berputar: render satu
                      klip memakan puluhan detik sampai beberapa menit, dan yang
                      berputar tanpa angka tidak bisa dibedakan dari macet. */}
                  {e.status === 'running' && (
                    <div style={{ height: '5px', marginTop: '5px', borderRadius: '99px',
                                  background: 'var(--bg-glass)', overflow: 'hidden',
                                  border: '1px solid var(--border-color)' }}>
                      <div style={{ width: `${Math.max(2, Math.round((e.progress ?? 0) * 100))}%`,
                                    height: '100%', background: 'var(--reh)',
                                    transition: 'width .5s' }} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="stage-row">
            <FrameStage src={srcPutar} videoRef={videoRef}
                        segments={selected?.segments ?? null}
                        frameMode={frameModeEfektif} reframe={reframe} aspectRatio={aspectRatio}
                        boxRect={kunciBingkaiAktif?.rect ?? null}
                        onBoxRectChange={setKotakBingkai}
                        layout={susunanTampil} onLayoutChange={setSusunanEfektif}
                        selectedFrameId={selectedFrameId} onSelectFrame={setSelectedFrameId}
                        personKeys={personKeys} onLockPerson={aimPerson} />

            <div className="pit editor-pit">
              <ClipPreview src={srcPutar} clip={selected} aspectRatio={aspectRatio}
                           cerminSiap={cerminSiap}
                           onKeduaStyleChange={selected?.subtitle_kedua ? (patch) => editor.updateClip(
                             selected.clip_id, { subtitle_kedua: { ...selected.subtitle_kedua,
                               style: { ...(selected.subtitle_kedua.style ?? {}), ...patch } } }) : null}
                           style={{ ...style, showHook }} videoRef={videoRef}
                           constrained={constrained} frameMode={frameModeEfektif}
                           boxRect={kunciBingkaiAktif?.rect ?? null}
                           reframe={reframe} reframeLoading={reframeLoading}
                           onStyleChange={patchStyle} onCardChange={patchCard}
                           layout={susunanTampil} onLayoutChange={setSusunanEfektif}
                           frameEditing={tab === 'frame'}
                           selectedFrameId={selectedFrameId}
                           onSelectFrame={setSelectedFrameId}
                           /* Pegangan sisipan hanya di tab Sisipan. Kotak
                              putus-putus di atas gambar akan mengganggu saat
                              orang sedang menyetel subtitle atau bingkai. */
                           frameZoom={selected?.frame_zoom ?? 1}
                           frameGeserY={selected?.frame_geser_y ?? 0}
                           sisipanTerpilih={tab === 'media' ? sisipanTerpilih : null}
                           onPilihSisipan={tab === 'media' ? setSisipanTerpilih : null}
                           onSisipanRect={tab === 'media' && selected ? (id, rect) => {
                             const kini = selected.media_layers ?? [];
                             editor.updateClip(selected.clip_id, {
                               media_layers: kini.map((l) => (l.id === id ? {
                                 ...l,
                                 rect: {
                                   x: Number(rect.x.toFixed(2)), y: Number(rect.y.toFixed(2)),
                                   w: Number(rect.w.toFixed(2)), h: Number(rect.h.toFixed(2)),
                                 },
                               } : l)),
                             });
                           } : null} />
            </div>
          </div>
        </main>

        {/* Panel alat. Hanya ada saat dipanggil. */}
        {tab && (
          <aside className="studio-panel">
            <div className="plate-head">
              <span className={`reh${selected?.source === 'manual' ? ' reh--manual' : ''}`}>{letter}</span>
              <span className="mark" style={{ color: 'var(--ink)' }}>
                {TABS.find((t) => t.id === tab)?.label}
              </span>
              <button className="btn-secondary studio-icon" style={{ marginLeft: 'auto' }}
                      onClick={() => setTab(null)} title="Tutup panel" aria-label="Tutup panel">
                <X size={14} />
              </button>
            </div>
            <div className="studio-panel-body">
              {tab === 'trim' && (
                <>
                  <TrimPanel clip={selected} videoDuration={duration} busy={editor.busy}
                             onNudge={editor.nudgeSegment} onSetBounds={editor.setSegmentBounds}
                             onAddSegment={editor.addSegment} onRemoveSegment={editor.removeSegment} />
                  {selected && selected.segments.length > 1 && (
                    <div style={{
                      marginTop: '12px', paddingTop: '12px',
                      borderTop: '1px solid var(--rule-2)', fontSize: '.78rem',
                      display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center',
                    }}>
                      <b style={{ width: '100%' }}>
                        Klip {letter} menyambung {selected.segments.length} potongan:
                      </b>
                      {selected.segments.map((s, i) => (
                        <span key={i} className="tc" style={{
                          display: 'inline-flex', alignItems: 'center', gap: '6px',
                          padding: '3px 8px', background: 'var(--plate-2)',
                          border: '1px solid var(--rule-2)', borderRadius: 'var(--r-sm)',
                        }}>
                          {formatTime(s.start)}-{formatTime(s.end)}
                          <Trash2 size={11} style={{ cursor: 'pointer', color: 'var(--danger)' }}
                                  onClick={() => editor.removeSegment(selected.clip_id, i)} />
                        </span>
                      ))}
                    </div>
                  )}
                </>
              )}
              {tab === 'subtitle' && (
                <TerjemahPanel clip={selected} videoId={videoId}
                               styleUtama={style} onStyleUtama={setStyle}
                               onSemua={terjemahSemua}
                               onChange={(next) => selected
                                 && editor.updateClip(selected.clip_id, { subtitle_kedua: next })} />
              )}
              {tab === 'subtitle' && (
                <SubtitlePanel clip={selected} onUpdate={editor.updateSubtitle}
                               onRemove={editor.removeSubtitle} style={style} onStyle={setStyle}
                               selectedLine={selectedLine} onSelectLine={setSelectedLine}
                               onSeekLine={seekClip}
                               onAutoSpeakers={editor.autoSpeakers}
                               speakerCount={data.speaker_count || 2}
                               speakerConfident={data.speaker_confident ?? null}
                               onRedetect={redetectSpeakers} redetecting={redetecting} />
              )}
              {tab === 'style' && (
                <StylePanel style={style} onChange={setStyle}
                            speakerCount={Math.max(data.speaker_count || 1, 2)}
                            aspectRatio={aspectRatio} onAspectChange={setAspectRatio}
                            showHook={showHook} onShowHookChange={setShowHook}
                            hookText={selected?.hook_text ?? ''}
                            onHookTextChange={(t) => selected
                              && editor.updateClip(selected.clip_id, { hook_text: t })}
                            klipUntukTema={selected ? {
                              video_id: videoId,
                              title: selected.title || selected.hook_text || '',
                              duration: (selected.segments || []).reduce(
                                (n, sg) => n + Math.max(0, sg.end - sg.start), 0),
                              jenis: selected.jenis || '',
                              subtitles: (selected.subtitles || []).slice(0, 80).map((l) => ({
                                start: l.start, end: l.end, text: l.text, speaker: l.speaker,
                              })),
                            } : null} />
              )}
              {tab === 'title' && (
                <TitlePanel clip={selected}
                            onRetitle={handleRetitle} retitling={retitling}
                            onChange={(patch) => selected
                              && editor.updateClip(selected.clip_id, patch)} />
              )}
              {tab === 'media' && (
                <MediaPanel clip={selected} videoId={videoId} aspectRatio={aspectRatio}
                            waktuSekarang={clipNow()}
                            durasiKlip={(selected?.segments ?? []).reduce(
                              (n, sg) => n + (sg.end - sg.start), 0)}
                            onLayers={(next) => selected
                              && editor.updateClip(selected.clip_id, { media_layers: next })}
                            frameKeys={frameKeys} onFrameKeys={setFrameKeys}
                            sorot={sisipanTerpilih} onSorot={setSisipanTerpilih} />
              )}
              {tab === 'sutradara' && (
                <SutradaraPanel clip={selected} videoId={videoId} aspectRatio={aspectRatio}
                                lapisan={selected?.media_layers ?? []}
                                onLayers={(next) => selected
                                  && editor.updateClip(selected.clip_id, { media_layers: next })}
                                frameKeys={frameKeys} onFrameKeys={setFrameKeys}
                                onSegments={(segs) => selected
                                  && editor.recomputeSubtitles(selected.clip_id, segs)} />
              )}
              {tab === 'frame' && (
                <FramePanel frameMode={frameModeEfektif} onFrameModeChange={pilihCaraBingkai}
                            jenisKlip={jenisSekarang}
                            pilihanSendiri={!!selected?.cara_bingkai && !(selected?.frame_keys?.length >= 2)}
                            onOtomatis={() => editor.updateClip(selected.clip_id, { cara_bingkai: null })}
                            frameMotion={frameMotion}
                            onFrameMotionChange={setFrameMotion}
                            frameZoom={selected?.frame_zoom ?? 1}
                            frameGeserY={selected?.frame_geser_y ?? 0}
                            onFrameZoom={(v) => selected
                              && editor.updateClip(selected.clip_id, { frame_zoom: v })}
                            onFrameGeserY={(v) => selected
                              && editor.updateClip(selected.clip_id, { frame_geser_y: v })}
                            layout={susunanTampil} onLayoutChange={setSusunanEfektif}
                            gamingSibuk={gamingSibuk}
                            onGaming={setelGaming} onGamingUlang={ulangiGaming}
                            selectedFrameId={selectedFrameId}
                            onSelectFrame={setSelectedFrameId}
                            faceTrackAvailable={!!reframe?.people?.length}
                            peopleCount={orangHadir.length}
                            aimedPerson={aimedPerson} onAimPerson={aimPerson}
                            keyCount={personKeys.length}
                            onClearKeys={() => setPersonKeys([])}
                            frameKeys={frameKeys} onFrameKeys={setFrameKeys}
                            waktuSekarang={clipNow()}
                            durasiKlip={(selected?.segments ?? []).reduce(
                              (n, sg) => n + (sg.end - sg.start), 0)} />
              )}
            </div>
          </aside>
        )}

        {/* Rel alat: ikon saja, selalu di tempat yang sama.
            Menekan ikon yang sedang menyala menutup panelnya, jadi panggung
            bisa dikembalikan ke lebar penuh tanpa mencari tombol lain. */}
        <nav className="studio-tools">
          {TABS.map(({ id, label, Icon }) => (
            <button key={id} title={label} aria-label={label}
                    className={`studio-tool${tab === id ? ' is-on' : ''}`}
                    onClick={() => setTab((cur) => (cur === id ? null : id))}>
              <Icon size={17} strokeWidth={1.8} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* ── Dok: transport dan linimasa, selalu terlihat ──────────────────── */}
      <div className="studio-dock" style={{ height: `${dockH}px` }}>
        {/* Tepi yang bisa ditarik. Diberi peran pemisah supaya pembaca layar
            dan papan ketik juga bisa memakainya, bukan hanya tetikus. */}
        <div className="dock-grip" onPointerDown={dragDock}
             role="separator" aria-orientation="horizontal"
             aria-label="Seret untuk mengubah tinggi linimasa"
             tabIndex={0}
             onKeyDown={(e) => {
               const d = e.key === 'ArrowUp' ? 24 : e.key === 'ArrowDown' ? -24 : 0;
               if (!d) return;
               e.preventDefault();
               setDockH((h) => {
                 const max = Math.max(DOCK_MIN, window.innerHeight * 0.72);
                 const n = Math.round(Math.min(max, Math.max(DOCK_MIN, h + d)));
                 localStorage.setItem('omniclip.dockH', String(n));
                 return n;
               });
             }} />
        <div className="dock-bar">
          <button className="btn-secondary" onClick={togglePlay} style={{ minWidth: '78px' }}>
            <Play size={13} /> Spasi
          </button>
          <div className="tc dock-clock">
            <span className="mark" style={{ color: 'var(--ink-3)' }}>Video</span>
            {formatTimecode(sourceTime)}
            <span style={{ color: 'var(--ink-3)', fontWeight: 500, fontSize: '.82rem' }}>
              {' / '}{formatTimecode(duration)}
            </span>
          </div>

          {/* SATU tombol untuk memotong, bukan dua.
              Mulanya dua tombol bernama "Tandai I" dan "Tandai O", nama yang
              hanya masuk akal bagi yang sudah tahu istilah in-point dan
              out-point. Diberi nama yang jelas, keduanya jadi panjang dan
              memakan separuh bilah untuk pekerjaan yang urutannya sudah pasti:
              awal selalu didahulukan, akhir selalu menyusul. Sesuatu yang
              urutannya pasti tidak butuh dua tombol, ia butuh satu tombol yang
              tahu sedang di langkah mana. */}
          <div className="cutter">
            <button className="btn-secondary cutter-btn" onClick={tandaiPotong}
                    title={mark.in === null
                      ? 'Menandai awal klip baru di posisi playhead'
                      : mark.out === null
                        ? 'Menandai akhir klip baru di posisi playhead'
                        : 'Mulai menandai ulang dari posisi playhead'}>
              <Scissors size={13} />
              {mark.in === null ? 'Mulai potong'
                : mark.out === null ? 'Akhiri potong' : 'Tandai ulang'}
              <kbd style={kbd}>{mark.in === null || mark.out !== null ? 'I' : 'O'}</kbd>
            </button>
            <span className="tc cutter-range">
              {mark.in === null && mark.out === null
                ? 'tandai awal & akhirnya'
                : `${mark.in === null ? '…' : formatTime(mark.in)}-${mark.out === null ? '…' : formatTime(mark.out)}`
                  + (mark.in !== null && mark.out !== null
                    ? ` · ${Math.max(0, mark.out - mark.in).toFixed(1)} dtk` : '')}
            </span>
            {mark.in !== null && mark.out !== null && (
              <button className="btn-primary cutter-btn" onClick={createFromMarks}
                      title="Membuat klip baru dari rentang yang ditandai"
                      disabled={editor.busy || mark.out - mark.in < 1.5}>
                {editor.busy ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
                Jadikan klip
              </button>
            )}
          </div>

          {/* Dua linimasa berbagi satu tempat, bukan bertumpuk.
              Keduanya menjawab pertanyaan yang berbeda dan jarang ditanyakan
              bersamaan: "di mana klip ini jatuh dalam satu jam rekaman" dan "di
              detik ke berapa baris ini muncul". Menaruh keduanya sekaligus di
              dok berarti tidak ada yang cukup tinggi untuk dipegang. */}
          <button className="btn-secondary cutter-btn"
                  onClick={addSegmentAtPlayhead} disabled={!selected || editor.busy}
                  title="Menyambungkan potongan baru dari posisi playhead ke klip ini">
            <Plus size={12} /> Sambung dari sini
          </button>
          {!constrained && (
            <button className="btn-secondary cutter-btn"
                    onClick={() => selected && selectClip(selected.clip_id)}>
              Kembali ke klip
            </button>
          )}

          <div className="dock-switch">
            <button className={dockView === 'clip' ? 'is-on' : ''}
                    onClick={() => setDockView('clip')}>Klip ini</button>
            <button className={dockView === 'all' ? 'is-on' : ''}
                    onClick={() => setDockView('all')}>Seluruh rekaman</button>
          </div>

          <span className="mark dock-keys">
            ← → 1 dtk · Shift 10 dtk · J K L 5 dtk
          </span>
        </div>

        <div className="dock-body">
          {dockView === 'clip' ? (
            <ClipTimeline clip={selected} reframe={reframe}
                          personKeys={personKeys} onPersonKeys={setPersonKeys}
                          frameKeys={frameKeys} onFrameKeys={setFrameKeys}
                          mediaLayers={selected?.media_layers ?? []}
                          onMediaLayers={(next) => selected
                            && editor.updateClip(selected.clip_id, { media_layers: next })}
                          sisipanTerpilih={sisipanTerpilih}
                          onPilihSisipan={(id) => { setSisipanTerpilih(id); setTab('media'); }}
                          modeDasar={frameMode}
                          videoRef={videoRef} onSeekClip={seekClip}
                          onMoveSubtitle={(i, a, b) => selected
                            && editor.moveSubtitle(selected.clip_id, i, a, b)}
                          onSetSegmentBounds={(i, a, b) => selected
                            && editor.setSegmentBounds(selected.clip_id, i, a, b)}
                          onSelectSubtitle={setSelectedLine}
                          onUpdateSubtitle={(i, patch) => selected
                            && editor.updateSubtitle(selected.clip_id, i, patch)}
                          selectedLine={selectedLine}
                          speakerColors={style.speaker_colors ?? []}
                          reframeLoading={reframeLoading}
                          frameAiming={frameMode === 'smart'}
                          busy={editor.busy} />
          ) : (
            <StaveSystem
              duration={duration} peaks={peaks} clips={clips}
              selectedId={editor.selectedId}
              speakerCount={data.speaker_count || 1}
              speakerColors={style.speaker_colors ?? []}
              videoRef={videoRef}
              onSeek={seekSource} onSelectClip={selectClip}
              onTrimClip={editor.setSegmentBounds} busy={editor.busy}
              onRemoveClip={hapusKlip}
              mark={mark}
            />
          )}
        </div>
      </div>
    </div>
  );
}

async function waitForJob(jobId, { interval = 1200, limit = 2400000, onProgress } = {}) {
  const started = Date.now();
  for (;;) {
    // eslint-disable-next-line no-await-in-loop
    const job = await apiGet(`/jobs/${jobId}`);
    onProgress?.(job);
    if (['done', 'failed', 'cancelled'].includes(job.status)) return job;
    if (Date.now() - started > limit) return { status: 'failed', error: 'Waktu render habis.' };
    // eslint-disable-next-line no-await-in-loop
    await new Promise((r) => setTimeout(r, interval));
  }
}

/**
 * Pesan tahap tanpa angka persennya sendiri. Server menulis "Merender klip…
 * 5%" — persen tahap encode — sementara bilahnya menunjukkan persen seluruh
 * pekerjaan (13%). Dua angka berbeda di satu baris hanya membingungkan.
 */
function bersihkanPesan(pesan) {
  return String(pesan || '').replace(/\s*\d+(?:[.,]\d+)?\s*%\s*$/, '').trim();
}

/** "sisa 1 mnt 20 dtk" — perkiraan dari job, dibulatkan supaya tidak gelisah. */
function sisaWaktu(detik) {
  const d = Math.max(0, Math.round(detik));
  if (d < 60) return `${d} dtk`;
  const m = Math.floor(d / 60);
  return m < 60 ? `${m} mnt ${d % 60} dtk` : `${Math.floor(m / 60)} jam ${m % 60} mnt`;
}

const kbd = {
  display: 'inline-block', padding: '1px 5px', margin: '0 1px',
  borderRadius: '4px', background: 'var(--bg-glass)',
  border: '1px solid var(--border-color)', fontSize: '0.66rem',
  fontFamily: 'inherit', fontWeight: 700, color: 'var(--text-secondary)',
};

/**
 * Timecode gaya editor: HH:MM:SS.d
 *
 * Sepersepuluh detik ikut ditampilkan karena batas klip disetel pada ketelitian
 * itu; MM:SS saja membuat dua posisi yang berbeda terlihat identik persis saat
 * pengguna sedang mencoba membedakannya.
 */
function formatTimecode(seconds) {
  const t = Math.max(0, Number(seconds) || 0);
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = Math.floor(t % 60);
  const d = Math.floor((t % 1) * 10);
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(h)}:${pad(m)}:${pad(s)}.${d}`;
}

function Centered({ children }) {
  return (
    <div style={{ padding: '70px 20px', textAlign: 'center' }}>{children}</div>
  );
}
