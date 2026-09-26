import React, { useMemo, useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Search, Loader2, Video, RefreshCw, History, X, Scissors, CheckCircle2 } from 'lucide-react';
import { apiDelete, apiGet, apiPost } from '../lib/api';
import { VideoCard } from '../components/VideoCards';

// Tahun sengaja tidak dicantumkan: menempelkan "2024" ke setiap kueri menyaring
// hasil ke tahun yang sudah lewat.
// Emoji dibuang: ia bukan sistem ikon, dan sebelas emoji dari sebelas keluarga
// gambar yang berbeda membuat baris ini terbaca sebagai tempelan, bukan kendali.
const CATEGORIES = [
  { label: 'Trending', query: 'trending viral indonesia' },
  { label: 'Podcast', query: 'podcast indonesia terbaru' },
  { label: 'Wawancara', query: 'wawancara eksklusif indonesia' },
  { label: 'Edukasi', query: 'edukasi menarik indonesia' },
  // BUKAN "gaming highlights": di YouTube Indonesia kata "highlights"
  // dikuasai sorotan sepak bola dan basket, dan kuerinya mengembalikan
  // Asian Games, bukan permainan. Diuji langsung: 5 dari 6 hasil teratas
  // adalah olahraga.
  { label: 'Gaming', query: 'gameplay game indonesia' },
  { label: 'Musik', query: 'musik viral indonesia' },
  { label: 'Tech', query: 'teknologi AI indonesia' },
  { label: 'Finance', query: 'investasi tips keuangan indonesia' },
  { label: 'Komedi', query: 'komedi lucu indonesia' },
  { label: 'Kuliner', query: 'kuliner makanan enak indonesia' },
  { label: 'Travel', query: 'travel wisata indonesia' },
];

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
  const [draft, setDraft] = useState(q);
  const [feed, setFeed] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // Dinaikkan oleh tombol Segarkan, dan dimulai dari angka acak sekali per
  // kunjungan. Server memakainya sebagai BENIH, jadi beranda tetap berbeda
  // tiap kali dibuka tapi tidak lagi berubah di tengah gulir.
  const [nonce, setNonce] = useState(() => Math.floor(Math.random() * 1e6));
  const [sort, setSort] = useState('relevan');
  // Penyaring milik YouTube sendiri (parameter sp), bukan saringan di sini atas
  // data yang tidak lengkap. Kosong = semua.
  const [durasi, setDurasi] = useState('');
  const [tanggal, setTanggal] = useState('');
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

  useEffect(() => { setDraft(q); }, [q]);

  // Riwayat pencarian PROFIL AKTIF — tiap profil punya minatnya sendiri, dan
  // pencarian satu profil tidak ikut muncul di profil lain.
  const [riwayat, setRiwayat] = useState([]);
  const [cariAktif, setCariAktif] = useState(false);
  useEffect(() => {
    apiGet('/riwayat-cari').then((r) => setRiwayat(r.riwayat ?? [])).catch(() => {});
  }, [q]);
  const buangRiwayat = (kueri) => {
    setRiwayat((r) => r.filter((x) => x.query !== kueri));
    apiDelete(`/riwayat-cari?q=${encodeURIComponent(kueri)}`).catch(() => {});
  };

  // Saran di bawah kotak cari, seperti YouTube dan Google: riwayat yang
  // cocok dengan yang sedang diketik, bukan seluruh riwayat apa adanya.
  // Kosong berarti yang terbaru lebih dulu.
  const [sorot, setSorot] = useState(-1);
  const saran = useMemo(() => {
    const k = draft.trim().toLowerCase();
    const cocok = k ? riwayat.filter((r) => r.query.toLowerCase().includes(k)
                                         && r.query.toLowerCase() !== k)
                    : riwayat;
    return cocok.slice(0, 8);
  }, [riwayat, draft]);
  useEffect(() => { setSorot(-1); }, [draft, cariAktif]);

  const pilihSaran = (kueri) => {
    setDraft(kueri);
    setCariAktif(false);
    setParams({ q: kueri }, { replace: false });
  };

  const tombolCari = (e) => {
    if (!cariAktif || !saran.length) {
      if (e.key === 'ArrowDown' && saran.length) { setCariAktif(true); e.preventDefault(); }
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSorot((i) => (i + 1) % saran.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSorot((i) => (i <= 0 ? saran.length - 1 : i - 1));
    } else if (e.key === 'Enter' && sorot >= 0) {
      e.preventDefault();
      pilihSaran(saran[sorot].query);
    } else if (e.key === 'Escape') {
      setCariAktif(false);
    }
  };

  // Identitas daftar yang sedang ditampilkan. Kueri, urutan, atau tombol
  // Segarkan yang berubah berarti daftar yang lain sama sekali.
  const kunci = `${q}|${sort}|${durasi}|${tanggal}|${nonce}`;
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
      : `/trending?limit=${batas}&refresh=${nonce}`;
    apiGet(path)
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

  const submit = (e) => {
    e.preventDefault();
    const value = draft.trim();
    setParams(value ? { q: value } : {}, { replace: false });
  };

  const activeCategory = CATEGORIES.findIndex((c) => c.query === q);

  // Urutan dikerjakan YouTube, bukan diurutkan ulang di sini: tanpa tanggal
  // unggah di hasil pencarian, "terbaru" mustahil dijawab dari data yang ada.
  const SORTS = [
    ['relevan', 'Paling relevan'],
    ['terbaru', 'Terbaru'],
    ['terpopuler', 'Tayangan terbanyak'],
    ['rating', 'Paling disukai'],
  ];

  return (
    <div className="page">
      <div className="work-block">
        <div style={{ minWidth: 0, flex: '1 1 260px' }}>
          <h1 className="work-title">Cari video</h1>
          <div className="sub">
            Tempel tautan YouTube, atau telusuri untuk mencari bahan.
          </div>
        </div>
        {!q && (
          <div className="actions">
            <button className="btn-secondary" disabled={loading}
                    onClick={() => setNonce((n) => n + 1)}>
              <RefreshCw size={14} className={loading ? 'animate-spin' : undefined} />
              Segarkan
            </button>
          </div>
        )}
      </div>

      <form onSubmit={(e) => { setCariAktif(false); submit(e); }}
            className="search-container">
        <div className="search-input-wrapper">
          {/* Kotak dan saran-sarannya satu kesatuan: saran MENEMPEL di bawah
              kotaknya, selebar kotaknya, seperti YouTube dan Google.

              Versi sebelumnya menaruh riwayat sebagai deretan chip DI LUAR
              kotak, di bawah seluruh formulir. Diminta pemiliknya diganti:
              "buat search bar itu mirip milik youtube atau google karena
              lebih bagus seperti itu dan clean". */}
          <div className="cari-kotak">
            <Search size={16} className="cari-ikon" aria-hidden="true" />
            <input
              type="text"
              className="search-input"
              placeholder="Tempel tautan YouTube, atau ketik kata kunci"
              value={draft}
              role="combobox"
              aria-expanded={cariAktif && saran.length > 0}
              aria-controls="cari-saran"
              aria-activedescendant={sorot >= 0 ? `saran-${sorot}` : undefined}
              autoComplete="off"
              onChange={(e) => { setDraft(e.target.value); setCariAktif(true); }}
              onFocus={() => setCariAktif(true)}
              onBlur={() => setCariAktif(false)}
              onKeyDown={tombolCari}
            />
            {draft && (
              <button type="button" className="cari-hapus" aria-label="Kosongkan"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => { setDraft(''); setCariAktif(true); }}>
                <X size={16} />
              </button>
            )}
            {cariAktif && saran.length > 0 && (
              <ul id="cari-saran" className="cari-saran" role="listbox">
                {saran.map((r, i) => {
                  const k = draft.trim();
                  const at = k ? r.query.toLowerCase().indexOf(k.toLowerCase()) : -1;
                  return (
                    <li key={r.query} id={`saran-${i}`} role="option"
                        aria-selected={i === sorot}
                        className={i === sorot ? 'is-on' : undefined}
                        // Tekan tetikus menjalankan pilihan SEBELUM kotak
                        // kehilangan fokus. Dulu jeda 180 milidetik dipakai
                        // untuk itu, dan klik yang sedikit lebih lambat
                        // hilang begitu saja.
                        onMouseDown={(e) => { e.preventDefault(); pilihSaran(r.query); }}
                        onMouseEnter={() => setSorot(i)}>
                      <History size={15} className="cari-saran-ikon" aria-hidden="true" />
                      <span className="cari-saran-teks">
                        {at < 0 ? r.query : (
                          <>
                            {r.query.slice(0, at)}
                            <b>{r.query.slice(at, at + k.length)}</b>
                            {r.query.slice(at + k.length)}
                          </>
                        )}
                      </span>
                      <button type="button" className="cari-saran-buang"
                              aria-label={`Hapus "${r.query}" dari riwayat`}
                              onMouseDown={(e) => {
                                e.preventDefault(); e.stopPropagation();
                                buangRiwayat(r.query);
                              }}>
                        Hapus
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
          <button type="submit" className="btn-primary" disabled={loading}
                  style={{ minWidth: '104px' }}>
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
            Cari
          </button>
        </div>
      </form>

      <div style={{
        display: 'flex', gap: '8px', overflowX: 'auto',
        paddingBottom: '8px', marginBottom: '20px', scrollbarWidth: 'none',
      }}>
        {CATEGORIES.map((cat, i) => (
          <button
            key={cat.label}
            onClick={() => setParams({ q: cat.query })}
            className={`chip${activeCategory === i ? ' is-on' : ''}`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Urutan hanya berlaku untuk pencarian: beranda tanpa kata kunci sudah
          mengambil kueri acak tiap muat, dan mengurutkannya tidak berarti. */}
      {q && (
        <div style={{
          display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center',
          marginBottom: '18px',
        }}>
          <span className="mark" style={{ color: 'var(--ink-3)' }}>Urutkan</span>
          {SORTS.map(([id, label]) => (
            <button key={id} onClick={() => setSort(id)}
                    className={`chip${sort === id ? ' is-on' : ''}`}>
              {label}
            </button>
          ))}
        </div>
      )}
      {q && (
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center',
                      marginTop: '-8px', marginBottom: '18px' }}>
          <span className="mark" style={{ color: 'var(--ink-3)' }}>Durasi</span>
          {[['', 'Semua'], ['pendek', '< 4 mnt'], ['sedang', '4-20 mnt'], ['panjang', '> 20 mnt']]
            .map(([id, label]) => (
              <button key={id || 'semua'} onClick={() => setDurasi(id)}
                      className={`chip${durasi === id ? ' is-on' : ''}`}>{label}</button>
            ))}
          <span className="mark" style={{ color: 'var(--ink-3)', marginLeft: '8px' }}>Diunggah</span>
          {[['', 'Kapan saja'], ['hari', 'Hari ini'], ['minggu', 'Minggu ini'], ['bulan', 'Bulan ini'], ['tahun', 'Tahun ini']]
            .map(([id, label]) => (
              <button key={id || 'kapan'} onClick={() => setTanggal(id)}
                      className={`chip${tanggal === id ? ' is-on' : ''}`}>{label}</button>
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
          <h3 style={{ fontWeight: 700, marginBottom: '6px' }}>Pencarian gagal</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6, maxWidth: '440px', margin: '0 auto' }}>
            {error.message}
          </p>
          {error.code === 'YTDLP_RATE_LIMIT' && (
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '10px', lineHeight: 1.6 }}>
              YouTube sedang membatasi permintaan dari komputer ini. Tunggu beberapa
              menit, atau pasang berkas cookies di halaman Settings.
            </p>
          )}
          <button className="btn-secondary" style={{ marginTop: '16px', fontSize: '0.83rem' }}
                  onClick={() => setNonce((n) => n + 1)}>
            Coba lagi
          </button>
        </div>
      ) : feed.length === 0 ? (
        <div style={{ padding: '60px 20px', textAlign: 'center', background: 'var(--bg-card)', borderRadius: 'var(--r-md)', border: '1px dashed var(--border-color)' }}>
          <Video size={40} style={{ color: 'var(--text-muted)', marginBottom: '12px' }} />
          <h3 style={{ fontWeight: 700 }}>Tidak ada video ditemukan</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Coba kata kunci yang berbeda.
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
                     title="Pilih untuk diklip bersama"
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
                Gagal memuat lebih banyak: {error.message}
              </span>
            : menambah || (loading && feed.length)
              ? <><RefreshCw size={14} className="animate-spin" style={{ verticalAlign: '-2px' }} /> Memuat lagi…</>
              : habis || batas >= PLAFON
                ? 'Sudah sampai ujung hasil.'
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
            {pilih.size} video dipilih
          </span>
          <button className="btn-primary" onClick={klipSemua} disabled={mengantre}
                  style={{ fontSize: '0.8rem', display: 'inline-flex', gap: '6px',
                           alignItems: 'center' }}>
            {mengantre ? <Loader2 size={14} className="animate-spin" /> : <Scissors size={14} />}
            {mengantre ? 'Mengantre…' : 'Klip semuanya'}
          </button>
          <button onClick={() => setPilih(new Set())}
                  style={{ background: 'none', border: 'none', cursor: 'pointer',
                           color: 'var(--text-muted)', display: 'flex' }}
                  aria-label="Batalkan pilihan">
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
          {hasilAntre.masuk} video diantrekan
          {hasilAntre.sudah > 0 && `, ${hasilAntre.sudah} sudah pernah diklip`}
          {hasilAntre.gagal > 0 && `, ${hasilAntre.gagal} gagal`}
          . Lihat kemajuannya di Partitur.
        </div>
      )}
    </div>
  );
}
