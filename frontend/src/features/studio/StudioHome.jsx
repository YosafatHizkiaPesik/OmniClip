import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Sparkles, Loader2, AlertTriangle, CheckCircle2, Trash2, Clock, Film, RefreshCw, Search,
  RotateCw,
} from 'lucide-react';
import { apiDelete, apiGet, apiPost } from '../../lib/api';
import ImportBar from './ImportBar';
import { formatTime } from '../../utils/timeFormat';
import BilahProses from '../../components/BilahProses';

/**
 * Halaman depan Studio: setiap video yang diminta untuk diklip jadi satu kartu.
 *
 * Inilah yang membuat pengguna tidak perlu menunggui satu video sampai selesai.
 * Tekan "Clip" pada beberapa video, kembali mencari video lain, lalu buka
 * halaman ini untuk melihat mana yang sudah siap ditinjau.
 */

const POLL_MS = 2500;

const STATUS_META = {
  queued: { label: 'Menunggu antrean', color: 'var(--text-secondary)', Icon: Clock },
  running: { label: 'Sedang diproses', color: 'var(--accent-cyan)', Icon: Loader2 },
  done: { label: 'Siap ditinjau', color: 'var(--entry)', Icon: CheckCircle2 },
  failed: { label: 'Gagal', color: 'var(--accent-red, var(--danger))', Icon: AlertTriangle },
  empty: { label: 'Tidak ada klip', color: 'var(--text-muted)', Icon: AlertTriangle },
  unknown: { label: 'Belum diproses', color: 'var(--text-muted)', Icon: Clock },
};

/**
 * "sekitar 10 menit lagi" dari sebuah waktu epoch.
 *
 * Kasar dengan sengaja: yang dibutuhkan pembacanya bukan detiknya, melainkan
 * apakah ini soal menit atau soal jam.
 */
function sebentarLagi(waktu) {
  const menit = Math.max(0, Math.round((waktu * 1000 - Date.now()) / 60000));
  if (menit <= 1) return 'sebentar lagi';
  if (menit < 60) return `sekitar ${menit} menit lagi`;
  return `sekitar ${Math.round(menit / 60)} jam lagi`;
}

