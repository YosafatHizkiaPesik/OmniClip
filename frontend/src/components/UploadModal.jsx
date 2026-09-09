import React, { useEffect, useMemo, useState } from 'react';
import {
  X, UploadCloud, Loader2, CheckCircle2, AlertTriangle, ExternalLink,
} from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';

const TARGETS = [
  { id: 'drive', label: 'Google Drive', hint: 'Masuk ke folder OmniClip di Drive Anda.' },
  { id: 'youtube', label: 'YouTube', hint: 'Naik sebagai video di kanal Anda sendiri.' },
];

const PRIVACY = [
  { id: 'private', label: 'Privat', hint: 'Hanya Anda yang bisa melihatnya.' },
  { id: 'unlisted', label: 'Tidak publik', hint: 'Bisa dilihat siapa pun yang punya tautannya.' },
  { id: 'public', label: 'Publik', hint: 'Muncul di kanal dan bisa ditemukan lewat pencarian.' },
];

/**
 * Mengunggah SATU klip.
 *
 * Sengaja satu, dan sengaja tanpa "unggah semua". Antarmuka yang menerima
 * daftar akan membuat mengirim selusin video ke satu kanal beruntun terasa
 * seperti satu tombol yang wajar — padahal justru itu pola yang membuat sebuah
 * kanal ditandai YouTube. Antreannya di server pun hanya selebar satu.
 */
