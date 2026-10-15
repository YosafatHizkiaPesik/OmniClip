import React, { useEffect, useState } from 'react';
import { Loader2, Scissors, Sparkles, Wand2 } from 'lucide-react';
import { apiGet, apiPost } from '../../lib/api';
import { formatTime } from '../../utils/timeFormat';
import { angka, useT } from '../../lib/i18n';

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
  frameKeys = [], onFrameKeys, onSegments,
}) {
  const t = useT();
  const [hasil, setHasil] = useState(null);
  const [menyusun, setMenyusun] = useState(false);
  const [kemajuan, setKemajuan] = useState(null);
  const [galat, setGalat] = useState(null);
  // Hasil milik klip tertentu; berpindah klip mengosongkannya.
  useEffect(() => { setHasil(null); setGalat(null); }, [clip?.clip_id]);

  const [rapat, setRapat] = useState(null);
  const [merapat, setMerapat] = useState(false);

  /**
   * Membuang jeda dan gumaman.
   *
   * Hasilnya langsung diterapkan, bukan ditawarkan lebih dulu, karena apa yang
   * berubah paling jelas terlihat dengan MENONTONNYA — dan Undo mengembalikan
   * semuanya dalam satu tekan. Yang ditampilkan sesudahnya adalah angkanya:
   * berapa detik hilang, dan berapa potongan yang dibatalkan karena di sana
   * ternyata masih ada suara.
   */
  const rapatkan = async () => {
    if (!clip?.segments?.length || !onSegments) return;
    setMerapat(true);
    setGalat(null);
    try {
      // Menghitung jejak energi seluruh klip dari berkas sumbernya; pada
      // podcast satu jam di cakram lambat ini bukan hitungan detik.
      const r = await apiPost('/clip-rapatkan', {
        video_id: videoId, segments: clip.segments,
      }, { timeout: 180000 });
      setRapat(r);
      if (r.potongan) onSegments(r.segments);
    } catch (e) {
      setGalat(e.message);
    } finally {
      setMerapat(false);
    }
  };

  const susun = async (mesin) => {
    if (!clip?.segments?.length) return;
    // Kunci yang sudah disunting sendiri tidak ditimpa diam-diam. Undo tetap
    // bisa mengembalikannya, tapi keputusan menggantinya milik pengguna.
    const milikPengguna = (frameKeys ?? []).filter((k) => !k.asal && k.t > 0.05);
    if (milikPengguna.length && !window.confirm(
      t('sutradara.yakin_ganti'))) return;
    setMenyusun(true);
    setGalat(null);
    setHasil(null);
    setKemajuan({ progress: 0, message: t('sutradara.memulai') });
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
      if (job.status !== 'done') throw new Error(job.error || t('sutradara.gagal'));
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

  if (!clip) return <p style={kecil}>{t('studio.pilih_klip_dulu')}</p>;

  return (
    <div>
      <div style={kartu}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '7px', marginBottom: '6px' }}>
          <Scissors size={15} style={{ color: 'var(--reh)' }} />
          <b style={{ fontSize: '0.84rem' }}>{t('sutradara.rapatkan_judul')}</b>
        </div>
        <p style={{ ...kecil, margin: '0 0 9px' }}>
          {t('sutradara.rapatkan_ket')}
        </p>
        <button className="btn-secondary" onClick={rapatkan}
                disabled={merapat || !onSegments}
                style={{ fontSize: '0.8rem', display: 'inline-flex', gap: '6px',
                         alignItems: 'center' }}>
          {merapat ? <Loader2 size={14} className="animate-spin" /> : <Scissors size={14} />}
          {merapat ? t('sutradara.mengukur') : t('sutradara.rapatkan')}
        </button>
        {rapat && (
          <p style={{ ...kecil, margin: '9px 0 0',
                      color: rapat.potongan ? 'var(--entry)' : 'var(--text-secondary)' }}>
            {rapat.pesan}
            {rapat.ditahan > 0 && t('sutradara.ditahan', { n: rapat.ditahan })}
            {rapat.potongan > 0 && t('sutradara.undo')}
          </p>
        )}
      </div>

      <div style={{ ...kartu, borderColor: 'var(--accent-cyan)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '7px', marginBottom: '6px' }}>
          <Wand2 size={15} style={{ color: 'var(--accent-cyan)' }} />
          <b style={{ fontSize: '0.84rem' }}>{t('sutradara.susun_judul')}</b>
        </div>
        <p style={{ ...kecil, margin: '0 0 9px' }}>
          {t('sutradara.susun_ket_a')} <b>{t('sutradara.susun_ket_b')}</b>
          {t('sutradara.susun_ket_c')}
        </p>
        <div style={{ display: 'flex', gap: '7px', flexWrap: 'wrap' }}>
          <button className="btn-primary" onClick={() => susun('ai')} disabled={menyusun}
                  style={{ fontSize: '0.8rem', display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
            {menyusun ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
            {menyusun ? t('sutradara.menonton') : t('sutradara.susun_ai')}
          </button>
          <button className="btn-secondary" onClick={() => susun('lokal')} disabled={menyusun}
                  title={t('sutradara.lokal_judul')}
                  style={{ fontSize: '0.78rem' }}>
            {t('sutradara.lokal')}
          </button>
          {adaUsulan && !menyusun && (
            <button className="btn-secondary" onClick={buang} style={{ fontSize: '0.78rem' }}>
              {t('sutradara.buang')}
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
              <li>{t('sutradara.token', { n: angka(hasil.pemakaian.masuk) })}</li>
            )}
            {(hasil.kejutan ?? []).map((k) => (
              <li key={k.t}>{t('sutradara.kaget', { waktu: formatTime(k.t), db: k.di_atas_db })}</li>
            ))}
          </ul>
        )}
      </div>

      {galat && <p style={{ ...kecil, color: 'var(--danger)' }}>{galat}</p>}

      <p style={{ ...kecil, margin: '2px 2px 0' }}>
        {t('sutradara.catatan_a')} <b>{t('sutradara.catatan_b')}</b> {t('sutradara.catatan_c')}
      </p>
    </div>
  );
}