export default function StudioHome({ onOpen, onFindVideos }) {
  const [projects, setProjects] = useState(null);
  const [error, setError] = useState(null);
  // Kabar sesaat sesudah menghapus, misalnya ruang yang dibebaskan.
  const [pesan, setPesan] = useState(null);
  const timerRef = useRef(null);
  const [putaran, setPutaran] = useState(0);
  const [melanjutkan, setMelanjutkan] = useState(null);
  const [catatanLanjut, setCatatanLanjut] = useState({});

  const load = useCallback(async () => {
    try {
      const data = await apiGet('/projects');
      setProjects(data);
      setError(null);
      return data;
    } catch (err) {
      setError(err);
      return [];
    }
  }, []);

  // Selama masih ada yang berjalan, daftar disegarkan berkala. Begitu semuanya
  // selesai, polling berhenti sendiri — tidak ada gunanya membebani server
  // untuk daftar yang tidak berubah.
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      const data = await load();
      if (!alive) return;
      const busy = (data || []).some((p) => p.status === 'running' || p.status === 'queued');
      if (busy) timerRef.current = setTimeout(tick, POLL_MS);
    };
    tick();
    return () => { alive = false; clearTimeout(timerRef.current); };
  }, [load, putaran]);

  // Melanjutkan pekerjaan yang gagal atau terputus. Server menjalankannya ulang
  // dengan setelan yang sama, dan langkah yang sudah pernah selesai — unduhan,
  // transkrip — tidak diulang.
  const lanjutkan = async (videoId, e) => {
    e.stopPropagation();
    setMelanjutkan(videoId);
    try {
      const r = await apiPost(`/projects/${videoId}/lanjutkan`, {});
      setCatatanLanjut((prev) => ({ ...prev, [videoId]: r.dilewati ?? [] }));
      setPutaran((n) => n + 1);      // polling berhenti saat semua selesai; hidupkan lagi
    } catch (err) {
      setError(err);
    } finally {
      setMelanjutkan(null);
    }
  };

  /**
   * Menghapus kartu Partitur, dengan pilihan ikut membuang video mentahnya.
   *
   * Dulu video mentahnya SELALU tertinggal, dan tidak ada satu pun tempat di
   * layar yang menyebutkannya. Terukur pada penyimpanan pemiliknya: 42 video
   * sumber menumpuk sampai 37,9 GB, terbesar 3,99 GB. Tapi membuangnya
   * diam-diam juga salah — mengunduhnya lagi memakan menit-menit — jadi yang
   * benar adalah menanyakannya.
   */
  const handleDelete = async (videoId, e) => {
    e.stopPropagation();
    const p = (projects ?? []).find((x) => x.video_id === videoId);
    const nama = (p?.title || videoId).slice(0, 60);
    // eslint-disable-next-line no-alert
    const ikutVideo = window.confirm(
      `Hapus "${nama}" dari Partitur.\n\n`
      + 'TEKAN OK untuk menghapus kartunya BESERTA berkas video mentahnya '
      + '(membebaskan ruang, dan video itu harus diunduh lagi bila dipakai lagi).\n\n'
      + 'TEKAN Batal untuk pilihan berikutnya.');
    let hapusVideo = ikutVideo;
    if (!ikutVideo) {
      // eslint-disable-next-line no-alert
      if (!window.confirm(`Hapus kartunya saja, berkas videonya DIBIARKAN?\n\n"${nama}"`)) return;
      hapusVideo = false;
    }
    try {
      const r = await apiDelete(
        `/projects/${videoId}${hapusVideo ? '?hapus_video=true' : ''}`);
      setProjects((prev) => prev.filter((x) => x.video_id !== videoId));
      if (r?.bita_dibebaskan > 0) {
        setPesan(`Ruang yang dibebaskan: ${(r.bita_dibebaskan / 1e9).toFixed(2)} GB`);
        setTimeout(() => setPesan(null), 6000);
      }
    } catch (err) {
      setError(err);
    }
  };

  if (projects === null) {
    return (
      <div style={{ padding: '60px 20px', textAlign: 'center', color: 'var(--text-secondary)' }}>
        <Loader2 size={26} className="animate-spin" style={{ color: 'var(--accent-cyan)' }} />
        <p style={{ marginTop: '10px', fontSize: '0.85rem' }}>Memuat daftar project…</p>
      </div>
    );
  }

  return (
    <div style={{ paddingBottom: '40px' }}>
      {pesan && (
        <div className="plate studio-note" style={{ marginBottom: '12px', fontSize: '.82rem' }}>
          {pesan}
        </div>
      )}
      <header style={{
        display: 'flex', alignItems: 'center', gap: '12px',
        flexWrap: 'wrap', marginBottom: '18px',
      }}>
        <div>
          <h1 style={{ fontSize: '1.3rem', fontWeight: 800, marginBottom: '3px' }}>Partitur</h1>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: 0 }}>
            {projects.length
              ? `${projects.length} video · klik kartu untuk membuka editor`
              : 'Belum ada video yang diproses'}
          </p>
        </div>
        <div style={{ flex: 1 }} />
        <button className="btn-secondary" onClick={load} style={{ fontSize: '0.8rem' }}>
          <RefreshCw size={14} /> Segarkan
        </button>
        <button className="btn-primary" onClick={onFindVideos} style={{ fontSize: '0.8rem' }}>
          <Search size={14} /> Cari video
        </button>
      </header>

      <ImportBar onDone={load} />

      {error && (
        <div style={{
          padding: '11px 13px', marginBottom: '14px', fontSize: '0.82rem',
          borderRadius: 'var(--radius-md)', color: 'var(--accent-red, var(--danger))',
          background: 'color-mix(in srgb, var(--danger) 12%, transparent)', border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)',
        }}>
          {error.message}
        </div>
      )}

      {!projects.length && !error && (
        <div style={{
          maxWidth: '520px', margin: '50px auto', padding: '32px 24px', textAlign: 'center',
          background: 'var(--bg-card)', border: '1px dashed var(--border-color)',
          borderRadius: 'var(--radius-lg)',
        }}>
          <Film size={38} style={{ color: 'var(--text-muted)', marginBottom: '14px' }} />
          <h3 style={{ fontWeight: 700, marginBottom: '8px' }}>Belum ada project klip</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.65 }}>
            Buka halaman Cari video, pilih videonya, lalu tekan <strong>Potong jadi klip</strong>.
            Prosesnya berjalan di latar belakang, jadi Anda bisa langsung memilih
            video berikutnya tanpa menunggu.
          </p>
          <button className="btn-primary" onClick={onFindVideos}
                  style={{ marginTop: '18px', fontSize: '0.84rem' }}>
            <Search size={15} /> Cari video
          </button>
        </div>
      )}

      <div style={{
        display: 'grid', gap: '14px',
        gridTemplateColumns: 'repeat(auto-fill, minmax(268px, 1fr))',
      }}>
        {projects.map((p) => {
          const meta = STATUS_META[p.status] ?? STATUS_META.unknown;
          const busy = p.status === 'running' || p.status === 'queued';
          const openable = p.status === 'done';

          return (
            <div
              key={p.video_id}
              onClick={() => openable && onOpen(p)}
              style={{
                background: 'var(--bg-card)', border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-lg)', overflow: 'hidden',
                cursor: openable ? 'pointer' : 'default',
                display: 'flex', flexDirection: 'column',
                opacity: p.status === 'failed' ? 0.75 : 1,
              }}
            >
              <div className="pit-frame"><div className="pit-well" style={{ aspectRatio: '16/9' }}>
                {p.thumbnail && (
                  <img src={p.thumbnail} alt="" loading="lazy"
                       style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                )}
                {p.duration ? (
                  <span style={{
                    position: 'absolute', right: '7px', bottom: '7px', padding: '2px 6px',
                    background: 'rgba(0,0,0,0.8)', borderRadius: '4px',
                    fontSize: '0.68rem', fontWeight: 700, color: '#fff',
                    fontVariantNumeric: 'tabular-nums',
                  }}>
                    {formatTime(p.duration)}
                  </span>
                ) : null}
                {p.status === 'done' && p.clip_count > 0 && (
                  <span style={{
                    position: 'absolute', left: '7px', top: '7px', padding: '3px 8px',
                    background: 'var(--hl)', borderRadius: '99px',
                    fontSize: '0.68rem', fontWeight: 800, color: '#1A1400',
                  }}>
                    {p.clip_count} klip
                  </span>
                )}
              </div></div>

              <div style={{ padding: '11px 13px', display: 'flex', flexDirection: 'column', gap: '7px', flex: 1 }}>
                <div style={{
                  fontSize: '0.84rem', fontWeight: 700, lineHeight: 1.35,
                  display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                }}>
                  {p.title}
                </div>
                {p.channel && (
                  <div style={{ fontSize: '0.73rem', color: 'var(--text-muted)' }}>{p.channel}</div>
                )}

                <div style={{ flex: 1 }} />

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.74rem', color: meta.color }}>
                  <meta.Icon size={13} className={p.status === 'running' ? 'animate-spin' : undefined} />
                  <span style={{ fontWeight: 700 }}>{meta.label}</span>
                  {p.engine && p.status === 'done' && (
                    <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>
                      · {p.engine === 'gemini' ? 'Gemini'
                        : p.engine === 'openrouter' ? 'OpenRouter' : 'mesin lokal'}
                    </span>
                  )}
                </div>

                {/* Kenapa mesinnya lokal. "heuristik" saja terbaca seperti
                    pilihan yang disengaja, padahal biasanya ia akibat Gemini
                    yang sedang penuh, dan mencoba lagi nanti sering berhasil. */}
                {p.sumber_rendah && p.status === 'done' && (
                  <div style={{ fontSize: '0.71rem', color: 'var(--text-muted)',
                                lineHeight: 1.45 }}>
                    {p.sumber_rendah}
                  </div>
                )}

                {p.mesin_gagal && p.status === 'done' && (
                  <div style={{ fontSize: '0.71rem', color: 'var(--text-muted)',
                                lineHeight: 1.45 }}>
                    {p.mesin_gagal}, jadi klipnya dipilih mesin lokal.
                    {/* Saran "cari ulang sendiri" hanya berguna bila memang
                        tidak ada yang akan mencarikannya. */}
                    {!p.coba_lagi_pada && ' Buka editor lalu "Cari ulang klip" bila ingin dicoba lagi.'}
                  </div>
                )}

                {/* Pencarian ulang yang dijadwalkan nanti. Disebut sebagai
                    keterangan, bukan sebagai keadaan video: klipnya sudah ada,
                    kartunya tetap bisa dibuka, dan yang akan terjadi nanti
                    hanya mengganti daftar klipnya dengan yang lebih baik. */}
                {p.coba_lagi_pada && p.status === 'done' && (
                  <div style={{ fontSize: '0.71rem', color: 'var(--text-muted)',
                                lineHeight: 1.45 }}>
                    Klipnya akan dicari ulang dengan Gemini {sebentarLagi(p.coba_lagi_pada)}.
                    Sampai saat itu klip yang ada sekarang tetap bisa dibuka dan disunting.
                  </div>
                )}

                {busy && <BilahProses job={{ ...p.job, status: p.status }} />}

                {p.status === 'failed' && p.job?.error && (
                  <div style={{ fontSize: '0.71rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                    {p.job.error}
                  </div>
                )}
                {busy && catatanLanjut[p.video_id]?.length > 0 && (
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                    Dilanjutkan, dilewati: {catatanLanjut[p.video_id].join(', ')}.
                  </div>
                )}

                <div style={{ display: 'flex', gap: '7px', marginTop: '3px' }}>
                  {p.status === 'failed' && (
                    <button className="btn-primary" style={{ flex: 1, fontSize: '0.76rem', padding: '7px' }}
                            disabled={melanjutkan === p.video_id}
                            title="Menjalankan ulang dengan setelan yang sama. Unduhan dan transkrip yang sudah ada tidak diulang."
                            onClick={(e) => lanjutkan(p.video_id, e)}>
                      {melanjutkan === p.video_id
                        ? <Loader2 size={13} className="animate-spin" /> : <RotateCw size={13} />}
                      Lanjutkan proses
                    </button>
                  )}
                  {openable && (
                    <button className="btn-primary" style={{ flex: 1, fontSize: '0.76rem', padding: '7px' }}
                            onClick={(e) => { e.stopPropagation(); onOpen(p); }}>
                      <Sparkles size={13} /> Buka editor
                    </button>
                  )}
                  <button
                    onClick={(e) => handleDelete(p.video_id, e)}
                    title="Hapus hasil analisis"
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      width: '30px', height: '30px', borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-color)', background: 'transparent',
                      color: 'var(--text-muted)', cursor: 'pointer',
                    }}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
