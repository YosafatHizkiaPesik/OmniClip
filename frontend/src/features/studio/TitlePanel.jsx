import React, { useEffect, useRef, useState } from 'react';
import {
  Copy, Check, Plus, X, Sparkles, Volume2, Loader2, Download, AlertTriangle,
} from 'lucide-react';
import { apiGet, apiPost } from '../../lib/api';
import { CARD_VARIANTS } from './cardStyles';
import {
  DEFAULT_JUDUL_VIDEO, GaleriTema, iniTema, useDaftarTema,
} from './JudulTema';
import { useT } from '../../lib/i18n';

const TITLE_MAX = 100;

export const DEFAULT_CARD = {
  enabled: false, text: '', mode: 'freeze', seconds: 3,
  voice: true, voice_id: 'piper-news', rate: 1.05, size: 104,
  // Letak dan lebar judul, dalam persen kanvas — diseret langsung di atas
  // pratinjau, bukan diketik di sini. Angka default menaruhnya di tengah.
  pos_x: 50, pos_y: 50, box_w: 84, variant: 'garis',
};

const MODES = [
  { id: 'freeze', label: 'kartu_mode.freeze', hint: 'kartu_mode.freeze_ket' },
  { id: 'zoom', label: 'kartu_mode.zoom', hint: 'kartu_mode.zoom_ket' },
  { id: 'overlay', label: 'kartu_mode.overlay', hint: 'kartu_mode.overlay_ket' },
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
/**
 * Satu kotak contoh gaya judul: gambar kecil gelap dengan judulnya sendiri di
 * atasnya, digambar persis seperti pratinjau klip menggambarnya.
 *
 * `key` pada teksnya dinaikkan setiap tetikus masuk, supaya elemennya lahir
 * ulang dan animasinya berputar lagi — tanpa itu gerakannya hanya terlihat
 * sekali, saat panel pertama dibuka, lalu tidak pernah lagi.
 */
function ContohGaya({ v, teks, warna, bayang, aktif, onPilih }) {
  const t = useT();
  const [putar, setPutar] = useState(0);
  const skala = 0.34;               // kotak contoh setinggi ±34% kanvas 1920
  return (
    <button type="button" onClick={onPilih} onMouseEnter={() => setPutar((n) => n + 1)}
            className={`judul-contoh${aktif ? ' is-on' : ''}`} title={t(v.note)}>
      <span className="judul-contoh-layar">
        <span key={putar} data-kartu-judul style={{
          display: 'inline-block', color: warna, fontWeight: 900,
          fontSize: `${Math.round(104 * skala * 0.34)}px`, lineHeight: 1.12,
          textTransform: 'uppercase', textAlign: 'center',
          animation: v.anim || undefined,
          ...v.css(bayang, skala * 0.34),
        }}>
          {teks.length > 26 ? `${teks.slice(0, 24).trim()}…` : teks}
        </span>
      </span>
      <span className="judul-contoh-nama">{t(v.label)}</span>
    </button>
  );
}

/** Pilihan lama tampil judul di dalam video. `null` berarti sepanjang klip. */
const LAMA_JUDUL = [
  { id: null, label: 'judul.sepanjang' },
  { id: 5, label: 'judul.lima_detik' },
  { id: 10, label: 'judul.sepuluh_detik' },
];

export default function TitlePanel({
  clip, onChange, onRetitle = null, retitling = false, onJudulSemua = null,
}) {
  const t = useT();
  const [copied, setCopied] = useState(false);
  const [draft, setDraft] = useState('');
  // Keadaan suara pembaca: ada/tidak, sedang dipasang, sedang dibacakan.
  const [voiceReady, setVoiceReady] = useState(null);
  const [voices, setVoices] = useState([]);
  const [busy, setBusy] = useState(null);
  const [heard, setHeard] = useState(null);
  const [voiceError, setVoiceError] = useState(null);
  const audioRef = useRef(null);
  const daftarTema = useDaftarTema();
  const [tersebar, setTersebar] = useState(false);

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
        {t('studio.pilih_satu_klip')}
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
  // Judul yang menempel di dalam video, juga milik klipnya sendiri.
  const jv = { ...DEFAULT_JUDUL_VIDEO, ...clip.judul_video };
  const patchJv = (patch) => onChange({ judul_video: { ...jv, ...patch } });
  const jvText = (jv.teks || '').trim() || title;
  const catatanTema = (id) => daftarTema.find((tm) => tm.id === id)?.catatan;

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
          setVoiceError(t('judul.autoplay_ditahan'));
        }
      }
    } catch (e) {
      setVoiceError(e.message || t('judul.gagal_baca'));
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
      setVoiceError(e.message || t('judul.gagal_pasang'));
    } finally {
      setBusy(null);
    }
  };

  const addTag = () => {
    const tag = draft.trim().replace(/^#+/, '').replace(/[^\wÀ-ɏ]/g, '');
    if (!tag || tags.includes(`#${tag}`)) { setDraft(''); return; }
    onChange({ hashtags: [...tags, `#${tag}`].slice(0, 12) });
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
          {t('judul.judul_klip')}{' '}
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
          ? t('judul.oleh_gemini')
          : t('judul.dari_pembuka')}
        {' '}{t('judul.nama_berkas')}
      </p>

      {/* Klip yang tidak terpilih Gemini saat analisis keluar dengan judul
          heuristik: sebuah kalimat dari klipnya sendiri. Benar, dan datar.
          Tombol ini membetulkannya tanpa menganalisis ulang apa pun. */}
      {onRetitle && (
        <button className="btn-secondary" onClick={onRetitle} disabled={retitling}
                style={{ justifyContent: 'center' }}>
          {retitling ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
          {retitling ? t('judul.gemini_menulis') : t('judul.tulis_ulang')}
        </button>
      )}

      {/* ── Kartu judul di awal klip ──────────────────────────────────────
          Judul yang hanya tertulis kehilangan separuh gunanya di feed yang
          diputar sambil lalu. Kartu di awal, judul besar, dibacakan, memberi
          penonton alasan untuk berhenti sebelum sempat menggulir pergi. */}
      <div style={{ borderTop: '1px solid var(--rule-2)', paddingTop: '12px' }}>
        <label style={{
          display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer',
        }}>
          <input type="checkbox" checked={card.enabled}
                 onChange={(e) => patchCard({ enabled: e.target.checked })}
                 style={{ width: '15px', height: '15px' }} />
          <span className="mark" style={{ color: 'var(--ink)' }}>
            {t('judul.kartu_awal')}
          </span>
        </label>
        <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.55, margin: '6px 0 0' }}>
          {t('judul.kartu_awal_ket')}
        </p>

        {card.enabled && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '11px' }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
              <span className="mark" style={{ color: 'var(--ink)' }}>{t('judul.teks_kartu')}</span>
              <textarea className="field" rows={2} value={card.text}
                        placeholder={title || t('judul.ikut_judul')}
                        onChange={(e) => patchCard({ text: e.target.value })}
                        style={{ resize: 'vertical', fontFamily: 'inherit', lineHeight: 1.5 }} />
            </label>
            <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', margin: 0 }}>
              {t('judul.teks_kartu_ket')}
            </p>

            <div>
              <div className="mark" style={{ color: 'var(--ink)', marginBottom: '6px' }}>
                {t('judul.latar')}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {MODES.map((m) => (
                  <button key={m.id} onClick={() => patchCard({ mode: m.id })}
                          className={`choice${card.mode === m.id ? ' is-on' : ''}`}>
                    <div className="choice-t">{t(m.label)}</div>
                    <div className="choice-h">{t(m.hint)}</div>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div className="mark" style={{ color: 'var(--ink)', marginBottom: '6px' }}>
                {t('judul.gaya')}
              </div>
              {/* Tiap pilihan MEMPERLIHATKAN dirinya, bukan hanya menyebut
                  namanya. Dulu yang ada cuma nama dan satu kalimat keterangan,
                  jadi satu-satunya cara tahu rupa "Stiker dilempar" adalah
                  memilihnya lalu memutar pratinjau klipnya. Diminta pemiliknya:
                  "buatkan juga preview tampilannya seperti apa agar jelas saat
                  kita memilih". Gerakannya diputar ulang saat disentuh tetikus,
                  memakai CSS yang SAMA dengan pratinjau klip. */}
              <GaleriTema teks={cardText} pilihan={card.variant}
                          onPilih={(id) => patchCard({ variant: id })} />
              <div className="mark" style={{ color: 'var(--ink-3)', margin: '12px 0 6px' }}>
                {t('judul.hanya_teks')}
              </div>
              <div className="judul-galeri">
                {CARD_VARIANTS.map((v) => (
                  <ContohGaya key={v.id} v={v} teks={cardText || t('judul.contoh')}
                              warna={card.color || '#FFFFFF'} bayang={card.shadow || '#000000'}
                              aktif={(card.variant || 'garis') === v.id}
                              onPilih={() => patchCard({ variant: v.id })} />
                ))}
              </div>
              <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.55, margin: '8px 0 0' }}>
                {iniTema(card.variant)
                  ? catatanTema(card.variant)
                  : t(CARD_VARIANTS.find((v) => v.id === (card.variant || 'garis'))?.note ?? '')}
              </p>
              <p style={{
                fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.6,
                margin: '8px 0 0',
              }}>
                {t('judul.seret_ket')}
              </p>
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
              <input type="checkbox" checked={card.voice}
                     onChange={(e) => patchCard({ voice: e.target.checked })}
                     style={{ width: '15px', height: '15px' }} />
              <span style={{ fontSize: '.82rem' }}>{t('judul.bacakan')}</span>
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
                        {t('judul.suara_belum')}
                      </span>
                    </div>
                    <button className="btn-secondary" onClick={pasangSuara} disabled={busy === 'pasang'}
                            style={{ justifyContent: 'center' }}>
                      {busy === 'pasang'
                        ? <Loader2 size={14} className="animate-spin" />
                        : <Download size={14} />}
                      {busy === 'pasang' ? t('judul.mengunduh_suara') : t('judul.pasang_suara')}
                    </button>
                  </>
                ) : (
                  <>
                    <div>
                      <div className="mark" style={{ color: 'var(--ink)', marginBottom: '6px' }}>
                        {t('judul.suara_pembaca')}
                      </div>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                        {voices.filter((v) => v.ready).map((v) => (
                          <button key={v.id}
                                  className={`chip${card.voice_id === v.id ? ' is-on' : ''}`}
                                  title={v.note}
                                  onClick={() => { setHeard(null); patchCard({ voice_id: v.id }); }}>
                            {v.label}{v.bahasa === 'en' ? ' · EN' : ''}
                          </button>
                        ))}
                      </div>
                      {/* Pertukarannya disebut apa adanya. Suara Microsoft itu
                          yang terdengar "benar" bagi penonton, tapi memakainya
                          berarti judul klip dikirim keluar dari mesin ini. */}
                      <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.55, margin: '6px 0 0' }}>
                        {voices.find((v) => v.id === card.voice_id)?.online
                          ? t('judul.suara_online')
                          : t('judul.suara_lokal')}
                      </p>
                    </div>
                    <label style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                      <span style={{ fontSize: '.76rem', color: 'var(--ink-2)' }}>
                        {t('judul.tempo', { n: card.rate.toFixed(2) })}
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
                        {t('judul.bacaan_a', { n: heard.seconds.toFixed(1) })}{' '}
                        <b>{t('judul.bacaan_detik', { n: heard.card_seconds.toFixed(1) })}</b>
                        {t('judul.bacaan_b')}
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
                  {t('judul.kartu_tahan', { n: card.seconds.toFixed(1) })}
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

      {/* ── Judul di dalam video ───────────────────────────────────────────
          Berbeda dari kartu di atas: kartu tampil di depan klip lalu pergi,
          judul ini ikut berjalan di atas videonya. Penonton yang masuk di
          tengah klip tetap tahu klip ini tentang apa. */}
      <div style={{ borderTop: '1px solid var(--rule-2)', paddingTop: '12px' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
          <input type="checkbox" checked={jv.aktif}
                 onChange={(e) => patchJv({ aktif: e.target.checked })}
                 style={{ width: '15px', height: '15px' }} />
          <span className="mark" style={{ color: 'var(--ink)' }}>
            {t('judul.di_video')}
          </span>
        </label>
        <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.55, margin: '6px 0 0' }}>
          {t('judul.di_video_ket')}
        </p>

        {jv.aktif && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '11px' }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
              <span className="mark" style={{ color: 'var(--ink)' }}>{t('judul.teks_judul')}</span>
              <textarea className="field" rows={2} value={jv.teks} maxLength={240}
                        placeholder={title || t('judul.ikut_judul')}
                        onChange={(e) => patchJv({ teks: e.target.value })}
                        style={{ resize: 'vertical', fontFamily: 'inherit', lineHeight: 1.5 }} />
            </label>

            <div>
              <div className="mark" style={{ color: 'var(--ink)', marginBottom: '6px' }}>
                {t('judul.lama_tampil')}
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {LAMA_JUDUL.map((l) => (
                  <button key={String(l.id)} type="button"
                          className={`chip${(jv.durasi ?? null) === l.id ? ' is-on' : ''}`}
                          onClick={() => patchJv({ durasi: l.id })}>
                    {t(l.label)}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div className="mark" style={{ color: 'var(--ink)', marginBottom: '6px' }}>
                {t('judul.tema')}
              </div>
              <GaleriTema teks={jvText} pilihan={jv.tema}
                          onPilih={(id) => patchJv({ tema: id })} />
              <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.55, margin: '8px 0 0' }}>
                {catatanTema(jv.tema)}
              </p>
            </div>

            {onJudulSemua && (
              <button className="btn-secondary" style={{ justifyContent: 'center' }}
                      onClick={() => {
                        // Teks tidak ikut disebar: tiap klip memakai judulnya
                        // sendiri, kecuali teks itu memang diisi di klip itu.
                        onJudulSemua({ ...jv, teks: '' });
                        setTersebar(true);
                        setTimeout(() => setTersebar(false), 1800);
                      }}>
                {tersebar ? <Check size={14} style={{ color: 'var(--entry)' }} /> : <Copy size={14} />}
                {tersebar ? t('judul.diterapkan') : t('judul.terapkan_semua')}
              </button>
            )}
          </div>
        )}
      </div>

      <div>
        <div className="mark" style={{ color: 'var(--ink)', marginBottom: '6px' }}>
          {t('judul.tagar_n', { n: tags.length })}
        </div>
        <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginBottom: '7px' }}>
          {tags.map((tg) => (
            <span key={tg} className="chip" style={{ display: 'inline-flex', gap: '5px', alignItems: 'center' }}>
              {tg}
              <X size={11} style={{ cursor: 'pointer' }}
                 onClick={() => onChange({ hashtags: tags.filter((x) => x !== tg) })} />
            </span>
          ))}
          {tags.length === 0 && (
            <span style={{ fontSize: '.75rem', color: 'var(--ink-3)' }}>{t('judul.belum_tagar')}</span>
          )}
        </div>
        <div style={{ display: 'flex', gap: '6px' }}>
          <input className="field" value={draft} placeholder={t('judul.tambah_tagar')}
                 onChange={(e) => setDraft(e.target.value)}
                 onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTag(); } }}
                 style={{ flex: 1, minWidth: 0, padding: '6px 9px', fontSize: '.8rem' }} />
          <button className="btn-secondary" onClick={addTag} disabled={!draft.trim()}
                  style={{ fontSize: '.76rem', padding: '6px 10px' }}>
            <Plus size={12} /> {t('judul.tambah')}
          </button>
        </div>
        <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.55, margin: '8px 0 0' }}>
          {t('judul.tagar_ket')}
        </p>
      </div>

      <button className="btn-secondary" onClick={copyAll}
              disabled={!title && tags.length === 0}
              style={{ justifyContent: 'center' }}>
        {copied ? <Check size={14} style={{ color: 'var(--entry)' }} /> : <Copy size={14} />}
        {copied ? t('judul.tersalin') : t('judul.salin')}
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
