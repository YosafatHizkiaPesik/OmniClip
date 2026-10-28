import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Sparkles, Loader2, AlertTriangle, CheckCircle2, Trash2, Clock, Film, RefreshCw, Search,
  RotateCw, ArrowRight,
} from 'lucide-react';
import { apiDelete, apiGet, apiPost } from '../../lib/api';
import ImportBar from './ImportBar';
import { namaMesin } from '../../lib/mesin';
import { formatTime } from '../../utils/timeFormat';
import BilahProses, { LapisProses } from '../../components/BilahProses';
import { useT } from '../../lib/i18n';

/**
 * Halaman depan Studio: setiap video yang diminta untuk diklip jadi satu kartu.
 *
 * Inilah yang membuat pengguna tidak perlu menunggui satu video sampai selesai.
 * Tekan "Clip" pada beberapa video, kembali mencari video lain, lalu buka
 * halaman ini untuk melihat mana yang sudah siap ditinjau.
 */

const POLL_MS = 2500;
// Jeda mencoba lagi sesudah permintaan gagal: lebih panjang, karena yang
// membuatnya gagal biasanya server yang sedang sibuk.
const POLL_ULANG_MS = 5000;

const STATUS_META = {
  queued: { label: 'partitur.status_queued', color: 'var(--text-secondary)', Icon: Clock },
  running: { label: 'partitur.status_running', color: 'var(--accent-cyan)', Icon: Loader2 },
  done: { label: 'partitur.status_done', color: 'var(--entry)', Icon: CheckCircle2 },
  failed: { label: 'partitur.status_failed', color: 'var(--accent-red, var(--danger))', Icon: AlertTriangle },
  empty: { label: 'partitur.status_empty', color: 'var(--text-muted)', Icon: AlertTriangle },
  unknown: { label: 'partitur.status_unknown', color: 'var(--text-muted)', Icon: Clock },
};

/**
 * "sekitar 10 menit lagi" dari sebuah waktu epoch.
 *
 * Kasar dengan sengaja: yang dibutuhkan pembacanya bukan detiknya, melainkan
 * apakah ini soal menit atau soal jam.
 */
function sebentarLagi(waktu, t) {
  const menit = Math.max(0, Math.round((waktu * 1000 - Date.now()) / 60000));
  if (menit <= 1) return t('partitur.sebentar');
  if (menit < 60) return t('partitur.menit_lagi', { n: menit });
  return t('partitur.jam_lagi', { n: Math.round(menit / 60) });
}

