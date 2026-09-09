import React, { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  Search, Download, Scissors, ArrowLeft, CheckCircle2, Sparkles, Loader2,
  Eye, Clock, AlertTriangle,
} from 'lucide-react';
import { apiGet, apiPost, downloadToDisk } from '../lib/api';
import { useJobRunner } from '../hooks/useJob';
import JobProgress from '../components/JobProgress';
import { ChannelAvatar, RelatedVideoCard, formatViews } from '../components/VideoCards';
import { formatDurationHuman } from '../utils/timeFormat';

const RESOLUTIONS = ['360p', '480p', '720p', '1080p', 'Audio MP3'];

/**
 * Halaman tonton.
 *
 * Sengaja dijaga tetap ringkas: pemutar, identitas video, dua tombol aksi, dan
 * rekomendasi. Pengaturan yang jarang diubah — panjang klip, model AI, ketelitian
 * transkrip — pindah ke Settings; menaruhnya di sini membuat layar penuh pilihan
 * yang harus dibaca ulang setiap kali membuka video.
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
  const [resolution, setResolution] = useState('720p');
  const downloadJob = useJobRunner();

  const [queueing, setQueueing] = useState(false);
  const [pending, setPending] = useState(null);
  const [notice, setNotice] = useState(null);

  useEffect(() => { window.scrollTo({ top: 0 }); }, [videoId]);

  useEffect(() => {
    let cancelled = false;
    setNotice(null);
    setPending(null);
    if (location.state?.video?.id === videoId) {
      setVideo(location.state.video);
      return undefined;
    }
    setVideo(null);
    apiGet(`/video-info?url=${encodeURIComponent(videoId)}`)
      .then((info) => { if (!cancelled) setVideo({ ...info, id: videoId }); })
      .catch((err) => { if (!cancelled) setInfoError(err); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId]);

  useEffect(() => {
    let cancelled = false;
    if (!video?.title) return undefined;
    setRelatedLoading(true);
    const q = `${video.channel ?? ''} ${video.title.split(' ').slice(0, 4).join(' ')}`;
    apiGet(`/search?q=${encodeURIComponent(q)}&limit=15`)
      .then((data) => {
        if (cancelled) return;
        setRelated((Array.isArray(data) ? data : []).filter((v) => v.id !== videoId).slice(0, 12));
      })
      .catch(() => { if (!cancelled) setRelated([]); })
      .finally(() => { if (!cancelled) setRelatedLoading(false); });
    return () => { cancelled = true; };
  }, [video?.title, video?.channel, videoId]);

  const startClip = useCallback(async () => {
    setPending(null);
    setQueueing(true);
    try {
      const res = await apiPost('/auto-clip', {
        video_id: videoId,
        // 0 = biarkan server menghitungnya dari durasi video. Angka tetap 8
        // memperlakukan podcast dua jam sama dengan video sepuluh menit.
        max_clips: Number(localStorage.getItem('omniclip_max_clips') || 0),
        // Preferensi tersimpan di Settings. Halaman ini tidak menanyakannya lagi.
        clip_length: localStorage.getItem('omniclip_clip_length') || 'medium',
        whisper_model: localStorage.getItem('omniclip_whisper_model') || 'base',
        gemini_model: localStorage.getItem('omniclip_gemini_model') || null,
      });
      setNotice({
        kind: res.cached ? 'cached' : 'queued',
        text: res.cached
          ? 'Video ini sudah pernah diklip. Hasilnya menunggu di Clip Studio.'
          : 'Diantrekan. Prosesnya berjalan di latar belakang — Anda bisa langsung memilih video lain.',
      });
    } catch (err) {
      setNotice({ kind: 'error', text: err.message });
    } finally {
      setQueueing(false);
    }
  }, [videoId]);

  const handleClip = async () => {
    if (queueing) return;
    setNotice(null);
    setQueueing(true);
    try {
      const info = await apiGet(`/video-info?url=${encodeURIComponent(videoId)}`);
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
      setNotice({ kind: 'error', text: `Gagal menyimpan file: ${err.message}` });
    }
  };

  if (infoError) {
    return (
      <div style={{ maxWidth: '520px', margin: '60px auto', textAlign: 'center' }}>
        <AlertTriangle size={34} style={{ color: 'var(--accent-red, var(--danger))', marginBottom: '12px' }} />
        <h3 style={{ fontWeight: 700, marginBottom: '7px' }}>Video tidak bisa dibuka</h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{infoError.message}</p>
        <button className="btn-primary" onClick={() => navigate('/')} style={{ marginTop: '16px' }}>
          <ArrowLeft size={14} /> Kembali ke feed
        </button>
      </div>
    );
  }

  const downloadResult = downloadJob.result;

  return (
    <div className="watch-layout" style={{ display: 'flex', gap: '24px', maxWidth: '100%' }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', gap: '10px', marginBottom: '16px' }}>
          <button className="btn-secondary" onClick={() => navigate(-1)} style={{ padding: '0 14px' }}>
            <ArrowLeft size={16} /> Kembali
          </button>
          <button className="btn-secondary" onClick={() => navigate('/')} style={{ padding: '0 14px' }}>
            <Search size={16} /> Cari video
          </button>
        </div>

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
            {video?.title ?? 'Memuat…'}
          </h2>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            flexWrap: 'wrap', gap: '12px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <ChannelAvatar name={video?.channel} size={32} />
              <div>
                <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>{video?.channel}</div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'flex', gap: '8px' }}>
                  {video?.views > 0 && (
                    <span><Eye size={10} style={{ verticalAlign: 'middle' }} /> {formatViews(video.views)} views</span>
                  )}
                  {video?.duration > 0 && (
                    <span><Clock size={10} style={{ verticalAlign: 'middle' }} /> {formatDurationHuman(video.duration)}</span>
                  )}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              <button onClick={() => { downloadJob.reset(); setShowDownload(true); }}
                      className="btn-secondary"
                      style={{
                        background: 'rgba(79, 172, 254, 0.12)',
                        borderColor: 'rgba(79, 172, 254, 0.35)',
                        color: '#4facfe', fontSize: '0.85rem',
                      }}>
                <Download size={16} /> Unduh video
              </button>
              <button onClick={handleClip} disabled={queueing} className="btn-primary"
                      style={{ background: 'linear-gradient(135deg, var(--danger), #ff4e50)', color: '#fff', fontSize: '0.85rem' }}>
                {queueing
                  ? <><Loader2 size={16} className="animate-spin" /> Mengantre…</>
                  : <><Scissors size={16} /><Sparkles size={14} /> Potong jadi klip</>}
              </button>
            </div>
          </div>

          {pending && (
            <div style={{
              marginTop: '14px', padding: '14px 16px', background: 'var(--bg-card)',
              border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)',
            }}>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start', marginBottom: '11px' }}>
                <Clock size={18} style={{ color: 'var(--accent-cyan)', flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <div style={{ fontSize: '0.92rem', fontWeight: 800, marginBottom: '4px' }}>
                    Video ini tidak punya subtitle di YouTube
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                    Durasinya {Math.round(pending.minutes)} menit, jadi ucapannya harus
                    disalin dulu di komputer ini — perkiraan{' '}
                    <strong style={{ color: 'var(--accent-cyan)' }}>± {pending.fast} menit</strong>.
                    Prosesnya berjalan di latar belakang, jadi Anda tetap bisa menonton
                    dan mengantre video lain sementara menunggu.
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                <button className="btn-primary" style={{ fontSize: '0.82rem' }} onClick={startClip}>
                  <Sparkles size={14} /> Lanjutkan
                </button>
                <button className="btn-secondary" style={{ fontSize: '0.82rem' }}
                        onClick={() => setPending(null)}>
                  Batal
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
                  <Scissors size={13} /> Buka Clip Studio
                </button>
              )}
              <button className="btn-secondary" style={{ fontSize: '0.78rem', padding: '6px 12px' }}
                      onClick={() => setNotice(null)}>
                Tutup
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="watch-sidebar" style={{ width: '360px', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <div style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '8px', paddingLeft: '4px' }}>
          Video lain
        </div>
        {relatedLoading ? (
          <div style={{ padding: '40px', textAlign: 'center' }}>
            <Loader2 size={24} className="animate-spin" style={{ color: 'var(--accent-cyan)' }} />
          </div>
        ) : related.length === 0 ? (
          <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Tidak ada video terkait ditemukan.
          </div>
        ) : (
          related.map((v) => (
            <RelatedVideoCard key={v.id} video={v}
                              onClick={() => navigate(`/watch/${v.id}`, { state: { video: v } })} />
          ))
        )}
      </div>

      {showDownload && (
        <div className="modal-overlay">
          <div className="modal-box" style={{ maxWidth: '420px' }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, borderBottom: '1px solid var(--border-color)', paddingBottom: '10px' }}>
              Unduh: <span style={{ color: 'var(--accent-cyan)', fontSize: '0.88rem' }}>
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
                  {res}
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
                      <Download size={13} /> Simpan ke Perangkat
                    </button>
                  </div>
                )}
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button className="btn-secondary" onClick={() => setShowDownload(false)}>Tutup</button>
              <button className="btn-primary" onClick={submitDownload} disabled={downloadJob.active}>
                {downloadJob.active
                  ? <><Loader2 size={15} className="animate-spin" /> Mengunduh…</>
                  : <><Download size={15} /> Unduh via Server</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