export default function UploadModal({ clip, onClose, onDone }) {
  const meta = clip.metadata || {};
  const defaultTitle = useMemo(
    () => (meta.title || meta.hook_text || clip.file_name.replace(/\.mp4$/i, ''))
      .slice(0, 100),
    [meta.title, meta.hook_text, clip.file_name],
  );

  const [status, setStatus] = useState(null);
  const [target, setTarget] = useState('drive');
  const [title, setTitle] = useState(defaultTitle);
  const [description, setDescription] = useState('');
  const [privacy, setPrivacy] = useState('private');
  const [phase, setPhase] = useState('form');   // form | sending | done | failed
  const [message, setMessage] = useState('');
  const [result, setResult] = useState(null);

  useEffect(() => {
    apiGet('/uploads/google/status').then(setStatus).catch(() => setStatus(null));
  }, []);

  const submit = async () => {
    setPhase('sending');
    setMessage('Mengantre…');
    try {
      const { job_id: jobId } = await apiPost('/uploads', {
        clip_name: clip.file_name,
        target,
        title: title.trim(),
        description,
        privacy,
      });
      for (;;) {
        // eslint-disable-next-line no-await-in-loop
        const job = await apiGet(`/jobs/${jobId}`);
        // Pesannya datang DARI SERVER. Bilah kemajuan yang teksnya dikarang
        // browser dari sebuah angka adalah teater, dan pernah jadi teater di
        // aplikasi ini.
        if (job.message) setMessage(job.message);
        if (job.status === 'done') {
          setResult(job.result);
          setPhase('done');
          onDone?.();
          return;
        }
        if (job.status === 'failed' || job.status === 'cancelled') {
          setMessage(job.error || 'Unggahan gagal.');
          setPhase('failed');
          return;
        }
        // eslint-disable-next-line no-await-in-loop
        await new Promise((r) => setTimeout(r, 1200));
      }
    } catch (err) {
      setMessage(err.message);
      setPhase('failed');
    }
  };

  const connected = status?.connected;

  return (
    <div className="modal-overlay" onClick={phase === 'sending' ? undefined : onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}
           style={{ maxWidth: '520px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
          <UploadCloud size={18} style={{ color: 'var(--reh)' }} />
          <h2 style={{ fontSize: '1.05rem', fontWeight: 800, flex: 1 }}>Unggah klip</h2>
          {phase !== 'sending' && (
            <button onClick={onClose} aria-label="Tutup" className="rail-toggle"
                    style={{ color: 'var(--ink-2)', borderColor: 'var(--rule-2)' }}>
              <X size={15} />
            </button>
          )}
        </div>

        <div className="tc" style={{ fontSize: '.76rem', color: 'var(--ink-3)', marginBottom: '12px' }}>
          {clip.file_name}
        </div>

        {status && !connected ? (
          <div style={{ fontSize: '.85rem', lineHeight: 1.6, color: 'var(--ink-2)' }}>
            Akun Google belum tersambung. Buka <b>Pengaturan</b>, pasang berkas
            OAuth client dari Google Cloud Console, lalu sambungkan akun Anda.
            Sesudah itu tombol ini akan bekerja.
          </div>
        ) : phase === 'done' ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', gap: '9px', alignItems: 'center', fontSize: '.9rem' }}>
              <CheckCircle2 size={18} style={{ color: 'var(--entry)' }} />
              Terunggah ke {target === 'youtube' ? 'YouTube' : 'Google Drive'}.
            </div>
            <a href={result?.remote_url} target="_blank" rel="noreferrer"
               className="btn-secondary" style={{ textDecoration: 'none', justifyContent: 'center' }}>
              <ExternalLink size={14} /> Buka hasilnya
            </a>
            <button className="btn-primary" onClick={onClose}
                    style={{ justifyContent: 'center' }}>Selesai</button>
          </div>
        ) : phase === 'sending' ? (
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', fontSize: '.88rem',
                        padding: '14px 0' }}>
            <Loader2 size={18} className="animate-spin" style={{ color: 'var(--reh)' }} />
            {message}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {phase === 'failed' && (
              <div style={{
                display: 'flex', gap: '9px', fontSize: '.83rem', lineHeight: 1.55,
                padding: '10px 12px', borderRadius: 'var(--r-sm)',
                border: '1px solid var(--rule-2)', borderLeft: '3px solid var(--danger)',
                background: 'var(--plate-3)',
              }}>
                <AlertTriangle size={15} style={{ color: 'var(--danger)', flex: 'none', marginTop: '2px' }} />
                <span>{message}</span>
              </div>
            )}

            <div>
              <div className="mark" style={{ color: 'var(--ink)', marginBottom: '6px' }}>Tujuan</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {TARGETS.map((t) => (
                  <button key={t.id} onClick={() => setTarget(t.id)}
                          className={`choice${target === t.id ? ' is-on' : ''}`}>
                    <div className="choice-t">{t.label}</div>
                    <div className="choice-h">{t.hint}</div>
                  </button>
                ))}
              </div>
            </div>

            <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span className="mark" style={{ color: 'var(--ink)' }}>
                Judul <span style={{ color: 'var(--ink-3)' }}>({title.length}/100)</span>
              </span>
              <input className="field" value={title} maxLength={100}
                     onChange={(e) => setTitle(e.target.value)} />
            </label>

            {target === 'youtube' && (
              <>
                <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <span className="mark" style={{ color: 'var(--ink)' }}>Deskripsi</span>
                  <textarea className="field" rows={3} value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            style={{ resize: 'vertical', fontFamily: 'inherit' }} />
                </label>

                <div>
                  <div className="mark" style={{ color: 'var(--ink)', marginBottom: '6px' }}>
                    Siapa yang boleh melihat
                  </div>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {PRIVACY.map((p) => (
                      <button key={p.id} title={p.hint}
                              className={`chip${privacy === p.id ? ' is-on' : ''}`}
                              onClick={() => setPrivacy(p.id)}>
                        {p.label}
                      </button>
                    ))}
                  </div>
                  <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.5, margin: '8px 0 0' }}>
                    Bawaannya privat. Video yang sudah naik bisa diubah jadi publik
                    kapan saja dari YouTube Studio — sebaliknya tidak semudah itu.
                    {status?.gap_seconds > 0 && (
                      <> Sistem memberi jeda {status.gap_seconds} detik antar
                      unggahan YouTube dan mengirimkannya satu per satu.</>
                    )}
                  </p>
                </div>
              </>
            )}

            <button className="btn-primary" onClick={submit}
                    disabled={!title.trim() || !status}
                    style={{ justifyContent: 'center', marginTop: '2px' }}>
              <UploadCloud size={15} />
              Unggah ke {target === 'youtube' ? 'YouTube' : 'Drive'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
