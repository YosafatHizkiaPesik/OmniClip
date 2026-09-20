import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Film, Image as ImageIcon, Music, Upload, Loader2, Trash2, Wand2, Play, Square,
  Crosshair, Sparkles, X,
} from 'lucide-react';
import { apiDelete, apiGet, apiPost } from '../../lib/api';
import { formatTime } from '../../utils/timeFormat';

const IKON = { video: Film, gambar: ImageIcon, audio: Music };

export const POSISI = [
  ['penuh', 'Penuh'],
  ['atas', 'Separuh atas'],
  ['bawah', 'Separuh bawah'],
  ['tengah', 'Tengah'],
  ['sudut', 'Pojok'],
];

const kecil = { fontSize: '0.7rem', color: 'var(--text-secondary)', lineHeight: 1.45 };
const judul = {
  fontSize: '0.72rem', fontWeight: 800, letterSpacing: '0.04em',
  textTransform: 'uppercase', color: 'var(--text-secondary)', margin: '0 0 8px',
};
const kartu = {
  border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)',
  padding: '11px 12px', marginBottom: '12px',
};
const angka = {
  width: '64px', padding: '4px 6px', fontSize: '0.74rem', fontFamily: 'inherit',
  borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)',
  background: 'transparent', color: 'var(--text-primary)',
};

let urutId = 0;
const idBaru = () => `l${Date.now().toString(36)}${(urutId += 1)}`;

/**
 * Sisipan: berkas dari LUAR video sumber — cuplikan, gambar, musik, efek suara —
 * plus sutradara otomatis yang mengusulkan bingkai dan efek per momen.
 *
 * Usulan sutradara masuk sebagai kunci bingkai dan sisipan biasa, bertanda
 * "otomatis" beserta alasannya. Menjalankannya lagi hanya mengganti usulan
 * otomatis yang lama; apa pun yang ditambahkan pengguna sendiri tidak disentuh.
 */
