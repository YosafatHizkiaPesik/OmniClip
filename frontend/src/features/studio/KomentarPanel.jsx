import React, { useEffect, useRef, useState } from 'react';
import {
  Sparkles, Loader2, Mic, Square, Volume2, Trash2, Plus, Crosshair, AlertTriangle,
} from 'lucide-react';
import { apiGet, apiPost } from '../../lib/api';
import { formatTime } from '../../utils/timeFormat';

/**
 * Komentar pemilik kanal untuk satu klip (JOB-2 F1-3 sampai F1-6).
 *
 * Klip yang hanya potongan + subtitle dinilai YouTube sebagai "konten yang
 * digunakan ulang". Yang menambah nilai adalah suara ORANGNYA: pendapat,
 * reaksi, konteks. Panel ini tempat menulisnya, menaruhnya di waktu yang
 * tepat, lalu memberinya suara.
 *
 * Tiga tempat: PEMBUKA (sebelum klip mulai), SELA (di jeda antara dua kalimat)
 * dan PENUTUP (sesudah klip selesai). Saat dirender, gambar dibekukan selama
 * komentar diucapkan, jadi komentar tidak bertabrakan dengan orang di klip.
 *
 * Suara: rekaman mikrofon didahulukan, TTS cadangan. TTS menyalakan label
 * konten sintetis YouTube secara otomatis, dan itu ditentukan server dari
 * berkasnya, bukan dari panel ini.
 */

const POSISI = [
  { id: 'pembuka', label: 'Pembuka', hint: 'sebelum klip mulai' },
  { id: 'sela', label: 'Sela', hint: 'di tengah klip, gambar ditahan' },
  { id: 'penutup', label: 'Penutup', hint: 'sesudah klip selesai' },
];

let urut = 0;
const idBaru = () => `km${Date.now().toString(36)}${(urut += 1)}`;

export function komentarUntukRender(daftar) {
  return (daftar ?? [])
    .filter((k) => (k.teks || '').trim() || k.suara)
    .map((k) => ({
      posisi: k.posisi,
      ...(k.posisi === 'sela' ? { t: Number(k.t) || 0 } : {}),
      teks: (k.teks || '').trim(),
      suara: k.suara || '',
      tampil_teks: k.tampil_teks ?? !k.suara,
      mode: k.mode || 'bekukan',
    }));
}

function Rekam({ onSelesai, nonaktif }) {
  const [rekam, setRekam] = useState(false);
  const [sibuk, setSibuk] = useState(false);
  const [detik, setDetik] = useState(0);
  const [galat, setGalat] = useState('');
  const perekam = useRef(null);
  const jam = useRef(null);

  useEffect(() => () => {
    clearInterval(jam.current);
    perekam.current?.stream?.getTracks().forEach((t) => t.stop());
  }, []);

  const mulai = async () => {
    setGalat('');
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setGalat('Peramban ini tidak bisa merekam. Pakai Chrome, Edge, atau Firefox terbaru.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      const potongan = [];
      const mr = new MediaRecorder(stream);
      mr.ondataavailable = (e) => { if (e.data.size) potongan.push(e.data); };
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        clearInterval(jam.current);
        setRekam(false);
        const blob = new Blob(potongan, { type: mr.mimeType || 'audio/webm' });
        if (blob.size < 2000) { setGalat('Rekamannya kosong.'); return; }
        setSibuk(true);
        try {
          const fd = new FormData();
          const akhiran = (mr.mimeType || '').includes('ogg') ? 'ogg' : 'webm';
          fd.append('berkas', blob, `rekaman.${akhiran}`);
          onSelesai(await apiPost('/komentar/rekaman', fd));
        } catch (e) {
          setGalat(e.message || 'Rekaman gagal disimpan.');
        } finally { setSibuk(false); }
      };
      perekam.current = mr;
      mr.start();
      setDetik(0);
      setRekam(true);
      jam.current = setInterval(() => setDetik((n) => {
        // Batas satu menit, sama dengan batas server.
        if (n + 1 >= 60) mr.state === 'recording' && mr.stop();
        return n + 1;
      }), 1000);
    } catch (e) {
      setGalat(e?.name === 'NotAllowedError'
        ? 'Izin mikrofon ditolak. Izinkan mikrofon untuk halaman ini di peramban.'
        : 'Mikrofon tidak bisa dibuka.');
    }
  };

  const berhenti = () => perekam.current?.state === 'recording' && perekam.current.stop();

  return (
    <>
      {rekam ? (
        <button className="btn-secondary" onClick={berhenti}
                style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }}>
          <Square size={13} /> Berhenti ({detik} dtk)
        </button>
      ) : (
        <button className="btn-secondary" onClick={mulai} disabled={nonaktif || sibuk}>
          {sibuk ? <Loader2 size={13} className="animate-spin" /> : <Mic size={13} />}
          {sibuk ? 'Menyimpan…' : 'Rekam suara saya'}
        </button>
      )}
      {galat && <div style={{ fontSize: '.74rem', color: 'var(--danger)', width: '100%' }}>{galat}</div>}
    </>
  );
}

