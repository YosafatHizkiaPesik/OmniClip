import React, { useEffect, useRef, useState } from 'react';
import {
  Copy, Check, Plus, X, Sparkles, Volume2, Loader2, Download, AlertTriangle,
} from 'lucide-react';
import { apiGet, apiPost } from '../../lib/api';
import { CARD_VARIANTS } from './cardStyles';

const TITLE_MAX = 100;

export const DEFAULT_CARD = {
  enabled: false, text: '', mode: 'freeze', seconds: 3,
  voice: true, voice_id: 'piper-news', rate: 1.05, size: 104,
  // Letak dan lebar judul, dalam persen kanvas — diseret langsung di atas
  // pratinjau, bukan diketik di sini. Angka default menaruhnya di tengah.
  pos_x: 50, pos_y: 50, box_w: 84, variant: 'garis',
};

const MODES = [
  { id: 'freeze', label: 'Foto diam',
    hint: 'Satu bingkai klip dibekukan jadi latar, judul di atasnya, baru klipnya mulai. Klipnya utuh, hanya jadi lebih panjang.' },
  { id: 'zoom', label: 'Foto merayap membesar',
    hint: 'Sama seperti foto diam, tapi gambarnya membesar pelan selama judul dibaca — supaya tidak terlihat macet.' },
  { id: 'overlay', label: 'Klip langsung jalan',
    hint: 'Judul menutupi sebagian klip yang sudah berjalan lalu hilang. Tidak ada waktu yang terbuang.' },
];

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
export default function TitlePanel({ clip, onChange, onRetitle = null, retitling = false }) {
  const [copied, setCopied] = useState(false);
  const [draft, setDraft] = useState('');
  // Keadaan suara pembaca: ada/tidak, sedang dipasang, sedang dibacakan.
  const [voiceReady, setVoiceReady] = useState(null);
  const [voices, setVoices] = useState([]);
  const [busy, setBusy] = useState(null);
  const [heard, setHeard] = useState(null);
  const [voiceError, setVoiceError] = useState(null);
  const audioRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    apiGet('/title-voice/status')
      .then((r) => {
        if (cancelled) return;
        setVoiceReady(!!r.available);
        setVoices(r.voices || []);
      })
      .catch(() => { if (!cancelled) setVoiceReady(false); });
    return () => { cancelled = true; };
  }, []);

  if (!clip) {
    return (
      <p style={{ fontSize: '.8rem', color: 'var(--ink-3)', margin: 0 }}>
        Pilih satu huruf latihan dulu.
      </p>
    );
  }

  const title = clip.title ?? '';
  const tags = clip.hashtags ?? [];
  // Kartu judul disimpan PADA KLIPNYA, sama seperti tanda arah bingkai: tiap
  // klip punya judul sendiri, jadi setelannya pun harus ikut klipnya.
  const card = { ...DEFAULT_CARD, ...clip.title_card };
  const patchCard = (patch) => onChange({ title_card: { ...card, ...patch } });
  // Teks kartu mengikuti judul klip kecuali pengguna menuliskan yang lain.
  const cardText = (card.text || '').trim() || title;

  /** Membacakan judulnya sekarang, supaya tempo dan nadanya bisa dinilai. */
  const dengar = async () => {
    if (!cardText.trim()) return;
    setBusy('suara');
    setVoiceError(null);
    try {
      const r = await apiPost('/title-voice', {
        text: cardText, rate: card.rate, voice_id: card.voice_id,
      });
      setHeard(r);
      // Panjang kartu yang SEBENARNYA disimpan ke klipnya, supaya pratinjau
      // menahan layar selama itu — bukan selama angka bawaan.
      patchCard({
        card_seconds: r.card_seconds,
        // Disimpan bersama TANDA PENGENALNYA. Tanpa tanda itu, mengganti judul
        // lalu menekan putar akan memperdengarkan bacaan judul yang lama —
        // berkasnya masih ada, dan tidak ada yang tahu ia sudah kedaluwarsa.
        voice_url: r.url,
        voice_sig: `${cardText}|${card.voice_id || ''}|${card.rate || 1}`,
      });
      const el = audioRef.current;
      if (el) {
        el.src = r.url;
        el.currentTime = 0;
        // Firefox menolak memutar suara yang dimulai SESUDAH `await`: izin dari
        // klik pengguna sudah kedaluwarsa saat berkasnya selesai dibuat. Dulu
        // penolakan itu ditelan diam-diam, jadi tombolnya berhenti berputar
        // tanpa satu pun suara terdengar — persis "kenapa cuma loading".
        // Sekarang pemutarnya tetap tergambar, jadi selalu ada tombol putar.
        try {
          await el.play();
        } catch {
          setVoiceError('Peramban menahan pemutaran otomatis — tekan tombol putar di bawah.');
        }
      }
    } catch (e) {
      setVoiceError(e.message || 'Gagal membacakan judul.');
    } finally {
      setBusy(null);
    }
  };

  const pasangSuara = async () => {
    setBusy('pasang');
    setVoiceError(null);
    try {
      await apiPost('/title-voice/install', {});
      // Unduhan 63 MB; ditanyakan berkala sampai siap.
      for (let i = 0; i < 120; i += 1) {
        // eslint-disable-next-line no-await-in-loop
        await new Promise((r) => { setTimeout(r, 2500); });
        // eslint-disable-next-line no-await-in-loop
        const st = await apiGet('/title-voice/status');
        if (st.available) { setVoiceReady(true); break; }
      }
    } catch (e) {
      setVoiceError(e.message || 'Gagal memasang suara pembaca.');
    } finally {
      setBusy(null);
    }
  };

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
        {(clip.title_source === 'gemini' || clip.source === 'gemini')
          ? 'Ditulis oleh Gemini dari isi klip ini.'
          : 'Diambil dari kalimat pembuka klip ini sendiri — kutipan nyata, '
            + 'bukan judul karangan. Akurat, tapi jarang memancing.'}
        {' '}Judul ini jadi nama berkas hasil render, dan mengisi sendiri
        formulir saat klipnya diunggah.
      </p>

      {/* Klip yang tidak terpilih Gemini saat analisis keluar dengan judul
          heuristik: sebuah kalimat dari klipnya sendiri. Benar, dan datar.
          Tombol ini membetulkannya tanpa menganalisis ulang apa pun. */}
      {onRetitle && (
        <button className="btn-secondary" onClick={onRetitle} disabled={retitling}
                style={{ justifyContent: 'center' }}>
          {retitling ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
          {retitling ? 'Gemini sedang menulis…' : 'Tulis ulang judul & tagar dengan Gemini'}
        </button>
      )}

      {/* ── Kartu judul di awal klip ──────────────────────────────────────
          Judul yang hanya tertulis kehilangan separuh gunanya di feed yang
          diputar sambil lalu. Kartu di awal — judul besar, dibacakan — memberi
          penonton alasan untuk berhenti sebelum sempat menggulir pergi. */}
      <div style={{ borderTop: '1px solid var(--rule-2)', paddingTop: '12px' }}>
        <label style={{
          display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer',
        }}>
          <input type="checkbox" checked={card.enabled}
                 onChange={(e) => patchCard({ enabled: e.target.checked })}
                 style={{ width: '15px', height: '15px' }} />
          <span className="mark" style={{ color: 'var(--ink)' }}>
            Tampilkan judul di awal klip
          </span>
        </label>
        <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.55, margin: '6px 0 0' }}>
          Judulnya disiapkan di sini dan baru digabungkan dengan klipnya saat
          dirender — jadi mematikan pilihan ini mengembalikan klipnya seperti
          semula, tanpa perlu mengubah apa pun yang lain.
        </p>

        {card.enabled && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '11px' }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
              <span className="mark" style={{ color: 'var(--ink)' }}>Teks kartu</span>
              <textarea className="field" rows={2} value={card.text}
                        placeholder={title || 'ikut judul klip di atas'}
                        onChange={(e) => patchCard({ text: e.target.value })}
                        style={{ resize: 'vertical', fontFamily: 'inherit', lineHeight: 1.5 }} />
            </label>
            <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', margin: 0 }}>
              Dikosongkan berarti memakai judul klip di atas. Diisi berarti kartunya
              boleh berbeda dari judul unggahan — yang sering perlu, karena judul
              yang dibaca di layar dan judul yang dicari orang bukan hal yang sama.
            </p>

            <div>
              <div className="mark" style={{ color: 'var(--ink)', marginBottom: '6px' }}>
                Latar selama judul tampil
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {MODES.map((m) => (
                  <button key={m.id} onClick={() => patchCard({ mode: m.id })}
                          className={`choice${card.mode === m.id ? ' is-on' : ''}`}>
                    <div className="choice-t">{m.label}</div>
                    <div className="choice-h">{m.hint}</div>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div className="mark" style={{ color: 'var(--ink)', marginBottom: '6px' }}>
                Gaya judul
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {CARD_VARIANTS.map((v) => (
                  <button key={v.id} onClick={() => patchCard({ variant: v.id })}
                          className={`choice${(card.variant || 'garis') === v.id ? ' is-on' : ''}`}>
                    <div className="choice-t">{v.label}</div>
                    <div className="choice-h">{v.note}</div>
                  </button>
                ))}
              </div>
              <p style={{
                fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.6,
                margin: '8px 0 0',
              }}>
                Letak dan ukurannya diseret langsung di atas pratinjau: seret
                judulnya untuk memindahkan, bulatan di pojok kanan-bawah untuk
                melebarkan kotaknya sekaligus membesarkan hurufnya.
              </p>
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
              <input type="checkbox" checked={card.voice}
                     onChange={(e) => patchCard({ voice: e.target.checked })}
                     style={{ width: '15px', height: '15px' }} />
              <span style={{ fontSize: '.82rem' }}>Bacakan judulnya</span>
            </label>

            {card.voice ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {voiceReady === false ? (
                  <>
                    <div style={{
                      display: 'flex', gap: '8px', alignItems: 'flex-start',
                      padding: '9px 11px', borderRadius: 'var(--r-sm)',
                      border: '1px solid var(--rule-2)', background: 'var(--plate-3)',
                    }}>
                      <AlertTriangle size={14} style={{ flex: 'none', marginTop: '2px', color: 'var(--warn)' }} />
                      <span style={{ fontSize: '.75rem', color: 'var(--ink-2)', lineHeight: 1.55 }}>
                        Suara pembaca belum ada di mesin ini. Berkasnya 63 MB, diunduh
                        sekali lalu bekerja tanpa internet — judulnya tidak pernah
                        dikirim ke layanan mana pun.
                      </span>
                    </div>
                    <button className="btn-secondary" onClick={pasangSuara} disabled={busy === 'pasang'}
                            style={{ justifyContent: 'center' }}>
                      {busy === 'pasang'
                        ? <Loader2 size={14} className="animate-spin" />
                        : <Download size={14} />}
                      {busy === 'pasang' ? 'Mengunduh suara…' : 'Pasang suara pembaca'}
                    </button>
                  </>
                ) : (
                  <>
                    <div>
                      <div className="mark" style={{ color: 'var(--ink)', marginBottom: '6px' }}>
                        Suara pembaca
                      </div>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                        {voices.filter((v) => v.ready).map((v) => (
                          <button key={v.id}
                                  className={`chip${card.voice_id === v.id ? ' is-on' : ''}`}
                                  title={v.note}
                                  onClick={() => { setHeard(null); patchCard({ voice_id: v.id }); }}>
                            {v.label}
                          </button>
                        ))}
                      </div>
                      {/* Pertukarannya disebut apa adanya. Suara Microsoft itu
                          yang terdengar "benar" bagi penonton, tapi memakainya
                          berarti judul klip dikirim keluar dari mesin ini. */}
                      <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.55, margin: '6px 0 0' }}>
                        {voices.find((v) => v.id === card.voice_id)?.online
                          ? 'Dibuat di server Microsoft — judul klip dikirim ke sana untuk dibacakan, dan butuh internet. Ini suara yang dipakai kebanyakan alat pembuat klip.'
                          : 'Dibuat di komputer ini. Judul tidak dikirim ke mana pun dan tetap bekerja tanpa internet.'}
                      </p>
                    </div>
                    <label style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                      <span style={{ fontSize: '.76rem', color: 'var(--ink-2)' }}>
                        Tempo bacaan · {card.rate.toFixed(2)}×
                      </span>
                      <input type="range" min="0.7" max="1.4" step="0.05" value={card.rate}
                             onChange={(e) => { setHeard(null); patchCard({ rate: Number(e.target.value) }); }} />
                    </label>
                    <button className="btn-secondary" onClick={dengar}
                            disabled={busy === 'suara' || !cardText.trim()}
                            style={{ justifyContent: 'center' }}>
                      {busy === 'suara'
                        ? <Loader2 size={14} className="animate-spin" />
                        : <Volume2 size={14} />}
                      Dengarkan
                    </button>
                    {heard && (
                      <p style={{ fontSize: '.74rem', color: 'var(--ink-2)', margin: 0 }}>
                        Bacaannya {heard.seconds.toFixed(1)} detik, jadi kartunya
                        menahan layar <b>{heard.card_seconds.toFixed(1)} detik</b>.
                        {' '}Panjang kartu memang mengikuti bacaan — kartu yang
                        berganti sebelum kalimatnya selesai terdengar seperti kesalahan.
                      </p>
                    )}
                  </>
                )}
                {/* Pemutarnya TERLIHAT, bukan disembunyikan: pemutaran
                    otomatis sering ditahan peramban, dan tanpa tombol putar
                    yang kelihatan tidak ada jalan lain mendengarnya.
                    eslint-disable-next-line jsx-a11y/media-has-caption */}
                <audio ref={audioRef} controls
                       style={{ width: '100%', height: '34px', display: heard ? 'block' : 'none' }} />
              </div>
            ) : (
              <label style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                <span style={{ fontSize: '.76rem', color: 'var(--ink-2)' }}>
                  Kartu menahan layar · {card.seconds.toFixed(1)} detik
                </span>
                <input type="range" min="1.2" max="8" step="0.1" value={card.seconds}
                       onChange={(e) => patchCard({ seconds: Number(e.target.value) })} />
              </label>
            )}

            {voiceError && (
              <p style={{ fontSize: '.75rem', color: 'var(--danger)', margin: 0 }}>{voiceError}</p>
            )}
          </div>
        )}
      </div>

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
