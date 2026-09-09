import React, { useState } from 'react';
import { Copy, Check, Plus, X, Sparkles } from 'lucide-react';

const TITLE_MAX = 100;

/**
 * Judul dan tagar untuk klip yang akan diunggah.
 *
 * Judulnya bukan headline karangan: bila Gemini tidak ikut, ia adalah kalimat
 * pembuka klip itu sendiri. Tagar juga diturunkan dari kata yang benar-benar
 * diucapkan di klipnya, bukan dari daftar tagar populer — tagar yang tidak
 * nyambung dengan isinya tidak membuat video naik, ia membuatnya terlihat
 * seperti spam.
 *
 * Keduanya bisa disunting, dan yang disunting itulah yang dipakai: jadi nama
 * berkas hasil render, dan mengisi sendiri formulir unggah.
 */
export default function TitlePanel({ clip, onChange }) {
  const [copied, setCopied] = useState(false);
  const [draft, setDraft] = useState('');

  if (!clip) {
    return (
      <p style={{ fontSize: '.8rem', color: 'var(--ink-3)', margin: 0 }}>
        Pilih satu huruf latihan dulu.
      </p>
    );
  }

  const title = clip.title ?? '';
  const tags = clip.hashtags ?? [];

  const addTag = () => {
    const t = draft.trim().replace(/^#+/, '').replace(/[^\wÀ-ɏ]/g, '');
    if (!t || tags.includes(`#${t}`)) { setDraft(''); return; }
    onChange({ hashtags: [...tags, `#${t}`].slice(0, 12) });
    setDraft('');
  };

  const copyAll = async () => {
    const text = [title, tags.join(' ')].filter(Boolean).join('\n\n');
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // Papan klip bisa ditolak browser tanpa interaksi langsung; tidak ada
      // yang perlu diperbaiki pengguna, jadi tidak ada pesan galat.
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <label style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
        <span className="mark" style={{ color: 'var(--ink)' }}>
          Judul klip{' '}
          <span style={{ color: title.length > TITLE_MAX ? 'var(--danger)' : 'var(--ink-3)' }}>
            ({title.length}/{TITLE_MAX})
          </span>
        </span>
        <textarea className="field" rows={2} value={title} maxLength={TITLE_MAX}
                  onChange={(e) => onChange({ title: e.target.value })}
                  style={{ resize: 'vertical', fontFamily: 'inherit', lineHeight: 1.5 }} />
      </label>
      <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.55, margin: 0 }}>
        {clip.source === 'gemini'
          ? 'Ditulis ulang oleh Gemini dari isi klip ini.'
          : 'Diambil dari kalimat pembuka klip ini sendiri — kutipan nyata, '
            + 'bukan judul karangan. Silakan ubah.'}
        {' '}Judul ini jadi nama berkas hasil render, dan mengisi sendiri
        formulir saat klipnya diunggah.
      </p>

      <div>
        <div className="mark" style={{ color: 'var(--ink)', marginBottom: '6px' }}>
          Tagar ({tags.length})
        </div>
        <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginBottom: '7px' }}>
          {tags.map((t) => (
            <span key={t} className="chip" style={{ display: 'inline-flex', gap: '5px', alignItems: 'center' }}>
              {t}
              <X size={11} style={{ cursor: 'pointer' }}
                 onClick={() => onChange({ hashtags: tags.filter((x) => x !== t) })} />
            </span>
          ))}
          {tags.length === 0 && (
            <span style={{ fontSize: '.75rem', color: 'var(--ink-3)' }}>Belum ada tagar.</span>
          )}
        </div>
        <div style={{ display: 'flex', gap: '6px' }}>
          <input className="field" value={draft} placeholder="tambah tagar…"
                 onChange={(e) => setDraft(e.target.value)}
                 onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTag(); } }}
                 style={{ flex: 1, minWidth: 0, padding: '6px 9px', fontSize: '.8rem' }} />
          <button className="btn-secondary" onClick={addTag} disabled={!draft.trim()}
                  style={{ fontSize: '.76rem', padding: '6px 10px' }}>
            <Plus size={12} /> Tambah
          </button>
        </div>
        <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.55, margin: '8px 0 0' }}>
          Tagar di atas diambil dari kata yang benar-benar diucapkan di klip ini
          dan dari judul video sumbernya. Tagar yang tidak nyambung dengan isinya
          tidak membuat video naik — justru sebaliknya.
        </p>
      </div>

      <button className="btn-secondary" onClick={copyAll}
              disabled={!title && tags.length === 0}
              style={{ justifyContent: 'center' }}>
        {copied ? <Check size={14} style={{ color: 'var(--entry)' }} /> : <Copy size={14} />}
        {copied ? 'Tersalin' : 'Salin judul + tagar'}
      </button>

      {clip.ai_reason && (
        <div style={{
          display: 'flex', gap: '8px', alignItems: 'flex-start',
          padding: '9px 11px', borderRadius: 'var(--r-sm)',
          border: '1px solid var(--rule-2)', background: 'var(--plate-3)',
        }}>
          <Sparkles size={14} style={{ flex: 'none', marginTop: '2px', color: 'var(--cue)' }} />
          <span style={{ fontSize: '.75rem', color: 'var(--ink-2)', lineHeight: 1.55 }}>
            {clip.ai_reason}
          </span>
        </div>
      )}
    </div>
  );
}