function KartuKomentar({ k, onUbah, onHapus, waktuSekarang, durasiKlip, suaraTts, onSeek }) {
  const [tts, setTts] = useState(false);
  const [galat, setGalat] = useState('');
  const pilih = POSISI.find((p) => p.id === k.posisi) || POSISI[0];

  const bacakan = async () => {
    setTts(true); setGalat('');
    try {
      const r = await apiPost('/komentar/tts', { teks: k.teks, suara: k.suara_tts || '' });
      onUbah({ suara: r.id, sintetis: true, durasi_suara: r.durasi, teks_suara: k.teks });
    } catch (e) {
      setGalat(e.message || 'TTS gagal.');
    } finally { setTts(false); }
  };

  // Suara TTS yang dibuat dari teks LAMA tidak lagi cocok dengan teksnya.
  const ttsUsang = k.suara && k.sintetis && k.teks_suara !== undefined
    && (k.teks_suara || '').trim() !== (k.teks || '').trim();

  return (
    <div style={{ border: '1px solid var(--line)', borderRadius: 'var(--radius-md)',
                  padding: '10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
        <select className="field" value={k.posisi} style={{ width: 'auto', padding: '4px 6px' }}
                onChange={(e) => onUbah({
                  posisi: e.target.value,
                  ...(e.target.value === 'sela' && k.t == null
                    ? { t: Math.round(waktuSekarang * 10) / 10 } : {}),
                })}>
          {POSISI.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
        </select>
        <span style={{ fontSize: '.72rem', color: 'var(--ink-3)' }}>{pilih.hint}</span>
        <button className="btn-secondary" onClick={onHapus} title="Hapus komentar ini"
                style={{ marginLeft: 'auto', padding: '3px 7px' }}>
          <Trash2 size={13} />
        </button>
      </div>

      {k.posisi === 'sela' && (
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center', fontSize: '.78rem' }}>
          <span>Di detik</span>
          <input className="field" type="number" min={0} max={durasiKlip} step={0.1}
                 value={k.t ?? 0} style={{ width: '80px', padding: '3px 6px' }}
                 onChange={(e) => onUbah({ t: Math.max(0, Math.min(durasiKlip, Number(e.target.value) || 0)) })} />
          <button className="btn-secondary" style={{ padding: '3px 8px', fontSize: '.74rem' }}
                  title="Pakai posisi pemutar sekarang"
                  onClick={() => onUbah({ t: Math.round(waktuSekarang * 10) / 10 })}>
            <Crosshair size={12} /> {formatTime(waktuSekarang)}
          </button>
          <button className="btn-secondary" style={{ padding: '3px 8px', fontSize: '.74rem' }}
                  onClick={() => onSeek?.(Number(k.t) || 0)}>Lihat</button>
        </div>
      )}

      <textarea className="field" rows={3} maxLength={600} value={k.teks || ''}
                placeholder="Pendapat Anda tentang klip ini, dengan kata-kata sendiri."
                onChange={(e) => onUbah({ teks: e.target.value })}
                style={{ resize: 'vertical', fontFamily: 'inherit', lineHeight: 1.5 }} />

      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
        <Rekam onSelesai={(r) => onUbah({ suara: r.id, sintetis: false, durasi_suara: r.durasi,
                                          teks_suara: undefined })} />
        <select className="field" value={k.suara_tts || ''} title="Suara TTS"
                style={{ width: 'auto', padding: '4px 6px', fontSize: '.76rem' }}
                onChange={(e) => onUbah({ suara_tts: e.target.value })}>
          <option value="">Suara TTS bawaan</option>
          {suaraTts.filter((v) => v.ready).map((v) => (
            <option key={v.id} value={v.id}>{v.label}</option>
          ))}
        </select>
        <button className="btn-secondary" onClick={bacakan}
                disabled={tts || !(k.teks || '').trim()}
                title="Dibacakan suara buatan. Klipnya otomatis diberi label konten sintetis saat diunggah ke YouTube.">
          {tts ? <Loader2 size={13} className="animate-spin" /> : <Volume2 size={13} />}
          Bacakan (TTS)
        </button>
      </div>
      {galat && <div style={{ fontSize: '.74rem', color: 'var(--danger)' }}>{galat}</div>}

      {k.suara && (
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
          <audio controls src={`/api/komentar/suara/${k.suara}`} style={{ height: '30px', maxWidth: '100%' }} />
          <span style={{ fontSize: '.72rem', color: 'var(--ink-3)' }}>
            {k.sintetis ? 'TTS, diberi label sintetis' : 'Suara Anda'}
            {k.durasi_suara ? ` · ${Number(k.durasi_suara).toFixed(1)} dtk` : ''}
          </span>
          <button className="btn-secondary" style={{ padding: '3px 7px', fontSize: '.72rem' }}
                  onClick={() => onUbah({ suara: '', sintetis: false, durasi_suara: null })}>
            Lepas suara
          </button>
          {ttsUsang && (
            <span style={{ fontSize: '.72rem', color: 'var(--reh)', width: '100%' }}>
              Teksnya sudah diubah sesudah dibacakan. Tekan &quot;Bacakan&quot; lagi supaya suaranya sama.
            </span>
          )}
        </div>
      )}

      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', fontSize: '.78rem' }}>
        <label className="studio-check" title="Teks komentar tampil di tengah layar selama komentar berlangsung.">
          <input type="checkbox" checked={k.tampil_teks ?? !k.suara}
                 onChange={(e) => onUbah({ tampil_teks: e.target.checked })} />
          Tampilkan sebagai kartu teks
        </label>
        <label className="studio-check"
               title="Bekukan: gambar ditahan selama komentar, klip tidak tertimpa. Timpa: klip tetap jalan, suaranya dikecilkan.">
          <select className="field" value={k.mode || 'bekukan'}
                  style={{ width: 'auto', padding: '2px 6px', fontSize: '.76rem' }}
                  onChange={(e) => onUbah({ mode: e.target.value })}>
            <option value="bekukan">Bekukan gambar</option>
            <option value="timpa">Timpa, klip tetap jalan</option>
          </select>
        </label>
      </div>
    </div>
  );
}

export default function KomentarPanel({
  clip, videoId, waktuSekarang = 0, durasiKlip = 0, onChange, onSeek,
}) {
  const [draf, setDraf] = useState(null);
  const [sibuk, setSibuk] = useState(false);
  const [galat, setGalat] = useState('');
  const [suaraTts, setSuaraTts] = useState([]);
  const daftar = clip?.komentar ?? [];

  useEffect(() => {
    let batal = false;
    apiGet('/komentar/suara-tts').then((r) => { if (!batal) setSuaraTts(r.suara || []); })
      .catch(() => {});
    return () => { batal = true; };
  }, []);
  useEffect(() => { setDraf(null); setGalat(''); }, [clip?.clip_id]);

  if (!clip) return <p style={{ fontSize: '.85rem' }}>Pilih klip dulu.</p>;

  const ubah = (id, patch) => onChange(daftar.map((k) => (k.id === id ? { ...k, ...patch } : k)));
  const hapus = (id) => onChange(daftar.filter((k) => k.id !== id));
  const tambah = (posisi = 'pembuka', isi = {}) => onChange([...daftar, {
    id: idBaru(), posisi, teks: '', suara: '', mode: 'bekukan',
    ...(posisi === 'sela' ? { t: Math.round(waktuSekarang * 10) / 10 } : {}), ...isi,
  }]);

  const susunDraf = async (segarkan = false) => {
    if (daftar.some((k) => (k.teks || '').trim())
        && !window.confirm('Ganti komentar yang sudah ada dengan draf AI?')) return;
    setSibuk(true); setGalat('');
    try {
      const r = await apiPost('/clip-komentar', {
        video_id: videoId,
        title: clip.title || '',
        konteks: clip.konteks || '',
        duration: durasiKlip,
        subtitles: (clip.subtitles || []).slice(0, 600).map((l) => ({
          start: l.start, end: l.end, text: l.text || '',
        })),
        segarkan,
      }, { timeout: 150000 });
      setDraf(r);
      const baru = [];
      if (r.pembuka) baru.push({ id: idBaru(), posisi: 'pembuka', teks: r.pembuka, suara: '', mode: 'bekukan' });
      if (r.sela?.teks) baru.push({ id: idBaru(), posisi: 'sela', t: r.sela.detik, teks: r.sela.teks, suara: '', mode: 'bekukan' });
      if (r.penutup) baru.push({ id: idBaru(), posisi: 'penutup', teks: r.penutup, suara: '', mode: 'bekukan' });
      if (baru.length) onChange(baru);
    } catch (e) {
      setGalat(e.message || 'Draf gagal disusun.');
    } finally { setSibuk(false); }
  };

  const adaSuara = daftar.some((k) => k.suara);
  const tambahanDetik = daftar.reduce((n, k) => n + (k.mode === 'timpa' ? 0
    : k.suara ? (Number(k.durasi_suara) || 0) + 0.3
      : (k.teks || '').trim() && (k.tampil_teks ?? true)
        ? Math.max(2.5, Math.min(8, (k.teks || '').length / 14 + 1)) : 0), 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <p style={{ fontSize: '.78rem', lineHeight: 1.55, color: 'var(--ink-2)', margin: 0 }}>
        Pendapat Anda tentang klip ini. Inilah yang membedakan klip Anda dari potongan ulang
        biasa di mata YouTube. Draf AI hanya titik awal: ubah dengan kata-kata Anda sendiri,
        lalu rekam suara Anda.
      </p>

      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
        <button className="btn-secondary" onClick={() => susunDraf(false)} disabled={sibuk}>
          {sibuk ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
          {sibuk ? 'Menyusun draf…' : 'Susun draf AI'}
        </button>
        {draf && (
          <button className="btn-secondary" onClick={() => susunDraf(true)} disabled={sibuk}>
            Tulis ulang
          </button>
        )}
        <button className="btn-secondary" onClick={() => tambah(daftar.length ? 'sela' : 'pembuka')}>
          <Plus size={13} /> Tambah sendiri
        </button>
      </div>
      {galat && <div style={{ fontSize: '.76rem', color: 'var(--danger)' }}>{galat}</div>}
      {(draf?.catatan || []).map((c) => (
        <div key={c} style={{ fontSize: '.74rem', color: 'var(--ink-3)', display: 'flex', gap: '6px' }}>
          <AlertTriangle size={12} style={{ flex: 'none', marginTop: 2 }} /> {c}
        </div>
      ))}

      {daftar.map((k) => (
        <KartuKomentar key={k.id} k={k} waktuSekarang={waktuSekarang} durasiKlip={durasiKlip}
                       suaraTts={suaraTts} onSeek={onSeek}
                       onUbah={(p) => ubah(k.id, p)} onHapus={() => hapus(k.id)} />
      ))}

      {daftar.length > 0 && (
        <p style={{ fontSize: '.74rem', color: 'var(--ink-3)', margin: 0 }}>
          Klip jadi bertambah sekitar {tambahanDetik.toFixed(1)} detik
          {!adaSuara ? ', dan komentarnya tampil sebagai kartu teks tanpa suara' : ''}.
        </p>
      )}
    </div>
  );
}