export default function MediaPanel({
  clip, videoId, aspectRatio, waktuSekarang = 0, durasiKlip = 0,
  onLayers, frameKeys = [], onFrameKeys, sorot = null, onSorot = null,
}) {
  const [aset, setAset] = useState(null);
  const [galat, setGalat] = useState(null);
  const [unggah, setUnggah] = useState(false);
  const [sutradara, setSutradara] = useState(null);   // hasil terakhir
  const [menyusun, setMenyusun] = useState(false);
  // {progress, message} job sutradara yang sedang berjalan.
  const [kemajuan, setKemajuan] = useState(null);
  const [dengar, setDengar] = useState(null);
  const berkasRef = useRef(null);
  const audioRef = useRef(null);

  const lapisan = useMemo(() => clip?.media_layers ?? [], [clip]);
  const barisRef = useRef({});
  // Blok yang diklik di linimasa digulirkan ke pandangan di sini.
  useEffect(() => {
    if (sorot) barisRef.current[sorot]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [sorot]);
  const asetById = useMemo(
    () => Object.fromEntries((aset ?? []).map((a) => [a.id, a])), [aset]);

  const muat = () => apiGet('/aset').then((r) => setAset(r.aset || []))
    .catch((e) => setGalat(e.message));
  useEffect(() => { muat(); }, []);

  // Hasil sutradara milik klip tertentu; berpindah klip mengosongkannya.
  useEffect(() => { setSutradara(null); }, [clip?.clip_id]);

  const ubah = (id, patch) => onLayers(lapisan.map((l) => (l.id === id ? { ...l, ...patch } : l)));
  const hapus = (id) => onLayers(lapisan.filter((l) => l.id !== id));

  const tambah = (a) => {
    const t = Math.max(0, Math.min(waktuSekarang, Math.max(0, durasiKlip - 0.2)));
    const sisa = Math.max(0.2, durasiKlip - t);
    onLayers([...lapisan, {
      id: idBaru(), aset: a.id, jenis: a.jenis, nama: a.nama, t: Number(t.toFixed(2)),
      // Gambar tidak punya panjang sendiri: bawaannya empat detik. Video dan
      // suara sepanjang berkasnya, dipotong di akhir klip.
      dur: a.jenis === 'gambar' ? Math.min(4, sisa) : Number(Math.min(a.durasi || sisa, sisa).toFixed(2)),
      mulai_sumber: 0,
      posisi: a.jenis === 'gambar' ? 'sudut' : (a.jenis === 'video' ? 'bawah' : 'penuh'),
      // Cuplikan video dibisukan secara bawaan: suara orang yang sedang
      // membahasnya hampir selalu yang lebih penting.
      volume: a.jenis === 'video' ? 0 : (a.bawaan ? 0.8 : 0.35),
      // Musik (bukan efek) mengecil sendiri saat orang bicara.
      redam: a.jenis === 'audio' && !a.bawaan,
      asal: 'pengguna',
    }]);
  };

  const kirimBerkas = async (e) => {
    const f = e.target.files?.[0];
    e.target.value = '';
    if (!f) return;
    setUnggah(true); setGalat(null);
    try {
      const data = new FormData();
      data.append('berkas', f);
      const baru = await apiPost('/aset', data);
      await muat();
      tambah(baru);
    } catch (err) { setGalat(err.message); } finally { setUnggah(false); }
  };

  const hapusAset = async (a) => {
    if (!window.confirm(`Hapus "${a.nama}" dari pustaka? Klip yang memakainya kehilangan sisipan ini.`)) return;
    try { await apiDelete(`/aset/${a.id}`); await muat(); } catch (err) { setGalat(err.message); }
  };

  const putar = (a) => {
    const el = audioRef.current;
    if (!el) return;
    if (dengar === a.id) { el.pause(); setDengar(null); return; }
    el.src = `/api/aset/${encodeURIComponent(a.id)}/berkas`;
    el.currentTime = 0;
    el.play().then(() => setDengar(a.id)).catch(() => setDengar(null));
  };

  const susunOtomatis = async (mesin = 'ai') => {
    if (!clip) return;
    // Kunci yang sudah Anda sunting sendiri tidak ditimpa diam-diam. Undo tetap
    // bisa mengembalikannya, tapi keputusan menggantinya milik Anda.
    const milikPengguna = (frameKeys ?? []).filter((k) => !k.asal && k.t > 0.05);
    if (milikPengguna.length && !window.confirm(
      'Lajur Bingkai klip ini sudah Anda atur sendiri. Ganti dengan susunan sutradara? '
      + '(Bisa dikembalikan dengan Undo.)')) return;
    setMenyusun(true); setGalat(null); setSutradara(null);
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
      setSutradara(r);
      if (r.keys?.length) {
        // Bingkai susunan dari server tidak punya id; pratinjau memakainya
        // sebagai kunci elemen dan penanda bingkai terpilih.
        onFrameKeys(r.keys.map((k) => (k.layout?.frames ? {
          ...k,
          layout: { ...k.layout,
                    frames: k.layout.frames.map((f, i) => ({ ...f, id: f.id ?? `ai${k.t}-${i}` })) },
        } : k)));
      }
      if (r.layers?.length) {
        const tanpaOtomatis = lapisan.filter((l) => l.asal !== 'otomatis');
        onLayers([...tanpaOtomatis, ...r.layers.map((l) => ({ ...l, id: idBaru() }))]);
      }
    } catch (err) { setGalat(err.message); } finally { setMenyusun(false); setKemajuan(null); }
  };

  const buangOtomatis = () => {
    onLayers(lapisan.filter((l) => !l.asal));
    onFrameKeys((frameKeys ?? []).filter((k) => !k.asal));
    setSutradara(null);
  };

  const adaOtomatis = lapisan.some((l) => l.asal)
    || (frameKeys ?? []).some((k) => k.asal);

  if (!clip) return <p style={kecil}>Pilih klip dulu.</p>;

  const efek = (aset ?? []).filter((a) => a.bawaan);
  const milik = (aset ?? []).filter((a) => !a.bawaan);
  const urut = [...lapisan].sort((a, b) => (a.t ?? 0) - (b.t ?? 0));

  return (
    <div>
      <audio ref={audioRef} onEnded={() => setDengar(null)} hidden />

      {/* --- Sutradara otomatis --------------------------------------------- */}
      <div style={{ ...kartu, borderColor: 'var(--accent-cyan)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '7px', marginBottom: '6px' }}>
          <Wand2 size={15} style={{ color: 'var(--accent-cyan)' }} />
          <b style={{ fontSize: '0.84rem' }}>Sutradara bingkai</b>
        </div>
        <p style={{ ...kecil, margin: '0 0 9px' }}>
          AI menonton klip ini dan mengganti bingkai di momen reaksi: saat semua
          tertawa, wajah yang tertawa dipotong bergantian atau ditumpuk; saat
          pemain game kaget, wajahnya dibuat penuh — lalu kembali normal. Semua
          usulan muncul di lajur Bingkai bertanda ✦ dengan alasannya, dan bisa
          dihapus satu per satu.
        </p>
        <div style={{ display: 'flex', gap: '7px', flexWrap: 'wrap' }}>
          <button className="btn-primary" onClick={() => susunOtomatis('ai')} disabled={menyusun}
                  style={{ fontSize: '0.8rem', display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
            {menyusun ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
            {menyusun ? 'Menonton klip…' : 'Susun bingkai dengan AI'}
          </button>
          <button className="btn-secondary" onClick={() => susunOtomatis('lokal')} disabled={menyusun}
                  title="Tanpa internet dan tanpa kuota: dari tawa yang terdengar dan wajah yang terlihat"
                  style={{ fontSize: '0.78rem' }}>
            Mesin lokal
          </button>
          {adaOtomatis && !menyusun && (
            <button className="btn-secondary" onClick={buangOtomatis} style={{ fontSize: '0.78rem' }}>
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
        {sutradara && (
          <ul style={{ ...kecil, margin: '9px 0 0', paddingLeft: '17px' }}>
            {(sutradara.catatan ?? []).map((c, i) => <li key={i}>{c}</li>)}
            {sutradara.model && sutradara.pemakaian?.masuk && (
              <li>{sutradara.pemakaian.masuk.toLocaleString('id-ID')} token dipakai.</li>
            )}
            {(sutradara.kejutan ?? []).map((k) => (
              <li key={k.t}>Reaksi kaget di {formatTime(k.t)} — {k.di_atas_db} dB di atas kebiasaannya</li>
            ))}
          </ul>
        )}
      </div>

      {galat && <p style={{ ...kecil, color: 'var(--danger)' }}>{galat}</p>}

      {/* --- Sisipan di klip ini ------------------------------------------- */}
      <div style={judul}>Di klip ini ({urut.length})</div>
      {!urut.length && (
        <p style={{ ...kecil, margin: '0 0 12px' }}>
          Belum ada sisipan. Tambahkan dari pustaka di bawah — ia ditaruh di posisi
          garis main sekarang ({formatTime(waktuSekarang)}).
        </p>
      )}
      {urut.map((l) => {
        const a = asetById[l.aset];
        const Ikon = IKON[a?.jenis] ?? Music;
        const visual = a?.jenis === 'video' || a?.jenis === 'gambar';
        const bersuara = a?.jenis === 'audio' || (a?.jenis === 'video' && a?.punya_suara);
        return (
          <div key={l.id} ref={(el) => { barisRef.current[l.id] = el; }}
               onClick={() => onSorot?.(l.id)}
               style={{ ...kartu, padding: '9px 10px',
                        ...(sorot === l.id ? { borderColor: 'var(--hl)', background: 'var(--hl-wash)' } : {}) }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
              <Ikon size={14} style={{ flexShrink: 0, color: 'var(--text-secondary)' }} />
              <b style={{ fontSize: '0.78rem', flex: 1, minWidth: 0, overflow: 'hidden',
                          textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {a?.nama ?? 'Aset hilang'}
              </b>
              {l.asal === 'otomatis' && (
                <span style={{ fontSize: '0.62rem', fontWeight: 800, padding: '1px 6px',
                               borderRadius: '99px', background: 'var(--hl-wash)',
                               color: 'var(--accent-cyan)' }}>otomatis</span>
              )}
              <button className="btn-secondary studio-icon" title="Hapus sisipan ini"
                      onClick={() => hapus(l.id)}><X size={13} /></button>
            </div>
            {l.alasan && <p style={{ ...kecil, margin: '4px 0 0' }}>{l.alasan}</p>}
            {!a && (
              <p style={{ ...kecil, color: 'var(--danger)', margin: '4px 0 0' }}>
                Berkasnya sudah dihapus dari pustaka — sisipan ini akan dilewati saat render.
              </p>
            )}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center',
                          marginTop: '7px', fontSize: '0.72rem' }}>
              <label>Mulai <input type="number" step="0.1" min="0" style={angka}
                                  value={l.t ?? 0}
                                  onChange={(e) => ubah(l.id, { t: Math.max(0, Number(e.target.value) || 0) })} /></label>
              <button className="btn-secondary" style={{ fontSize: '0.68rem', padding: '3px 7px' }}
                      title="Pindahkan awalnya ke garis main"
                      onClick={() => ubah(l.id, { t: Number(waktuSekarang.toFixed(2)) })}>
                <Crosshair size={11} /> ke sini
              </button>
              <label>Lama <input type="number" step="0.1" min="0.1" style={angka}
                                 value={l.dur ?? ''}
                                 onChange={(e) => ubah(l.id, { dur: Math.max(0.1, Number(e.target.value) || 0.1) })} /></label>
              {a?.jenis === 'video' && (
                <label title="Detik keberapa di dalam berkasnya cuplikan ini dimulai">
                  Dari detik <input type="number" step="0.1" min="0" style={angka}
                                    value={l.mulai_sumber ?? 0}
                                    onChange={(e) => ubah(l.id, { mulai_sumber: Math.max(0, Number(e.target.value) || 0) })} />
                </label>
              )}
              {visual && (
                <select value={l.posisi ?? 'penuh'} onChange={(e) => ubah(l.id, { posisi: e.target.value })}
                        style={{ ...angka, width: 'auto' }}>
                  {POSISI.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
                </select>
              )}
              {bersuara && (
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                  Volume
                  <input type="range" min="0" max="2" step="0.05" value={l.volume ?? 1}
                         onChange={(e) => ubah(l.id, { volume: Number(e.target.value) })} />
                  <span style={{ width: '32px' }}>{Math.round((l.volume ?? 1) * 100)}%</span>
                </label>
              )}
              {bersuara && (
                <label title="Suara ini mengecil sendiri saat ada orang bicara"
                       style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <input type="checkbox" checked={!!l.redam}
                         onChange={(e) => ubah(l.id, { redam: e.target.checked })} />
                  Kecilkan saat orang bicara
                </label>
              )}
            </div>
          </div>
        );
      })}

      {/* --- Pustaka ------------------------------------------------------- */}
      <div style={{ ...judul, marginTop: '16px' }}>Berkas Anda</div>
      <button className="btn-secondary" onClick={() => berkasRef.current?.click()} disabled={unggah}
              style={{ fontSize: '0.8rem', display: 'inline-flex', gap: '6px', alignItems: 'center',
                       marginBottom: '9px' }}>
        {unggah ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
        {unggah ? 'Mengunggah…' : 'Impor video, gambar, atau musik'}
      </button>
      <input ref={berkasRef} type="file" hidden onChange={kirimBerkas}
             accept="video/*,audio/*,image/png,image/jpeg,image/webp,image/gif" />
      {aset === null && <p style={kecil}><Loader2 size={12} className="animate-spin" /> Memuat…</p>}
      {aset && !milik.length && (
        <p style={{ ...kecil, margin: '0 0 12px' }}>
          Belum ada. Contohnya cuplikan pertandingan untuk podcast bola, logo kanal,
          atau musik latar.
        </p>
      )}
      {milik.map((a) => {
        const Ikon = IKON[a.jenis] ?? Music;
        return (
          <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: '7px',
                                   padding: '6px 0', borderBottom: '1px solid var(--border-color)' }}>
            <Ikon size={14} style={{ color: 'var(--text-secondary)', flexShrink: 0 }} />
            <span style={{ fontSize: '0.76rem', flex: 1, minWidth: 0, overflow: 'hidden',
                           textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.nama}</span>
            <span style={kecil}>{a.jenis === 'gambar' ? 'gambar' : formatTime(a.durasi)}</span>
            {a.jenis === 'audio' && (
              <button className="btn-secondary studio-icon" onClick={() => putar(a)}
                      title="Dengarkan">{dengar === a.id ? <Square size={12} /> : <Play size={12} />}</button>
            )}
            <button className="btn-secondary" style={{ fontSize: '0.7rem', padding: '3px 8px' }}
                    onClick={() => tambah(a)}>+ Tambah</button>
            <button className="btn-secondary studio-icon" onClick={() => hapusAset(a)}
                    title="Hapus dari pustaka"><Trash2 size={12} /></button>
          </div>
        );
      })}

      <div style={{ ...judul, marginTop: '16px' }}>Efek suara bawaan</div>
      <p style={{ ...kecil, margin: '0 0 7px' }}>
        Dibuat sendiri oleh sistem, jadi bebas dipakai dan tidak butuh internet.
        Susun otomatis memilih dari daftar ini.
      </p>
      {efek.map((a) => (
        <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: '7px',
                                 padding: '6px 0', borderBottom: '1px solid var(--border-color)' }}>
          <button className="btn-secondary studio-icon" onClick={() => putar(a)} title="Dengarkan">
            {dengar === a.id ? <Square size={12} /> : <Play size={12} />}
          </button>
          <span style={{ flex: 1, minWidth: 0 }}>
            <span style={{ fontSize: '0.78rem', fontWeight: 700, display: 'block' }}>{a.nama}</span>
            <span style={kecil}>{a.catatan}</span>
          </span>
          <button className="btn-secondary" style={{ fontSize: '0.7rem', padding: '3px 8px' }}
                  onClick={() => tambah(a)}>+ Tambah</button>
        </div>
      ))}
    </div>
  );
}