export default function StudioHome({ onOpen, onFindVideos }) {
  const t = useT();
  const [projects, setProjects] = useState(null);
  const [error, setError] = useState(null);
  // Kabar sesaat sesudah menghapus, misalnya ruang yang dibebaskan.
  const [pesan, setPesan] = useState(null);
  const timerRef = useRef(null);
  const [putaran, setPutaran] = useState(0);
  const [melanjutkan, setMelanjutkan] = useState(null);
  const [catatanLanjut, setCatatanLanjut] = useState({});
  const [saring, setSaring] = useState('semua');

  const load = useCallback(async () => {
    try {
      const data = await apiGet('/projects');
      setProjects(data);
      setError(null);
      return { data, gagal: false };
    } catch (err) {
      // Gagal memuat TIDAK boleh terlihat seperti sedang memuat.
      //
      // Dulu `projects` dibiarkan null di sini, dan null itulah yang membuat
      // layar menampilkan "Memuat daftar project…". Jadi permintaan yang habis
      // waktunya berubah jadi lingkaran berputar selamanya: tanpa pesan, tanpa
      // tombol coba lagi, dan satu-satunya jalan keluar menyegarkan halaman.
      // Terlapor pemiliknya 30 September 2026, terjadi tiap kali kembali dari
      // Studio saat auto bingkai berjalan.
      setError(err);
      setProjects((prev) => prev ?? []);
      return { data: [], gagal: true };
    }
  }, []);

  // Selama masih ada yang berjalan, daftar disegarkan berkala. Begitu semuanya
  // selesai, polling berhenti sendiri — tidak ada gunanya membebani server
  // untuk daftar yang tidak berubah.
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      const { data, gagal } = await load();
      if (!alive) return;
      const busy = (data || []).some((p) => p.status === 'running' || p.status === 'queued');
      // Sesudah gagal, coba lagi sendiri. Permintaan yang kehabisan waktu
      // karena server sedang sibuk hampir selalu berhasil pada percobaan
      // berikutnya, dan menyuruh pengguna menekan tombol untuk itu cuma
      // memindahkan pekerjaan server ke tangan pengguna.
      if (busy || gagal) timerRef.current = setTimeout(tick, gagal ? POLL_ULANG_MS : POLL_MS);
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
      t('partitur.hapus_tanya', { nama }));
    let hapusVideo = ikutVideo;
    if (!ikutVideo) {
      // eslint-disable-next-line no-alert
      if (!window.confirm(t('partitur.hapus_kartu_saja', { nama }))) return;
      hapusVideo = false;
    }
    try {
      const r = await apiDelete(
        `/projects/${videoId}${hapusVideo ? '?hapus_video=true' : ''}`);
      setProjects((prev) => prev.filter((x) => x.video_id !== videoId));
      if (r?.bita_dibebaskan > 0) {
        setPesan(t('partitur.dibebaskan', { gb: (r.bita_dibebaskan / 1e9).toFixed(2) }));
        setTimeout(() => setPesan(null), 6000);
      }
    } catch (err) {
      setError(err);
    }
  };

  if (projects === null) {
    return (
      <div className="rak" aria-busy="true">
        <header className="rak-kepala">
          <div className="rak-kepala-teks">
            <h1 className="work-title rak-judul">{t('partitur.judul')}</h1>
            <p className="rak-angka"><span>{t('partitur.memuat')}</span></p>
          </div>
        </header>
        <div className="rak-grid">
          {[0, 1, 2, 3].map((n) => (
            <div key={n} className="lembar lembar-kerangka">
              <div className="pit-frame"><div className="pit-well" style={{ aspectRatio: '16/9' }} /></div>
              <div className="lembar-badan">
                <div className="kerangka" style={{ height: 14, width: '85%' }} />
                <div className="kerangka" style={{ height: 11, width: '45%' }} />
                <div className="kerangka" style={{ height: 32, marginTop: 14 }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  const jumlah = {
    semua: projects.length,
    proses: projects.filter((p) => p.status === 'running' || p.status === 'queued').length,
    siap: projects.filter((p) => p.status === 'done').length,
    gagal: projects.filter((p) => p.status === 'failed' || p.status === 'empty').length,
  };
  const cocok = {
    semua: () => true,
    proses: (p) => p.status === 'running' || p.status === 'queued',
    siap: (p) => p.status === 'done',
    gagal: (p) => p.status === 'failed' || p.status === 'empty',
  };
  // Saring yang kosong kembali ke "Semua", supaya halaman tidak tampak kosong
  // hanya karena pekerjaan yang tadi dipilih sudah selesai.
  const saringKini = jumlah[saring] ? saring : 'semua';
  const tampil = projects.filter(cocok[saringKini]);

  return (
    <div className="rak">
      {pesan && (
        <div className="plate studio-note" style={{ marginBottom: '12px', fontSize: '.82rem' }}>
          {pesan}
        </div>
      )}
      <header className="rak-kepala">
        <div className="rak-kepala-teks">
          <h1 className="work-title rak-judul">{t('partitur.judul')}</h1>
          <p className="rak-angka">
            {projects.length ? (
              <>
                <span><b>{jumlah.semua}</b>{t('rak.video')}</span>
                {jumlah.proses > 0 && <span className="is-reh"><b>{jumlah.proses}</b>{t('rak.diproses')}</span>}
                <span className="is-entry"><b>{jumlah.siap}</b>{t('rak.siap')}</span>
                {jumlah.gagal > 0 && <span><b>{jumlah.gagal}</b>{t('rak.gagal')}</span>}
              </>
            ) : <span>{t('partitur.kosong_sub')}</span>}
          </p>
        </div>
        <div className="rak-aksi">
          <ImportBar onDone={load} />
          <button className="btn-secondary" onClick={load} title={t('umum.segarkan')}>
            <RefreshCw size={14} /> {t('umum.segarkan')}
          </button>
          <button className="btn-primary" onClick={onFindVideos}>
            <Search size={14} /> {t('tonton.cari_video')}
          </button>
        </div>
      </header>

      {error && (
        <div className="rak-galat" role="alert">
          <AlertTriangle size={15} />
          <span>{error.name === 'TimeoutError' ? t('partitur.timeout') : error.message}</span>
          <button type="button" className="btn-secondary" onClick={() => setPutaran((n) => n + 1)}>
            <RotateCw size={13} /> {t('umum.coba_lagi')}
          </button>
        </div>
      )}

      {projects.length > 0 && (
        <div className="rak-alat">
          <div className="seg" role="tablist" aria-label={t('rak.saring')}>
            {[['semua', 'rak.s_semua'], ['proses', 'rak.s_proses'], ['siap', 'rak.s_siap'], ['gagal', 'rak.s_gagal']]
              .filter(([k]) => k === 'semua' || jumlah[k] > 0)
              .map(([k, kunci]) => (
                <button key={k} role="tab" aria-selected={saringKini === k}
                        className={saringKini === k ? 'is-on' : undefined} onClick={() => setSaring(k)}>
                  {t(kunci)} <span className="seg-n">{jumlah[k]}</span>
                </button>
              ))}
          </div>
        </div>
      )}

      {!projects.length && !error && (
        <div className="rak-kosong">
          <Film size={36} />
          <h3>{t('partitur.kosong')}</h3>
          <p>
            {t('partitur.kosong_a')} <strong>{t('tonton.potong')}</strong>.{' '}
            {t('partitur.kosong_b')}
          </p>
          <button className="btn-primary" onClick={onFindVideos} style={{ marginTop: '18px' }}>
            <Search size={15} /> {t('tonton.cari_video')}
          </button>
        </div>
      )}

      <div className="rak-grid">
        {tampil.map((p) => {
          const meta = STATUS_META[p.status] ?? STATUS_META.unknown;
          const busy = p.status === 'running' || p.status === 'queued';
          const openable = p.status === 'done';
          const gagal = p.status === 'failed' || p.status === 'empty';
          const kelasTanda = openable ? 'tanda--siap' : gagal ? 'tanda--gagal' : 'tanda--antre';

          return (
            <article
              key={p.video_id}
              className={`lembar${openable ? ' is-buka' : ''}${gagal ? ' is-redup' : ''}`}
              onClick={() => openable && onOpen(p)}
              onKeyDown={(e) => { if (openable && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); onOpen(p); } }}
              tabIndex={openable ? 0 : undefined}
              aria-label={p.title}
            >
              <div className="pit-frame"><div className="pit-well" style={{ aspectRatio: '16/9' }}>
                {p.thumbnail && (
                  <img src={p.thumbnail} alt="" loading="lazy"
                       style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
                )}
                {p.duration ? <span className="lencana lencana--kb">{formatTime(p.duration)}</span> : null}
                {openable && p.clip_count > 0 && (
                  <span className="lencana lencana--kia lencana--hl">{t('ulang.n_klip', { n: p.clip_count })}</span>
                )}
                {busy && <LapisProses job={{ ...p.job, status: p.status }} />}
              </div></div>

              <div className="lembar-badan">
                <h2 className="lembar-judul" title={p.title}>{p.title}</h2>
                {p.channel && <div className="lembar-meta"><span>{p.channel}</span></div>}

                {/* Saat diproses, stepper di bawah sudah menyebut keadaannya. */}
                {!busy && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginTop: 2 }}>
                    <span className={`tanda ${kelasTanda}`}>
                      <meta.Icon size={13} />{t(meta.label)}
                    </span>
                    {p.engine && openable && (
                      <span className="tanda-lain" style={{ fontSize: '.72rem', color: 'var(--ink-3)' }}>
                        · {namaMesin(p.engine)}
                      </span>
                    )}
                  </div>
                )}

                {/* Kenapa mesinnya lokal. "heuristik" saja terbaca seperti
                    pilihan yang disengaja, padahal biasanya ia akibat Gemini
                    yang sedang penuh, dan mencoba lagi nanti sering berhasil. */}
                {p.sumber_rendah && openable && <div className="lembar-catatan">{p.sumber_rendah}</div>}

                {p.mesin_gagal && openable && (
                  <div className="lembar-catatan">
                    {t('partitur.mesin_gagal', { alasan: p.mesin_gagal })}
                    {/* Saran "cari ulang sendiri" hanya berguna bila memang
                        tidak ada yang akan mencarikannya. */}
                    {!p.coba_lagi_pada && t('partitur.cari_ulang_saran')}
                  </div>
                )}

                {/* Pencarian ulang yang dijadwalkan nanti. Disebut sebagai
                    keterangan, bukan sebagai keadaan video: klipnya sudah ada,
                    kartunya tetap bisa dibuka, dan yang akan terjadi nanti
                    hanya mengganti daftar klipnya dengan yang lebih baik. */}
                {p.coba_lagi_pada && openable && (
                  <div className="lembar-catatan">
                    {t('partitur.dijadwalkan', { kapan: sebentarLagi(p.coba_lagi_pada, t) })}
                  </div>
                )}

                {busy && <BilahProses job={{ ...p.job, status: p.status }} />}

                {p.status === 'failed' && p.job?.error && (
                  <div className="lembar-catatan" style={{ color: 'var(--danger)' }}>{p.job.error}</div>
                )}
                {busy && catatanLanjut[p.video_id]?.length > 0 && (
                  <div className="lembar-catatan">
                    {t('partitur.dilewati', { daftar: catatanLanjut[p.video_id].join(', ') })}
                  </div>
                )}

                <div className="lembar-kaki">
                  {p.status === 'failed' && (
                    <button className="btn-garis" disabled={melanjutkan === p.video_id}
                            title={t('partitur.lanjut_judul')}
                            onClick={(e) => lanjutkan(p.video_id, e)}>
                      {melanjutkan === p.video_id
                        ? <Loader2 size={13} className="animate-spin" /> : <RotateCw size={13} />}
                      {t('partitur.lanjut')}
                    </button>
                  )}
                  {openable && (
                    <button className="btn-garis" tabIndex={-1}
                            onClick={(e) => { e.stopPropagation(); onOpen(p); }}>
                      <Sparkles size={13} /> {t('partitur.buka_editor')} <ArrowRight size={13} />
                    </button>
                  )}
                  {!openable && p.status !== 'failed' && <span style={{ flex: 1 }} />}
                  <button className="ikon-btn is-bahaya"
                          onClick={(e) => handleDelete(p.video_id, e)}
                          title={t('partitur.hapus_judul')} aria-label={t('partitur.hapus_judul')}>
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
