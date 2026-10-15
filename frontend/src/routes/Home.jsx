import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Loader2, Video, RefreshCw, X, Scissors, CheckCircle2, Flame, Mic, MessagesSquare, GraduationCap,
  Gamepad2, Music2, Cpu, TrendingUp, Laugh, UtensilsCrossed, Plane, ChevronLeft, ChevronRight, SlidersHorizontal,
} from 'lucide-react';
import { bahasa, useT } from '../lib/i18n';
import { apiGet, apiPost } from '../lib/api';
import { VideoCard } from '../components/VideoCards';
import CookiesAwal from '../components/CookiesAwal';

// Tahun sengaja tidak dicantumkan: menempelkan "2024" ke setiap kueri menyaring
// hasil ke tahun yang sudah lewat.
// Emoji dibuang: ia bukan sistem ikon, dan sebelas emoji dari sebelas keluarga
// gambar yang berbeda membuat baris ini terbaca sebagai tempelan, bukan kendali.
// Topik beranda (JOB-3): pil gaya YouTube dengan ikon dan warna khas.
// Kata kuncinya mengikuti bahasa pilihan: mode Inggris mencari video
// berbahasa Inggris. Untuk Gaming, BUKAN "gaming highlights": di YouTube
// Indonesia kata "highlights" dikuasai sorotan olahraga (5 dari 6 hasil).
const CATEGORIES = [
  { kunci: 'trending', Icon: Flame, warna: '#FF4D4D', q: { id: 'trending viral indonesia', en: 'trending viral today' } },
  { kunci: 'podcast', Icon: Mic, warna: '#A78BFA', q: { id: 'podcast indonesia terbaru', en: 'podcast full episode' } },
  { kunci: 'wawancara', Icon: MessagesSquare, warna: '#60A5FA', q: { id: 'wawancara eksklusif indonesia', en: 'exclusive interview' } },
  { kunci: 'edukasi', Icon: GraduationCap, warna: '#34D399', q: { id: 'edukasi menarik indonesia', en: 'educational explained' } },
  { kunci: 'gaming', Icon: Gamepad2, warna: '#F472B6', q: { id: 'gameplay game indonesia', en: 'gameplay walkthrough funny' } },
  { kunci: 'musik', Icon: Music2, warna: '#FBBF24', q: { id: 'musik viral indonesia', en: 'music video viral' } },
  { kunci: 'tech', Icon: Cpu, warna: '#22D3EE', q: { id: 'teknologi AI indonesia', en: 'tech AI news' } },
  { kunci: 'finance', Icon: TrendingUp, warna: '#4ADE80', q: { id: 'investasi tips keuangan indonesia', en: 'investing personal finance' } },
  { kunci: 'komedi', Icon: Laugh, warna: '#FB923C', q: { id: 'komedi lucu indonesia', en: 'stand up comedy' } },
  { kunci: 'kuliner', Icon: UtensilsCrossed, warna: '#F87171', q: { id: 'kuliner makanan enak indonesia', en: 'street food tour' } },
  { kunci: 'travel', Icon: Plane, warna: '#38BDF8', q: { id: 'travel wisata indonesia', en: 'travel vlog' } },
];

/**
 * Baris topik yang bisa digeser, seperti baris chip YouTube.
 *
 * Dilaporkan pemiliknya 15 Oktober 2026: topik di ujung kanan tidak bisa
 * dicapai (bilah gulirnya disembunyikan dan roda tetikus menggulir halaman),
 * dan pil yang disorot terpotong di atas karena wadah gulir memotong pil yang
 * terangkat. Sekarang: panah kiri/kanan muncul hanya bila ada yang tersembunyi
 * di sisi itu, roda tetikus menggeser baris, dan wadahnya punya ruang napas.
 */
