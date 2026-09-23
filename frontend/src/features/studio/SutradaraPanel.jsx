import React, { useEffect, useState } from 'react';
import { Loader2, Sparkles, Wand2 } from 'lucide-react';
import { apiGet, apiPost } from '../../lib/api';
import { formatTime } from '../../utils/timeFormat';

const kecil = { fontSize: '0.72rem', color: 'var(--text-secondary)', lineHeight: 1.5 };
const kartu = {
  border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)',
  padding: '11px 12px', marginBottom: '12px',
};

let urutId = 0;
const idBaru = () => `l${Date.now().toString(36)}${(urutId += 1)}`;

/**
 * Sutradara: satu tempat untuk "racik klip ini sebagus mungkin".
 *
 * Dulu ia menumpang di panel Sisipan, di bawah pustaka musik dan gambar.
 * Tempatnya salah dan pemiliknya menanyakannya: menyusun bingkai sepanjang
 * klip bukan "menyisipkan berkas", dan sutradara akan tumbuh ke hal-hal lain
 * (gaya subtitle per penutur, warna, letak teks) yang tidak ada hubungannya
 * dengan sisipan sama sekali. Jadi ia berdiri sendiri.
 *
 * Yang dihasilkan tetap USULAN: kunci bingkai bertanda ✦ di lajur Bingkai
 * beserta alasannya, bisa digeser, dihapus satu per satu, di-Undo, dan baru
 * tersimpan ketika pengguna menekan Simpan.
 */
