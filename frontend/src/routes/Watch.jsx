import React, { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  Download, Scissors, ArrowLeft, CheckCircle2, Sparkles, Loader2,
  Eye, Clock, AlertTriangle,
} from 'lucide-react';
import { apiDelete, apiGet, apiPost, downloadToDisk } from '../lib/api';
import { angkaRingkas, useT } from '../lib/i18n';
import { useChannelInfo } from '../lib/avatarChannel';
import { useJobRunner } from '../hooks/useJob';
import JobProgress from '../components/JobProgress';
import { ChannelAvatar, RelatedVideoCard, formatViews, useKeChannel } from '../components/VideoCards';
import { formatDurationHuman } from '../utils/timeFormat';

// 1080p jadi bawaan, sama dengan RESOLUSI_BAWAAN di backend/app/services/ytdlp.
//
// Dulu "Terbaik" (sampai 2160p), dan itulah asal keluhan "video yang
// didownload terlalu besar hingga proses lama": terukur 42 video, 37,9 GB,
// terbesar 3,99 GB. Keluaran klip 9:16 adalah 1080x1920, dan jendela yang
// dipotong dari sumber 1080p selebar 608 piksel — cukup dekat. Dari 720p hanya
// 405, itu sebabnya 720p tidak dijadikan bawaan.
const RESOLUSI_BAWAAN = '1080p';
const RESOLUTIONS = ['1080p', 'Terbaik', '720p', '480p', '360p', 'Audio MP3'];
// Nilainya dikirim apa adanya ke server; hanya labelnya yang diterjemahkan.
const LABEL_RESOLUSI = { Terbaik: 'tonton.terbaik', 'Audio MP3': 'tonton.audio_mp3' };

/**
 * Halaman tonton.
 *
 * Sengaja dijaga tetap ringkas: pemutar, identitas video, dua tombol aksi, dan
 * rekomendasi. Pengaturan yang jarang diubah — model AI, ketelitian transkrip —
 * pindah ke Settings; menaruhnya di sini membuat layar penuh pilihan yang harus
 * dibaca ulang setiap kali membuka video.
 *
 * Panjang klip dulu juga dipilih di sini. Pilihannya dihapus: panjang tiap klip
 * sekarang ditentukan isinya, bukan oleh preset yang harus ditebak sebelum
 * videonya dianalisis.
 */