function BarisTopik({ children }) {
  const t = useT();
  const ref = useRef(null);
  const [sisi, setSisi] = useState({ kiri: false, kanan: false });

  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const ukur = () => setSisi({
      kiri: el.scrollLeft > 2,
      kanan: el.scrollLeft + el.clientWidth < el.scrollWidth - 2,
    });
    // Roda tetikus vertikal menggeser baris ke samping, hanya bila memang ada
    // yang bisa digeser; selebihnya halaman tetap menggulir seperti biasa.
    const roda = (e) => {
      if (Math.abs(e.deltaY) <= Math.abs(e.deltaX) || el.scrollWidth <= el.clientWidth) return;
      const ujung = e.deltaY > 0
        ? el.scrollLeft + el.clientWidth >= el.scrollWidth - 1
        : el.scrollLeft <= 0;
      if (ujung) return;
      e.preventDefault();
      el.scrollLeft += e.deltaY;
    };
    ukur();
    el.addEventListener('scroll', ukur, { passive: true });
    el.addEventListener('wheel', roda, { passive: false });
    const ro = new ResizeObserver(ukur);
    ro.observe(el);
    return () => {
      el.removeEventListener('scroll', ukur);
      el.removeEventListener('wheel', roda);
      ro.disconnect();
    };
  }, []);

  const geser = (arah) => ref.current?.scrollBy({ left: arah * ref.current.clientWidth * 0.7, behavior: 'smooth' });
  return (
    <div className="baris-topik">
      {sisi.kiri && (
        <button type="button" className="baris-topik-panah kiri" aria-label={t('beranda.geser_kiri')} onClick={() => geser(-1)}>
          <ChevronLeft size={18} />
        </button>
      )}
      <div ref={ref} className="baris-topik-isi">{children}</div>
      {sisi.kanan && (
        <button type="button" className="baris-topik-panah kanan" aria-label={t('beranda.geser_kanan')} onClick={() => geser(1)}>
          <ChevronRight size={18} />
        </button>
      )}
    </div>
  );
}

/**
 * Feed pencarian.
 *
 * Kata kunci disimpan di URL (`/?q=...`), bukan hanya di state komponen.
 * Dengan begitu tombol back browser mengembalikan pencarian sebelumnya, dan
 * sebuah hasil pencarian bisa dibagikan atau di-bookmark.
 */
const LANGKAH = 20;   // kartu per langkah gulir
const PLAFON = 100;   // batas atas ytsearchN yang masih murah