export default function SutradaraPanel({
  clip, videoId, aspectRatio, lapisan = [], onLayers,
  frameKeys = [], onFrameKeys,
}) {
  const [hasil, setHasil] = useState(null);
  const [menyusun, setMenyusun] = useState(false);
  const [kemajuan, setKemajuan] = useState(null);
  const [galat, setGalat] = useState(null);
  // Hasil milik klip tertentu; berpindah klip mengosongkannya.
  useEffect(() => { setHasil(null); setGalat(null); }, [clip?.clip_id]);

  const susun = async (mesin) => {
    if (!clip?.segments?.length) return;
    // Kunci yang sudah disunting sendiri tidak ditimpa diam-diam. Undo tetap
    // bisa mengembalikannya, tapi keputusan menggantinya milik pengguna.
    const milikPengguna = (frameKeys ?? []).filter((k) => !k.asal && k.t > 0.05);
    if (milikPengguna.length && !window.confirm(
      'Lajur Bingkai klip ini sudah Anda atur sendiri. Ganti dengan susunan sutradara? '
      + '(Bisa dikembalikan dengan Undo.)')) return;
    setMenyusun(true);
    setGalat(null);
    setHasil(null);
    setKemajuan({ progress: 0, message: 'Memulai…' });
    try {
      const { job_id: jobId } = await apiPost('/clip-sutradara-ai', {
        video_id: videoId, segments: clip.segments, aspect_ratio: aspectRatio,
        subtitles: (clip.subtitles ?? []).map((l) => ({
          start: l.start, end: l.end, text: l.text, speaker: l.speaker ?? null,
        })),
        mesin,
      });
      let job;
      for (;;) {
        // eslint-disable-next-line no-await-in-loop
        job = await apiGet(`/jobs/${jobId}`);
        setKemajuan({ progress: job.progress ?? 0, message: job.message || '' });
        if (['done', 'failed', 'cancelled'].includes(job.status)) break;
        // eslint-disable-next-line no-await-in-loop
        await new Promise((r) => setTimeout(r, 1200));
      }
      if (job.status !== 'done') throw new Error(job.error || 'Sutradara gagal.');
      const r = job.result || {};
      setHasil(r);
      if (r.keys?.length) {
        // Bingkai susunan dari server tidak punya id; pratinjau memakainya
        // sebagai kunci elemen dan penanda bingkai terpilih.
        onFrameKeys(r.keys.map((k) => (k.layout?.frames ? {
          ...k,
          layout: { ...k.layout,
                    frames: k.layout.frames.map((f, i) => ({ ...f, id: f.id ?? `ai${k.t}-${i}` })) },
        } : k)));
      }
      if (r.layers?.length && onLayers) {
        const tanpaOtomatis = lapisan.filter((l) => l.asal !== 'otomatis');
        onLayers([...tanpaOtomatis, ...r.layers.map((l) => ({ ...l, id: idBaru() }))]);
      }
    } catch (err) {
      setGalat(err.message);
    } finally {
      setMenyusun(false);
      setKemajuan(null);
    }
  };

  const buang = () => {
    if (onLayers) onLayers(lapisan.filter((l) => !l.asal));
    onFrameKeys((frameKeys ?? []).filter((k) => !k.asal));
    setHasil(null);
  };

  const adaUsulan = (frameKeys ?? []).some((k) => k.asal)
    || lapisan.some((l) => l.asal);

  if (!clip) return <p style={kecil}>Pilih klip dulu.</p>;

  return (
    <div>
      <div style={{ ...kartu, borderColor: 'var(--accent-cyan)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '7px', marginBottom: '6px' }}>
          <Wand2 size={15} style={{ color: 'var(--accent-cyan)' }} />
          <b style={{ fontSize: '0.84rem' }}>Susun bingkai per momen</b>
        </div>
        <p style={{ ...kecil, margin: '0 0 9px' }}>
          AI menonton klip ini dan mengganti bingkai di momen reaksi: saat semua
          tertawa, wajah yang tertawa dipotong bergantian atau ditumpuk; saat
          pemain game kaget, wajahnya dibuat penuh — lalu kembali normal. Bagian
          tanpa wajah mengikuti gerakan. Sutradara hanya memakai empat cara:
          <b> ikuti wajah, ikuti gerakan, game, dan susunan</b> — tidak pernah
          bilah kabur, jadi gambar selalu memenuhi layar. Semua usulan muncul di
          lajur Bingkai bertanda ✦ dengan alasannya, dan bisa dihapus satu per satu.
        </p>
        <div style={{ display: 'flex', gap: '7px', flexWrap: 'wrap' }}>
          <button className="btn-primary" onClick={() => susun('ai')} disabled={menyusun}
                  style={{ fontSize: '0.8rem', display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
            {menyusun ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
            {menyusun ? 'Menonton klip…' : 'Susun bingkai dengan AI'}
          </button>
          <button className="btn-secondary" onClick={() => susun('lokal')} disabled={menyusun}
                  title="Tanpa internet dan tanpa kuota: dari tawa yang terdengar dan wajah yang terlihat"
                  style={{ fontSize: '0.78rem' }}>
            Mesin lokal
          </button>
          {adaUsulan && !menyusun && (
            <button className="btn-secondary" onClick={buang} style={{ fontSize: '0.78rem' }}>
              Buang usulan sutradara
            </button>
          )}
        </div>
        {kemajuan && (
          <div style={{ marginTop: '9px' }}>
            <div style={{ height: '6px', borderRadius: '99px', background: 'var(--bg-glass)',
                          border: '1px solid var(--border-color)', overflow: 'hidden' }}>
              <div style={{ width: `${Math.round((kemajuan.progress || 0) * 100)}%`, height: '100%',
                            background: 'var(--accent-cyan)', transition: 'width .4s' }} />
            </div>
            <p style={{ ...kecil, margin: '5px 0 0' }}>{kemajuan.message}</p>
          </div>
        )}
        {hasil && (
          <ul style={{ ...kecil, margin: '9px 0 0', paddingLeft: '17px' }}>
            {(hasil.catatan ?? []).map((c, i) => <li key={i}>{c}</li>)}
            {hasil.model && hasil.pemakaian?.masuk && (
              <li>{hasil.pemakaian.masuk.toLocaleString('id-ID')} token dipakai.</li>
            )}
            {(hasil.kejutan ?? []).map((k) => (
              <li key={k.t}>Reaksi kaget di {formatTime(k.t)} — {k.di_atas_db} dB di atas kebiasaannya</li>
            ))}
          </ul>
        )}
      </div>

      {galat && <p style={{ ...kecil, color: 'var(--danger)' }}>{galat}</p>}

      <p style={{ ...kecil, margin: '2px 2px 0' }}>
        Sutradara menyentuh <b>hanya</b> potongan bertanda ✦. Bingkai yang Anda
        susun sendiri tidak ditimpa, dan menjalankannya lagi hanya mengganti
        usulan sebelumnya.
      </p>
    </div>
  );
}