export default function Watch() {
  const { videoId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  // Video dari kartu yang diklik dipakai langsung supaya judul tampil seketika;
  // kalau halaman dibuka dari tautan langsung, metadatanya diambil dari server.
  const [video, setVideo] = useState(location.state?.video ?? null);
  const [infoError, setInfoError] = useState(null);
  const [related, setRelated] = useState([]);
  const [relatedLoading, setRelatedLoading] = useState(true);

  const [showDownload, setShowDownload] = useState(false);
  const [resolution, setResolution] = useState(RESOLUSI_BAWAAN);
  const downloadJob = useJobRunner();

  const [queueing, setQueueing] = useState(false);
  const [pending, setPending] = useState(null);
  // Resolusi sumber untuk mengklip. Diingat antar video: yang memilih 4K
  // sekali biasanya memang menginginkannya lagi.
  const [mutu, setMutu] = useState(
    () => localStorage.getItem('omniclip_mutu_klip') || '');
  const [pilihMutu, setPilihMutu] = useState(null);   // {pilihan, minutes, hasCaptions}
  const [mutuDipilih, setMutuDipilih] = useState(false);

  /** Memilih resolusi lalu melanjutkan ke pemeriksaan subtitle. */
  const pakaiMutu = (nilai) => {
    setMutu(nilai);
    try { localStorage.setItem('omniclip_mutu_klip', nilai); } catch { /* mode privat */ }
    const info = pilihMutu;
    setPilihMutu(null);
    setMutuDipilih(true);
    // Video panjang tanpa subtitle tetap ditanyakan sesudah ini.
    if (info && !info.hasCaptions && info.minutes > 12) {
      setPending({ minutes: info.minutes, fast: Math.ceil(info.minutes * 0.3) });
      return;
    }
    setQueueing(true);
    startClip(nilai);
  };
  const [notice, setNotice] = useState(null);

  useEffect(() => { window.scrollTo({ top: 0 }); }, [videoId]);

  // --- Gaya YouTube (JOB-3 J3-6, J3-7) ---------------------------------------
  const t = useT();
  const keChannel = useKeChannel();
  const infoChannel = useChannelInfo(video?.channel_id);
  const [diikuti, setDiikuti] = useState(false);
  const [deskripsiBuka, setDeskripsiBuka] = useState(false);
  const [dariChannel, setDariChannel] = useState([]);

  // Riwayat tontonan: dicatat sekali tiap video dibuka.
  useEffect(() => {
    if (!video?.title || video.id !== videoId) return;
    apiPost('/riwayat-tonton', {
      id: videoId, title: video.title || '', channel: video.channel || '',
      channel_id: video.channel_id || '', thumbnail: video.thumbnail || '',
      duration: video.duration || null, views: video.views || null,
    }).catch(() => {});
  }, [video?.title, video?.id, videoId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!video?.channel_id) return undefined;
    let batal = false;
    apiGet('/channel/ikuti').then((r) => {
      if (!batal) setDiikuti((r.channel ?? []).some((c) => c.channel_id === video.channel_id));
    }).catch(() => {});
    apiGet(`/channel/${encodeURIComponent(video.channel_id)}?batas=12`, { timeout: 90000 })
      .then((r) => { if (!batal) setDariChannel((r.video ?? []).filter((v) => v.id !== videoId)); })
      .catch(() => {});
    return () => { batal = true; };
  }, [video?.channel_id, videoId]);

  const ubahIkuti = async () => {
    const cid = video?.channel_id;
    if (!cid) return;
    if (diikuti) await apiDelete(`/channel/ikuti/${encodeURIComponent(cid)}`);
    else await apiPost('/channel/ikuti', { channel_id: cid, nama: video.channel || '', avatar: infoChannel?.avatar || '' });
    setDiikuti(!diikuti);
    window.dispatchEvent(new Event('omniclip:ikuti'));
  };

  useEffect(() => {
    let cancelled = false;
    setNotice(null);
    setPending(null);
    // Dibuka dari kartu: tampil seketika dari data kartunya, lalu dilengkapi
    // dari /video-info. Deskripsi di hasil pencarian hanya cuplikan pendek,
    // jadi tanpa ini "Selengkapnya" tidak membuka apa-apa (dilaporkan pemilik
    // 15 Oktober 2026). Kegagalan melengkapi tidak menjadi galat halaman.
    const dariKartu = location.state?.video?.id === videoId;
    if (dariKartu) setVideo(location.state.video);
    else setVideo(null);
    apiGet(`/video-info?url=${encodeURIComponent(videoId)}`)
      .then((info) => {
        if (cancelled) return;
        setVideo((lama) => (dariKartu
          ? { ...lama, description: info.description || lama?.description,
              channel_id: lama?.channel_id || info.channel_id }
          : { ...info, id: videoId }));
      })
      .catch((err) => { if (!cancelled && !dariKartu) setInfoError(err); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId]);

  useEffect(() => {
    let cancelled = false;
    if (!video?.title) return undefined;
    setRelatedLoading(true);
    const q = `${video.channel ?? ''} ${video.title.split(' ').slice(0, 4).join(' ')}`;
    // `catat=0`: kueri ini buatan halaman, bukan ketikan orangnya, jadi tidak
    // boleh masuk riwayat pencarian.
    apiGet(`/search?q=${encodeURIComponent(q)}&limit=15&catat=0`)
      .then((data) => {
        if (cancelled) return;
        setRelated((Array.isArray(data) ? data : []).filter((v) => v.id !== videoId).slice(0, 12));
      })
      .catch(() => { if (!cancelled) setRelated([]); })
      .finally(() => { if (!cancelled) setRelatedLoading(false); });
    return () => { cancelled = true; };
  }, [video?.title, video?.channel, videoId]);

  // `mutuPakai` diberikan saat resolusinya BARU SAJA dipilih: keadaan React
  // belum tentu terbarui saat pemanggilnya berjalan, dan mengandalkannya
  // berarti video pertama sesudah memilih tetap memakai resolusi yang lama.
  const startClip = useCallback(async (mutuPakai) => {
    const mutuFinal = typeof mutuPakai === 'string' ? mutuPakai : mutu;
    setPending(null);
    setQueueing(true);
    try {
      const res = await apiPost('/auto-clip', {
        video_id: videoId,
        // Resolusi sumber yang diunduh untuk diklip. Dipilih di kotak sebelum
        // tombolnya, dan diingat untuk video berikutnya.
        ...(mutuFinal ? { quality: mutuFinal } : {}),
        // 0 = biarkan server menghitungnya dari durasi video. Angka tetap 8
        // memperlakukan podcast dua jam sama dengan video sepuluh menit.
        max_clips: Number(localStorage.getItem('omniclip_max_clips') || 0),
        // Panjang milik video ini, dipilih tepat di atas tombolnya.
        whisper_model: localStorage.getItem('omniclip_whisper_model') || 'base',
        gemini_model: localStorage.getItem('omniclip_gemini_model') || null,
      });
      setNotice({
        kind: res.cached ? 'cached' : 'queued',
        text: res.cached
          ? t('tonton.sudah_diklip')
          : t('tonton.diantrekan'),
      });
    } catch (err) {
      setNotice({ kind: 'error', text: err.message });
    } finally {
      setQueueing(false);
    }
  }, [videoId, mutu, t]);

  /**
   * Menanyakan resolusi sumber SEBELUM mengklip.
   *
   * Sampai 29 September 2026 resolusinya dipatok 1080p tanpa bisa dipilih.
   * Angka itu benar untuk kebanyakan klip 9:16 dan jauh lebih murah didekode,
   * tapi pemiliknya melihat mutunya menurun pada sumber yang aslinya lebih
   * tinggi. Yang benar bukan mengganti patokannya, melainkan menanyakannya:
   * klip wajah dari podcast 4K memang pantas diambil dari 4K, dan klip gameplay
   * 1080p tidak akan membaik walau sumbernya dipaksa lebih tinggi.
   *
   * Daftarnya datang dari format yang BENAR-BENAR ditawarkan video itu, jadi
   * tidak pernah menjanjikan 1080p pada video yang maksimal 480p.
   */
  const handleClip = async () => {
    if (queueing) return;
    setNotice(null);
    setQueueing(true);
    try {
      const info = await apiGet(`/video-info?url=${encodeURIComponent(videoId)}`);
      const pilihan = (info.available_resolutions || [])
        .filter((r) => !/audio/i.test(r));
      if (pilihan.length > 1 && !mutuDipilih) {
        setPilihMutu({ pilihan, minutes: (info.duration || 0) / 60,
                       hasCaptions: info.has_captions });
        setQueueing(false);
        return;
      }
      const minutes = (info.duration || 0) / 60;
      // Video panjang tanpa subtitle harus disalin ucapannya di CPU. Ini satu-
      // satunya pilihan yang tetap ditanyakan di sini, karena hanya muncul saat
      // benar-benar relevan dan menyangkut waktu tunggu yang lama.
      if (!info.has_captions && minutes > 12) {
        const fast = Math.ceil(minutes * 0.3);
        setPending({ minutes, fast });
        setQueueing(false);
        return;
      }
      await startClip();
    } catch (err) {
      setNotice({ kind: 'error', text: err.message });
      setQueueing(false);
    }
  };

  const submitDownload = async () => {
    try {
      await downloadJob.run('/download', { url: videoId, resolution });
    } catch { /* error tampil di modal lewat downloadJob.error */ }
  };

  const saveToDisk = async (fileName) => {
    try {
      await downloadToDisk('local_downloads', fileName);
    } catch (err) {
      setNotice({ kind: 'error', text: t('tonton.gagal_simpan', { pesan: err.message }) });
    }
  };

  if (infoError) {
    return (
      <div style={{ maxWidth: '520px', margin: '60px auto', textAlign: 'center' }}>
        <AlertTriangle size={34} style={{ color: 'var(--accent-red, var(--danger))', marginBottom: '12px' }} />
        <h3 style={{ fontWeight: 700, marginBottom: '7px' }}>{t('tonton.tidak_bisa')}</h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{infoError.message}</p>
        <button className="btn-primary" onClick={() => navigate('/')} style={{ marginTop: '16px' }}>
          <ArrowLeft size={14} /> {t('tonton.kembali_feed')}
        </button>
      </div>
    );
  }

  const downloadResult = downloadJob.result;

  return (
    <div className="watch-layout" style={{ display: 'flex', gap: '24px', maxWidth: '100%' }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ background: '#000', borderRadius: '14px', overflow: 'hidden' }}>
          <iframe
            key={videoId}
            src={`https://www.youtube-nocookie.com/embed/${videoId}?autoplay=1&rel=0&enablejsapi=1&origin=${window.location.origin}`}
            title={video?.title ?? 'Video'}
            style={{ width: '100%', height: '420px', border: 'none', display: 'block' }}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            referrerPolicy="strict-origin-when-cross-origin"
          />
        </div>

        <div style={{ padding: '14px 0' }}>
          <h2 style={{ fontSize: '1.15rem', fontWeight: 700, lineHeight: 1.4, marginBottom: '10px' }}>
            {video?.title ?? t('umum.memuat')}
          </h2>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            flexWrap: 'wrap', gap: '12px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span onClick={(e) => keChannel(e, video?.channel_id)}
                    style={{ cursor: video?.channel_id ? 'pointer' : 'default', display: 'inline-flex' }}>
                <ChannelAvatar name={video?.channel} channelId={video?.channel_id} size={40} />
              </span>
              <div>
                <div className={video?.channel_id ? 'tautan-channel' : undefined}
                     onClick={(e) => keChannel(e, video?.channel_id)}
                     style={{ fontWeight: 700, fontSize: '0.95rem' }}>{video?.channel}</div>
                {infoChannel?.pelanggan != null && (
                  <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                    {t('channel.subscriber', { n: angkaRingkas(infoChannel.pelanggan) })}
                  </div>
                )}
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'flex', gap: '8px' }}>
                  {video?.views > 0 && (
                    <span><Eye size={10} style={{ verticalAlign: 'middle' }} /> {t('kartu.tayangan', { n: formatViews(video.views) })}</span>
                  )}
                  {video?.duration > 0 && (
                    <span><Clock size={10} style={{ verticalAlign: 'middle' }} /> {formatDurationHuman(video.duration)}</span>
                  )}
                </div>
              </div>
            </div>

            {video?.channel_id && (
              <button onClick={ubahIkuti} className={diikuti ? 'btn-secondary' : 'btn-primary'}
                      style={{ borderRadius: 999, padding: '8px 16px', marginRight: 'auto' }}>
                {diikuti ? t('channel.berhenti_ikuti') : t('channel.ikuti')}
              </button>
            )}
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              <button onClick={() => { downloadJob.reset(); setShowDownload(true); }}
                      className="btn-secondary"
                      style={{
                        background: 'rgba(79, 172, 254, 0.12)',
                        borderColor: 'rgba(79, 172, 254, 0.35)',
                        color: '#4facfe', fontSize: '0.85rem',
                      }}>
                <Download size={16} /> {t('tonton.unduh')}
              </button>
              <button onClick={handleClip} disabled={queueing} className="btn-primary"
                      style={{ background: 'linear-gradient(135deg, var(--danger), #ff4e50)', color: '#fff', fontSize: '0.85rem' }}>
                {queueing
                  ? <><Loader2 size={16} className="animate-spin" /> {t('kisi.mengantre')}</>
                  : <><Scissors size={16} /><Sparkles size={14} /> {t('tonton.potong')}</>}
              </button>
            </div>

          </div>

          {video?.description && (
            <div onClick={() => setDeskripsiBuka((v) => !v)}
                 style={{ marginTop: 14, padding: '12px 14px', borderRadius: 12, cursor: 'pointer',
                          background: 'var(--plate-2)', fontSize: '.84rem', lineHeight: 1.55,
                          whiteSpace: 'pre-line', color: 'var(--ink-2)' }}>
              <div style={{ ...(deskripsiBuka ? {} : { display: '-webkit-box', WebkitLineClamp: 3,
                                                        WebkitBoxOrient: 'vertical', overflow: 'hidden' }) }}>
                {video.description}
              </div>
              <div style={{ fontWeight: 700, marginTop: 6, color: 'var(--ink)' }}>
                {deskripsiBuka ? t('tonton.lebih_sedikit') : t('tonton.selengkapnya')}
              </div>
            </div>
          )}

          {pilihMutu && (
            <div style={{
              marginTop: '14px', padding: '14px 16px', background: 'var(--bg-card)',
              border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)',
            }}>
              <div style={{ fontSize: '0.92rem', fontWeight: 800, marginBottom: '4px' }}>
                {t('tonton.resolusi_tanya')}
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)',
                            lineHeight: 1.6, marginBottom: '12px' }}>
                {t('tonton.resolusi_jelas')}
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '10px' }}>
                {pilihMutu.pilihan.map((r) => {
                  const bawaan = r === '1080p';
                  return (
                    <button key={r} onClick={() => pakaiMutu(r)}
                            className={bawaan ? 'btn-primary' : 'btn-secondary'}
                            style={{ fontSize: '0.82rem' }}>
                      {r}{bawaan ? t('tonton.disarankan') : ''}
                    </button>
                  );
                })}
              </div>
              <button className="btn-secondary" style={{ fontSize: '0.78rem' }}
                      onClick={() => { setPilihMutu(null); setQueueing(false); }}>
                {t('umum.batal')}
              </button>
            </div>
          )}

          {pending && (
            <div style={{
              marginTop: '14px', padding: '14px 16px', background: 'var(--bg-card)',
              border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)',
            }}>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start', marginBottom: '11px' }}>
                <Clock size={18} style={{ color: 'var(--accent-cyan)', flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <div style={{ fontSize: '0.92rem', fontWeight: 800, marginBottom: '4px' }}>
                    {t('tonton.tanpa_subtitle')}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                    {t('tonton.tanpa_subtitle_a', { menit: Math.round(pending.minutes) })}{' '}
                    <strong style={{ color: 'var(--accent-cyan)' }}>{t('tonton.tanpa_subtitle_m', { menit: pending.fast })}</strong>
                    {t('tonton.tanpa_subtitle_b')}
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <button className="btn-primary" style={{ fontSize: '0.82rem' }} onClick={startClip}>
                  <Sparkles size={14} /> {t('umum.lanjutkan')}
                </button>
                <button className="btn-secondary" style={{ fontSize: '0.82rem' }}
                        onClick={() => setPending(null)}>
                  {t('umum.batal')}
                </button>
              </div>
            </div>
          )}

          {notice && (
            <div style={{
              marginTop: '14px', padding: '12px 15px', borderRadius: 'var(--radius-md)',
              display: 'flex', alignItems: 'center', gap: '11px', flexWrap: 'wrap',
              background: notice.kind === 'error' ? 'color-mix(in srgb, var(--danger) 12%, transparent)' : 'var(--hl-wash)',
              border: `1px solid ${notice.kind === 'error' ? 'color-mix(in srgb, var(--danger) 30%, transparent)' : 'var(--hl-wash)'}`,
            }}>
              {notice.kind === 'error'
                ? <AlertTriangle size={16} style={{ color: 'var(--accent-red, var(--danger))' }} />
                : <CheckCircle2 size={16} style={{ color: 'var(--accent-cyan)' }} />}
              <span style={{ fontSize: '0.83rem', flex: 1, minWidth: '200px' }}>{notice.text}</span>
              {notice.kind !== 'error' && (
                <button className="btn-primary" style={{ fontSize: '0.78rem', padding: '6px 12px' }}
                        onClick={() => navigate('/studio')}>
                  <Scissors size={13} /> {t('tonton.buka_studio')}
                </button>
              )}
              <button className="btn-secondary" style={{ fontSize: '0.78rem', padding: '6px 12px' }}
                      onClick={() => setNotice(null)}>
                {t('umum.tutup')}
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="watch-sidebar" style={{ width: '360px', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <div style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '8px', paddingLeft: '4px' }}>
          {t('tonton.video_lain')}
        </div>
        {relatedLoading ? (
          <div style={{ padding: '40px', textAlign: 'center' }}>
            <Loader2 size={24} className="animate-spin" style={{ color: 'var(--accent-cyan)' }} />
          </div>
        ) : related.length === 0 ? (
          <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            {t('tonton.tanpa_terkait')}
          </div>
        ) : (
          [...dariChannel.slice(0, 6),
            ...related.filter((v) => !dariChannel.slice(0, 6).some((d) => d.id === v.id))].map((v) => (
            <RelatedVideoCard key={v.id} video={v}
                              onClick={() => navigate(`/watch/${v.id}`, { state: { video: v } })} />
          ))
        )}
      </div>

      {showDownload && (
        <div className="modal-overlay">
          <div className="modal-box" style={{ maxWidth: '420px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, borderBottom: '1px solid var(--border-color)', paddingBottom: '10px' }}>
              {t('tonton.unduh_judul')} <span style={{ color: 'var(--accent-cyan)', fontSize: '0.88rem' }}>
                {(video?.title ?? '').slice(0, 48)}…
              </span>
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
              {RESOLUTIONS.map((res) => (
                <button key={res} onClick={() => setResolution(res)} style={{
                  padding: '10px 6px', borderRadius: '8px', fontWeight: 700, cursor: 'pointer', fontSize: '0.82rem',
                  border: resolution === res ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                  background: resolution === res ? 'var(--hl-wash)' : 'rgba(30,41,59,0.5)',
                  color: resolution === res ? 'var(--accent-cyan)' : 'var(--text-primary)',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px',
                }}>
                  {LABEL_RESOLUSI[res] ? t(LABEL_RESOLUSI[res]) : res}
                  {resolution === res && <CheckCircle2 size={13} />}
                </button>
              ))}
            </div>
            {(downloadJob.job || downloadJob.error) && (
              <div style={{ padding: '12px', background: 'var(--bg-glass)', border: '1px solid var(--border-color)', borderRadius: '10px' }}>
                <JobProgress job={downloadJob.job} error={downloadJob.error} onCancel={downloadJob.cancel} />
                {downloadResult && (
                  <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {downloadResult.note && (
                      <div style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>{downloadResult.note}</div>
                    )}
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                      {downloadResult.width}×{downloadResult.height} · {(downloadResult.file_size / 1048576).toFixed(1)} MB
                    </div>
                    <button onClick={() => saveToDisk(downloadResult.file_name)} className="btn-primary"
                            style={{ background: 'var(--entry)', color: '#fff', fontSize: '0.78rem', padding: '6px 12px', alignSelf: 'flex-start' }}>
                      <Download size={13} /> {t('tonton.simpan_perangkat')}
                    </button>
                  </div>
                )}
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button className="btn-secondary" onClick={() => setShowDownload(false)}>{t('umum.tutup')}</button>
              <button className="btn-primary" onClick={submitDownload} disabled={downloadJob.active}>
                {downloadJob.active
                  ? <><Loader2 size={15} className="animate-spin" /> {t('tonton.mengunduh')}</>
                  : <><Download size={15} /> {t('tonton.unduh_server')}</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}