export default function Home() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();

  // Klip banyak video sekaligus. Kosong = mode pilih mati, jadi satu klik pada
  // kartu tetap berarti "tonton video ini" seperti sebelumnya.
  const [pilih, setPilih] = useState(new Set());
  const [mengantre, setMengantre] = useState(false);
  const [hasilAntre, setHasilAntre] = useState(null);

  const togglePilih = (id) => setPilih((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });

  /**
   * Mengantrekan auto-klip untuk semua yang dicentang.
   *
   * Satu per satu, berurutan, bukan Promise.all: sepuluh permintaan
   * bersamaan hanya membuat server mengunduh metadata sepuluh video
   * sekaligus, dan yang paling mungkin gagal justru yang terakhir.
   * Antreannya sendiri di server yang mengatur giliran pengerjaannya.
   */
  const klipSemua = async () => {
    const daftar = [...pilih];
    if (!daftar.length) return;
    setMengantre(true);
    let masuk = 0; let sudah = 0; let gagal = 0;
    for (const id of daftar) {
      try {
        // eslint-disable-next-line no-await-in-loop
        const res = await apiPost('/auto-clip', {
          video_id: id,
          max_clips: Number(localStorage.getItem('omniclip_max_clips') || 0),
          whisper_model: localStorage.getItem('omniclip_whisper_model') || 'base',
          gemini_model: localStorage.getItem('omniclip_gemini_model') || null,
        });
        if (res.cached) sudah += 1; else masuk += 1;
      } catch {
        gagal += 1;
      }
    }
    setPilih(new Set());
    setMengantre(false);
    setHasilAntre({ masuk, sudah, gagal });
  };
  const q = params.get('q') ?? '';
  const [feed, setFeed] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // BENIH beranda: server memakainya supaya beranda tetap berbeda tiap kali
  // dibuka tapi tidak berubah di tengah gulir. Diminta dari server (bukan
  // diacak di sini) supaya yang dipakai adalah beranda yang sudah disiapkan
  // di latar: halaman langsung terisi tanpa menunggu pencarian YouTube.
  // `null` = belum ada benih, beranda belum dimuat.
  const [nonce, setNonce] = useState(null);
  const ambilBenih = () => apiGet('/trending/benih', { timeout: 8000 })
    .then((r) => setNonce(r.benih))
    .catch(() => setNonce(Math.floor(Math.random() * 1e6)));
  useEffect(() => {
    if (!q && nonce === null) ambilBenih();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, nonce]);
  const [sort, setSort] = useState('relevan');
  // Penyaring milik YouTube sendiri (parameter sp), bukan saringan di sini atas
  // data yang tidak lengkap. Kosong = semua.
  const [durasi, setDurasi] = useState('');
  const [tanggal, setTanggal] = useState('');
  const [jenis, setJenis] = useState('');
  // Panel penyaring tertutup sampai tombol Filter ditekan, seperti YouTube
  // (diminta pemilik 15 Oktober 2026). Jumlah penyaring yang aktif tetap
  // terlihat di tombolnya, jadi hasil yang tersaring tidak terbaca sebagai
  // hasil lengkap.
  const [bukaSaring, setBukaSaring] = useState(false);
  const jumlahSaring = [jenis, durasi, tanggal].filter(Boolean).length + (sort !== 'relevan' ? 1 : 0);
  // Tanggal unggah datang MENYUSUL, dari panggilan terpisah: hasil pencarian
  // YouTube tidak membawanya sama sekali, dan mengambilnya berarti membuka tiap
  // videonya. Kartunya tampil dulu, tanggalnya mengisi belakangan.
  const [dates, setDates] = useState({});
  // Infinite scroll dengan menaikkan BATAS, bukan offset.
  //
  // `ytsearchN:` milik yt-dlp tidak punya offset sama sekali — tidak ada cara
  // meminta "hasil ke-21 sampai ke-40". Yang bisa dilakukan hanya meminta N
  // yang lebih besar lalu memakai ekornya. Itu akan berarti mengulang seluruh
  // pencarian setiap kali, kalau saja hasilnya tidak di-cache di server; dengan
  // cache, langkah berikutnya menembak YouTube sekali lalu instan selamanya.
  //
  // Plafonnya 100 dan bukan 50: ytsearch50 terukur 4,2 detik, ytsearch100 4,8
  // detik. Ongkosnya ada pada permintaannya, bukan pada jumlah hasilnya.
  const [batas, setBatas] = useState(LANGKAH);
  const [habis, setHabis] = useState(false);
  const [menambah, setMenambah] = useState(false);
  const sentinelRef = useRef(null);
  // Cermin `feed` yang bisa dibaca saat tanggapan datang, tanpa menjadikan
  // `feed` kebergantungan efek pemuatan — yang akan membuat setiap penambahan
  // memicu pemuatan berikutnya.
  const feedRef = useRef([]);


  // Identitas daftar yang sedang ditampilkan. Kueri, urutan, atau tombol
  // Segarkan yang berubah berarti daftar yang lain sama sekali.
  const kunci = `${q}|${sort}|${durasi}|${tanggal}|${jenis}|${nonce}`;
  const kunciRef = useRef(kunci);
  if (kunciRef.current !== kunci) {
    // Disetel saat render, bukan di dalam useEffect. Lewat efek, satu putaran
    // render sempat terjadi dengan kunci BARU tapi batas LAMA — dan putaran itu
    // menembakkan permintaan untuk daftar yang salah, yang hasilnya lalu
    // ditambahkan ke daftar yang sudah bukan miliknya.
    kunciRef.current = kunci;
    feedRef.current = [];
    setFeed([]);
    setBatas(LANGKAH);
    setHabis(false);
  }

  useEffect(() => {
    if (!q && nonce === null) return undefined;     // menunggu benih beranda
    let batal = false;
    // Muatan pertama sebuah daftar mengganti isinya; sisanya MENAMBAH.
    //
    // Sebelumnya semua muatan mengganti, termasuk langkah gulir. Kalau urutan
    // dari server bergeser sedikit saja, seluruh kartu ter-render ulang sebagai
    // elemen baru, tinggi halaman berubah, dan peramban melempar pembaca
    // kembali ke atas — persis di saat ia sedang membaca kartu di dasar.
    const tumbuh = batas > LANGKAH;
    setLoading(true);
    setError(null);
    const path = q
      ? `/search?q=${encodeURIComponent(q)}&limit=${batas}&sort=${sort}`
        + (durasi ? `&durasi=${durasi}` : '') + (tanggal ? `&tanggal=${tanggal}` : '')
        + (jenis ? `&jenis=${jenis}` : '')
      : `/trending?limit=${batas}&refresh=${nonce}`;
    // 75 detik, bukan 30: beranda menunggu beberapa pencarian YouTube, dan
    // saat sambungan ke youtube.com tersendat server tetap selesai menyusun
    // tapi lewat 30 detik (15 Oktober 2026).
    apiGet(path, { timeout: 75000 })
      .then((data) => {
        if (batal) return;
        const datang = Array.isArray(data) ? data : [];
        const sebelum = tumbuh ? feedRef.current : [];
        const sudahAda = new Set(sebelum.map((v) => v.id));
        const tambahan = datang.filter((v) => v.id && !sudahAda.has(v.id));
        // Tidak ada satu pun yang baru meski batasnya dinaikkan = memang habis.
        if (tumbuh && !tambahan.length) setHabis(true);
        const gabungan = tumbuh ? sebelum.concat(tambahan) : datang;
        feedRef.current = gabungan;
        setFeed(gabungan);
      })
      .catch((err) => {
        if (batal) return;
        // Kegagalan harus terlihat: `catch { setFeed([]) }` membuat rate limit
        // YouTube tampak persis seperti "tidak ada hasil". Tapi kegagalan saat
        // MENAMBAH tidak boleh menghapus yang sudah terbaca — itu menghukum
        // pembaca atas satu langkah gulir yang gagal.
        setError(err);
        if (!tumbuh) {
          feedRef.current = [];
          setFeed([]);
        }
      })
      .finally(() => {
        if (batal) return;
        setLoading(false);
        setMenambah(false);
      });
    return () => { batal = true; };
    // `q`, `sort`, dan `nonce` semuanya sudah terkandung di dalam `kunci`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kunci, batas]);

  // Hanya video yang tanggalnya BELUM diketahui yang ditanyakan.
  //
  // Sebelumnya seluruh daftar dikirim setiap kali, termasuk video yang
  // tanggalnya sudah ikut bersama hasil pencarian dari basis data. Tiap id di
  // daftar itu berarti satu permintaan penuh ke YouTube — dua puluh kartu,
  // dua puluh permintaan, dan menggulir ke bawah menambah dua puluh lagi
  // untuk video yang sama. Ledakan itulah yang memicu verifikasi bot.
  useEffect(() => {
    const ids = feed
      .filter((v) => v.id && !v.upload_date && !dates[v.id])
      .map((v) => v.id);
    if (!ids.length) return undefined;
    let cancelled = false;
    apiGet(`/upload-dates?ids=${ids.join(',')}`)
      .then((res) => { if (!cancelled) setDates((prev) => ({ ...prev, ...res })); })
      // Tanggal yang tidak datang bukan kegagalan halaman: kartunya cukup
      // tidak menuliskan tanggal apa pun.
      .catch(() => {});
    return () => { cancelled = true; };
    // `dates` sengaja tidak masuk daftar kebergantungan: ia ditulis oleh efek
    // ini sendiri, jadi menyertakannya berarti efeknya memanggil dirinya lagi.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [feed]);

  // Sentinel di dasar daftar: begitu ia terlihat, batasnya dinaikkan.
  useEffect(() => {
    const el = sentinelRef.current;
    // `batas >= PLAFON` ikut di sini, bukan hanya di teks sentinelnya.
    // Tanpa itu pengamat tetap menyala di dasar daftar, menyetel `menambah`
    // menjadi true, lalu menaikkan batas ke angka yang sudah dipakai — tidak
    // ada muatan baru, jadi `loading` tidak pernah berubah dan yang mereset
    // `menambah` tidak pernah jalan. Hasilnya tulisan "Memuat lagi…" yang
    // menyala selamanya di dasar halaman: persis seperti gulir tak hingga
    // yang macet, padahal daftarnya memang sudah habis.
    if (!el || habis || loading || !feed.length || batas >= PLAFON) return undefined;
    const obs = new IntersectionObserver((entries) => {
      if (entries[0]?.isIntersecting) {
        setMenambah(true);
        setBatas((b) => Math.min(PLAFON, b + LANGKAH));
      }
    }, { rootMargin: '400px' });
    obs.observe(el);
    return () => obs.disconnect();
  }, [habis, loading, feed.length, batas]);


  const t = useT();
  const kueriTopik = (c) => c.q[bahasa()] ?? c.q.id;
  const activeCategory = CATEGORIES.findIndex((c) => Object.values(c.q).includes(q));

  // Urutan dikerjakan YouTube, bukan diurutkan ulang di sini: tanpa tanggal
  // unggah di hasil pencarian, "terbaru" mustahil dijawab dari data yang ada.
  const SORTS = [
    ['relevan', t('saring.relevan')],
    ['terbaru', t('saring.terbaru')],
    ['terpopuler', t('saring.terpopuler')],
    ['rating', t('saring.rating')],
  ];

  return (
    <div className="page">
      {/* Pertanyaan cookies, sekali saja, sebelum apa pun yang lain.

          Ditaruh di Beranda dan bukan di Pengaturan karena di sinilah orangnya
          berada saat pertama kali membuka OmniClip. Kartunya menyembunyikan
          dirinya sendiri begitu pertanyaannya terjawab atau sistem sudah
          memilih sendiri; lihat components/CookiesAwal.jsx. */}
      <CookiesAwal />

      {/* Judul dan kolom cari pindah ke header, seperti YouTube (JOB-3 J3-2).
          Kata kunci tetap dibaca dari URL (`/?q=`), jadi tidak ada yang
          berubah pada cara pencarian bekerja. */}
      <BarisTopik>
        {!q && (
          <button className="chip" disabled={loading} onClick={ambilBenih}
                  title={t('umum.segarkan')} style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
            <RefreshCw size={13} className={loading ? 'animate-spin' : undefined} />
          </button>
        )}
        {CATEGORIES.map((cat, i) => {
          const aktif = activeCategory === i;
          return (
            <button key={cat.kunci} onClick={() => setParams({ q: kueriTopik(cat) })}
                    className={`topik${aktif ? ' is-on' : ''}`} style={{ '--warna-topik': cat.warna }}>
              <cat.Icon size={15} strokeWidth={2.2} className="topik-ikon" />
              {t(`topik.${cat.kunci}`)}
            </button>
          );
        })}
      </BarisTopik>

      {/* Penyaring hanya untuk pencarian: beranda tanpa kata kunci sudah
          mengambil kueri acak tiap muat. Pil gaya YouTube, dua bahasa. */}
      {q && (
        <div className="tombol-saring-baris">
          <button type="button" className={`tombol-saring${bukaSaring ? ' is-on' : ''}`}
                  aria-expanded={bukaSaring} onClick={() => setBukaSaring((v) => !v)}>
            <SlidersHorizontal size={15} />
            {t('saring.tombol')}
            {jumlahSaring > 0 && <span className="tombol-saring-jumlah">{jumlahSaring}</span>}
          </button>
          {jumlahSaring > 0 && (
            <button type="button" className="saring"
                    onClick={() => { setJenis(''); setSort('relevan'); setDurasi(''); setTanggal(''); }}>
              {t('saring.reset')}
            </button>
          )}
        </div>
      )}
      {q && bukaSaring && (
        <div className="baris-saring">
          {[
            [t('saring.jenis'), jenis, setJenis, [['', t('saring.semua')], ['video', t('saring.video')],
              ['shorts', t('channel.tab_shorts')], ['live', t('channel.tab_live')]]],
            [t('saring.urutkan'), sort, setSort, SORTS],
            [t('saring.durasi'), durasi, setDurasi, [['', t('saring.semua')], ['pendek', t('saring.pendek')],
              ['sedang', t('saring.sedang')], ['panjang', t('saring.panjang')]]],
            [t('saring.diunggah'), tanggal, setTanggal, [['', t('saring.kapan_saja')], ['hari', t('saring.hari')],
              ['minggu', t('saring.minggu')], ['bulan', t('saring.bulan')], ['tahun', t('saring.tahun')]]],
          ].map(([judul, nilai, ubah, pilihan]) => (
            <div key={judul} className="kelompok-saring">
              <span className="judul-saring">{judul}</span>
              {pilihan.map(([id, label]) => (
                <button key={id || 'semua'} onClick={() => ubah(id)}
                        className={`saring${nilai === id ? ' is-on' : ''}`}>{label}</button>
              ))}
            </div>
          ))}
        </div>
      )}

      {/* Kerangka pemuatan HANYA saat belum ada apa-apa di layar.
          Sebelumnya syaratnya cuma `loading`, jadi tiap langkah gulir
          mengganti seluruh daftar dengan dua belas kotak kerangka: tinggi
          halaman runtuh dari 2608 piksel jadi 1453, peramban memaksa posisi
          gulir turun dari 1100 ke 685, lalu data datang dan seluruh kartu
          ter-render ulang. Di layar itu terbaca persis seperti "dilempar ke
          atas dan videonya diganti", dan memang itu yang terjadi. */}
      {loading && !feed.length ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '20px' }}>
          {[...Array(12)].map((_, i) => (
            <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ width: '100%', paddingTop: '56.25%', background: 'var(--plate-2)', borderRadius: 'var(--r-sm)', animation: 'pulse 1.5s ease-in-out infinite' }} />
              <div style={{ height: '14px', background: 'var(--plate-2)', borderRadius: 'var(--r-sm)', width: '90%', animation: 'pulse 1.5s ease-in-out infinite' }} />
              <div style={{ height: '12px', background: 'var(--plate-2)', borderRadius: 'var(--r-sm)', width: '60%', animation: 'pulse 1.5s ease-in-out infinite' }} />
            </div>
          ))}
        </div>
      ) : error && !feed.length ? (
        <div style={{
          padding: '46px 24px', textAlign: 'center', background: 'var(--bg-card)',
          borderRadius: 'var(--r-md)', border: '1px solid color-mix(in srgb, var(--danger) 40%, transparent)',
        }}>
          <Video size={38} style={{ color: 'var(--danger)', marginBottom: '12px' }} />
          <h3 style={{ fontWeight: 700, marginBottom: '6px' }}>{t('beranda.cari_gagal')}</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6, maxWidth: '440px', margin: '0 auto' }}>
            {error.message}
          </p>
          {error.code === 'YTDLP_RATE_LIMIT' && (
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '10px', lineHeight: 1.6 }}>
              {t('beranda.dibatasi')}
            </p>
          )}
          <button className="btn-secondary" style={{ marginTop: '16px', fontSize: '0.83rem' }}
                  onClick={() => setNonce((n) => n + 1)}>
            {t('umum.coba_lagi')}
          </button>
        </div>
      ) : feed.length === 0 ? (
        <div style={{ padding: '60px 20px', textAlign: 'center', background: 'var(--bg-card)', borderRadius: 'var(--r-md)', border: '1px dashed var(--border-color)' }}>
          <Video size={40} style={{ color: 'var(--text-muted)', marginBottom: '12px' }} />
          <h3 style={{ fontWeight: 700 }}>{t('beranda.kosong')}</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            {t('beranda.kosong_saran')}
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '20px 16px' }}>
          {feed.map((video) => (
            <div key={video.id} style={{ position: 'relative' }}>
              <VideoCard
                video={{ ...video, ...(dates[video.id] ?? {}) }}
                isSelected={pilih.has(video.id)}
                onClick={() => (pilih.size
                  ? togglePilih(video.id)
                  : navigate(`/watch/${video.id}`, { state: { video } }))}
              />
              {/* Kotak centang selalu ada, supaya memilih yang PERTAMA tidak
                  perlu mencari mode tersembunyi lebih dulu. */}
              <label onClick={(e) => e.stopPropagation()}
                     title={t('kisi.pilih')}
                     style={{
                       position: 'absolute', top: '8px', left: '8px', zIndex: 2,
                       display: 'flex', alignItems: 'center', justifyContent: 'center',
                       width: '26px', height: '26px', borderRadius: '7px', cursor: 'pointer',
                       background: pilih.has(video.id) ? 'var(--accent-cyan)' : 'rgba(0,0,0,0.55)',
                       border: '1px solid rgba(255,255,255,0.35)',
                     }}>
                <input type="checkbox" checked={pilih.has(video.id)}
                       onChange={() => togglePilih(video.id)}
                       style={{ margin: 0, accentColor: 'var(--accent-cyan)', cursor: 'pointer' }} />
              </label>
            </div>
          ))}
        </div>
      )}

      {feed.length > 0 && (
        <div ref={sentinelRef} style={{
          padding: '26px 12px', textAlign: 'center',
          fontSize: '0.8rem', color: 'var(--text-muted)',
        }}>
          {/* Kegagalan saat MENAMBAH muncul di sini, bukan menggantikan
              daftarnya: satu langkah gulir yang gagal tidak boleh menghapus
              apa yang sudah dibaca orang. */}
          {error && feed.length
            ? <span style={{ color: 'var(--danger)' }}>
                {t('beranda.gagal_tambah', { pesan: error.message })}
              </span>
            : menambah || (loading && feed.length)
              ? <><RefreshCw size={14} className="animate-spin" style={{ verticalAlign: '-2px' }} /> {t('umum.memuat_lagi')}</>
              : habis || batas >= PLAFON
                ? t('beranda.ujung')
                : ''}
        </div>
      )}

      {/* Bilah aksi: hanya muncul saat ada yang dipilih, menempel di bawah
          layar supaya tetap terjangkau setelah menggulir jauh. */}
      {pilih.size > 0 && (
        <div style={{
          position: 'fixed', left: '50%', bottom: '22px', transform: 'translateX(-50%)',
          zIndex: 40, display: 'flex', alignItems: 'center', gap: '12px',
          padding: '10px 14px', borderRadius: '999px',
          background: 'var(--bg-card)', border: '1px solid var(--border-color)',
          boxShadow: '0 6px 24px rgba(0,0,0,0.35)',
        }}>
          <span style={{ fontSize: '0.8rem', fontWeight: 700 }}>
            {t('kisi.dipilih', { n: pilih.size })}
          </span>
          <button className="btn-primary" onClick={klipSemua} disabled={mengantre}
                  style={{ fontSize: '0.8rem', display: 'inline-flex', gap: '6px',
                           alignItems: 'center' }}>
            {mengantre ? <Loader2 size={14} className="animate-spin" /> : <Scissors size={14} />}
            {mengantre ? t('kisi.mengantre') : t('kisi.klip_semua')}
          </button>
          <button onClick={() => setPilih(new Set())}
                  style={{ background: 'none', border: 'none', cursor: 'pointer',
                           color: 'var(--text-muted)', display: 'flex' }}
                  aria-label={t('kisi.batal')}>
            <X size={16} />
          </button>
        </div>
      )}

      {hasilAntre && (
        <div onClick={() => setHasilAntre(null)} style={{
          position: 'fixed', left: '50%', bottom: '22px', transform: 'translateX(-50%)',
          zIndex: 40, display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer',
          padding: '10px 16px', borderRadius: '999px', fontSize: '0.8rem',
          background: 'var(--bg-card)', border: '1px solid var(--border-color)',
          boxShadow: '0 6px 24px rgba(0,0,0,0.35)',
        }}>
          <CheckCircle2 size={15} style={{ color: 'var(--entry)' }} />
          {t('kisi.hasil', hasilAntre)}
        </div>
      )}
    </div>
  );
}
