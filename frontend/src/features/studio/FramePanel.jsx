import React, { useEffect, useState } from 'react';
import { Plus, Trash2, ArrowUp, ArrowDown, ScanFace, Loader2, Zap, RotateCcw } from 'lucide-react';
import { apiGet, apiPost } from '../../lib/api';
import FrameKeysPanel from './FrameKeysPanel';
import {
  LAYOUT_PRESETS, addedFrame, clampRect, frameInk, presetLayout,
} from './frames';
import { useT } from '../../lib/i18n';

/**
 * Sakelar penyiapan bingkai semua klip, plus tombol untuk video yang terlanjur.
 *
 * Diminta 25 September 2026. Bingkai tiap klip dulu baru dihitung saat klipnya
 * dibuka, jadi menelusuri dua puluh klip berarti menunggu dua puluh kali.
 * Penyiapan otomatis sesudah auto-klip menghapus penungguan itu, tapi ia
 * memakai CPU di latar, dan pada mesin yang pas-pasan itu terasa. Jadi
 * sakelarnya ada di sini, di tempat orang memikirkan bingkai, bukan terkubur
 * di Pengaturan.
 *
 * Dipindah ke PALING ATAS panel dan diberi kotaknya sendiri pada 26 September
 * 2026, atas permintaan pemiliknya: sebelumnya ia terselip di antara setelan
 * lain yang hanya muncul untuk sebagian cara membingkai, jadi letaknya
 * berpindah-pindah tergantung mode yang sedang dipilih.
 *
 * Sakelarnya berlaku SEKARANG. Dimatikan saat penyiapan sedang berjalan berarti
 * penyiapan itu berhenti di klip berikutnya; dinyalakan lagi berarti
 * melanjutkan, dan melanjutkan hampir gratis karena klip yang sudah terhitung
 * ada di simpanan.
 */
function PemanasanBingkai({ videoId, onUlangSemua = null }) {
  const t = useT();
  const [aktif, setAktif] = useState(null);
  const [sibuk, setSibuk] = useState(false);
  const [kabar, setKabar] = useState(null);

  useEffect(() => {
    apiGet('/settings')
      // Bawaannya MATI sejak 27 September 2026, jadi yang dianggap menyala
      // hanya jawaban yang benar-benar menyatakannya menyala.
      .then((r) => setAktif(r?.pemanasan_bingkai === true))
      .catch(() => setAktif(false));
  }, []);

  const ubah = async (nilai) => {
    const sebelum = aktif;
    setAktif(nilai);
    setKabar(null);
    try {
      // `video_id` ikut supaya menyalakannya kembali MELANJUTKAN video yang
      // sedang dibuka, bukan sekadar menyalakan sakelar untuk video berikutnya.
      const r = await apiPost('/settings/pemanasan-bingkai',
                              { aktif: nilai, video_id: videoId || null });
      if (!nilai) {
        setKabar(r?.dihentikan
          ? t('pemanasan.dihentikan')
          : t('pemanasan.dimatikan'));
      } else {
        setKabar(r?.dilanjutkan
          ? t('pemanasan.dilanjutkan')
          : t('pemanasan.dinyalakan'));
      }
    } catch (e) {
      setAktif(sebelum);
      setKabar(e.message);
    }
  };

  const ulangSemua = async () => {
    if (!onUlangSemua) return;
    setSibuk(true);
    setKabar(null);
    try {
      await onUlangSemua();
      setKabar(t('pemanasan.dibuang'));
    } catch (e) {
      setKabar(e.message);
    } finally {
      setSibuk(false);
    }
  };

  const siapkanSekarang = async () => {
    setSibuk(true);
    setKabar(null);
    try {
      const r = await apiPost(`/projects/${videoId}/siapkan-bingkai`, {});
      setKabar(t('pemanasan.n_klip', { n: r.klip }));
    } catch (e) {
      setKabar(e.message);
    } finally {
      setSibuk(false);
    }
  };

  const menyala = aktif === true;
  return (
    <div style={{
      border: `1px solid ${menyala ? 'var(--accent-cyan)' : 'var(--rule-2)'}`,
      borderRadius: 'var(--r-sm)', padding: '10px 11px',
      background: 'var(--plate-3)', display: 'flex',
      flexDirection: 'column', gap: '8px',
    }}>
      <label style={{ display: 'flex', alignItems: 'center', gap: '9px',
                      cursor: aktif === null ? 'default' : 'pointer' }}>
        <input type="checkbox" checked={menyala} disabled={aktif === null}
               onChange={(e) => ubah(e.target.checked)}
               style={{ width: '16px', height: '16px',
                        accentColor: 'var(--accent-cyan)', flex: 'none' }} />
        <b style={{ fontSize: '0.82rem', flex: 1 }}>{t('pemanasan.judul')}</b>
        <span style={{
          fontSize: '0.64rem', fontWeight: 800, padding: '2px 8px',
          borderRadius: '99px', flex: 'none',
          background: menyala ? 'var(--accent-cyan)' : 'var(--bg-glass)',
          color: menyala ? '#0B1220' : 'var(--text-muted)',
        }}>
          {aktif === null ? '…' : menyala ? t('pemanasan.nyala') : t('pemanasan.mati')}
        </span>
      </label>
      <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', margin: 0,
                  lineHeight: 1.55 }}>
        {menyala
          ? t('pemanasan.nyala_ket')
          : t('pemanasan.mati_ket')}
      </p>
      {/* Tetap ada walau sakelarnya mati: sakelar itu tentang SEMUA video, dan
          tombol ini tentang video yang sedang dibuka. Permintaan langsung
          mengabaikan sakelarnya (lihat `paksa` di routers/clips.py). */}
      {videoId && (
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center',
                      alignSelf: 'flex-start' }}>
          <button className="btn-secondary" onClick={siapkanSekarang} disabled={sibuk}
                  style={{ fontSize: '0.72rem', padding: '5px 9px',
                           display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            {sibuk ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />}
            {t('pemanasan.siapkan')}
          </button>
          {/* Ikon saja. Diminta pemiliknya 1 Oktober 2026 supaya tidak memakan
              tempat; artinya sudah terbaca dari ikon putar-ulang, dan
              keterangan lengkapnya ada di `title`. */}
          {onUlangSemua && (
            <button className="btn-secondary" onClick={ulangSemua} disabled={sibuk}
                    aria-label={t('pemanasan.ulang')}
                    title={t('pemanasan.ulang_judul')}
                    style={{ padding: '5px 7px', display: 'inline-flex',
                             alignItems: 'center', flex: 'none' }}>
              <RotateCcw size={13} />
            </button>
          )}
        </div>
      )}
      {kabar && (
        <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', margin: 0,
                    lineHeight: 1.5 }}>{kabar}</p>
      )}
    </div>
  );
}

// `label` dan `hint` adalah kunci kamus, diterjemahkan saat dirender.
export const FRAME_MODES = [
  { id: 'smart', label: 'mode.smart', hint: 'mode.smart_ket' },
  { id: 'motion', label: 'mode.motion', hint: 'mode.motion_ket' },
  { id: 'gaming', label: 'mode.gaming', hint: 'mode.gaming_ket' },
  { id: 'layout', label: 'mode.layout', hint: 'mode.layout_ket' },
  { id: 'blur', label: 'mode.blur', hint: 'mode.blur_ket' },
  { id: 'center', label: 'mode.center', hint: 'mode.center_ket' },
  { id: 'original', label: 'mode.original', hint: 'mode.original_ket' },
];

/**
 * Tab Bingkai.
 *
 * Susunannya mengikuti urutan pekerjaannya: pilih caranya, lalu — kalau
 * disusun sendiri — pilih titik berangkat dari susunan siap pakai, baru
 * setel tiap bingkainya. Angka di bagian bawah adalah untuk membetulkan hasil
 * seretan sampai persis, bukan untuk menggantikannya.
 */
export default function FramePanel({
  frameMode, onFrameModeChange,
  // Gaya perpindahan: kamera mengikuti dengan mulus, atau diam lalu memotong.
  frameMotion = 'smooth', onFrameMotionChange = null,
  frameZoom = 1, frameGeserY = 0, onFrameZoom = null, onFrameGeserY = null,
  videoId = null,
  // Menghitung ulang bingkai SELURUH klip video ini dari nol.
  onUlangSemua = null,
  layout, onLayoutChange,
  // Main game: setelan susunan dua bidangnya.
  gamingSibuk = false, onGaming = null, onGamingUlang = null,
  frameKeys, onFrameKeys, waktuSekarang, durasiKlip,
  selectedFrameId, onSelectFrame,
  faceTrackAvailable = false,
  peopleCount = 0,
  // Siapa yang sedang dituju bingkai PADA DETIK INI, dan cara mengubahnya
  // mulai dari detik ini. Bukan sakelar sekali untuk seluruh klip: satu klip
  // podcast berpindah pembicara belasan kali.
  aimedPerson = null,
  onAimPerson = null,
  keyCount = 0,
  onClearKeys = null,
  // Bingkai bawaan klip ini dari isinya: 'memuat' | {mode, alasan} | null.
  jenisKlip = null,
  // Pengguna sudah memilih sendiri untuk klip ini; `onOtomatis` membuangnya.
  pilihanSendiri = false, onOtomatis = null,
}) {
  const t = useT();
  const frames = layout?.frames ?? [];
  const selected = frames.find((f) => f.id === selectedFrameId) ?? frames[0] ?? null;

  const patch = (id, key, rect) => onLayoutChange({
    ...layout,
    frames: layout.frames.map((f) => (f.id === id ? { ...f, [key]: clampRect(rect) } : f)),
  });

  const setField = (id, patchObj) => onLayoutChange({
    ...layout,
    frames: layout.frames.map((f) => (f.id === id ? { ...f, ...patchObj } : f)),
  });

  const remove = (id) => {
    const next = frames.filter((f) => f.id !== id);
    onLayoutChange({ ...layout, frames: next });
    if (selectedFrameId === id) onSelectFrame(next[0]?.id ?? null);
  };

  /** Urutan daftar = urutan tumpukan. Yang di bawah daftar tergambar di atas. */
  const move = (id, dir) => {
    const i = frames.findIndex((f) => f.id === id);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= frames.length) return;
    const next = [...frames];
    [next[i], next[j]] = [next[j], next[i]];
    onLayoutChange({ ...layout, frames: next });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '9px' }}>
      {/* Paling atas, dan dengan kotaknya sendiri. Sebelumnya ia terselip di
          antara setelan yang hanya muncul untuk sebagian cara membingkai, jadi
          letaknya berpindah-pindah dan sering tidak terlihat sama sekali. */}
      <PemanasanBingkai videoId={videoId} onUlangSemua={onUlangSemua} />

      <div className="mark" style={{ color: 'var(--ink)' }}>{t('bingkai.cara')}</div>
      {jenisKlip === 'memuat' && !pilihanSendiri && (
        <div className="choice-h" style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <Loader2 size={12} className="animate-spin" />
          {t('bingkai.membaca_isi')}
        </div>
      )}
      {jenisKlip?.mode && !pilihanSendiri && (
        <div className="choice-h">{t('bingkai.dipilih_otomatis', { alasan: jenisKlip.alasan })}</div>
      )}
      {pilihanSendiri && onOtomatis && (
        <div className="choice-h">
          {t('bingkai.dipilih_sendiri')}{' '}
          <button className="chip" onClick={onOtomatis} style={{ fontSize: '0.7rem' }}>
            {t('bingkai.ke_otomatis')}
          </button>
        </div>
      )}
      {FRAME_MODES.map((m) => (
        <button key={m.id} onClick={() => onFrameModeChange(m.id)}
                className={`choice${frameMode === m.id ? ' is-on' : ''}`}>
          <div className="choice-t">{t(m.label)}</div>
          <div className="choice-h">{t(m.hint)}</div>
        </button>
      ))}

      {/* Perbesaran dan geseran tegak.
          Bingkai wajah memakai SELURUH tinggi sumber, jadi secara tegak tidak
          ada yang bisa digeser: potongannya sudah setinggi gambarnya.
          Memperbesar memotong lebih sedikit dari tingginya, dan barulah ada
          sisa untuk memilih bagian mana yang dipakai. Diminta 25 September
          2026: sisipan ditaruh di atas menutupi wajah, dan wajahnya tidak bisa
          dipindahkan ke bawah. */}
      {(frameMode === 'smart' || frameMode === 'motion') && onFrameZoom && (
        <>
          <div style={{ height: '1px', background: 'var(--rule-2)', margin: '4px 0' }} />
          <div className="mark" style={{ color: 'var(--ink)' }}>
            {t('bingkai.perbesar', { n: Number(frameZoom).toFixed(2) })}
          </div>
          <input type="range" min="1" max="2" step="0.02" value={frameZoom}
                 onChange={(e) => onFrameZoom(Number(e.target.value))}
                 style={{ width: '100%', accentColor: 'var(--accent-cyan)' }} />
          <div className="mark" style={{ color: frameZoom > 1 ? 'var(--ink)' : 'var(--ink-3)' }}>
            {frameGeserY > 0 ? t('bingkai.turunkan_n_bawah', { n: Math.round(frameGeserY) })
              : frameGeserY < 0 ? t('bingkai.turunkan_n_atas', { n: Math.round(-frameGeserY) })
                : t('bingkai.turunkan_tengah')}
          </div>
          <input type="range" min="-100" max="100" step="5" value={frameGeserY}
                 disabled={frameZoom <= 1}
                 onChange={(e) => onFrameGeserY(Number(e.target.value))}
                 style={{ width: '100%', accentColor: 'var(--accent-cyan)',
                          opacity: frameZoom <= 1 ? 0.4 : 1 }} />
          <p style={{ fontSize: '0.67rem', color: 'var(--text-muted)', margin: '2px 0 0',
                      lineHeight: 1.5 }}>
            {frameZoom <= 1
              ? t('bingkai.perbesar_dulu')
              : t('bingkai.perbesar_guna')}
          </p>
          {frameZoom > 1 && (
            <button className="btn-secondary" style={{ fontSize: '0.7rem', padding: '4px 9px' }}
                    onClick={() => { onFrameZoom(1); onFrameGeserY(0); }}>
              {t('bingkai.kembalikan')}
            </button>
          )}
        </>
      )}

      {(frameMode === 'smart' || frameMode === 'layout') && onFrameMotionChange && (
        <>
          <div style={{ height: '1px', background: 'var(--rule-2)', margin: '4px 0' }} />
          <div className="mark" style={{ color: 'var(--ink)' }}>{t('bingkai.perpindahan')}</div>
          <div style={{ display: 'flex', gap: '6px' }}>
            {[
              { id: 'smooth', label: t('bingkai.mulus'), hint: t('bingkai.mulus_ket') },
              { id: 'cut', label: t('bingkai.seketika'), hint: t('bingkai.seketika_ket') },
            ].map((m) => (
              <button key={m.id} onClick={() => onFrameMotionChange(m.id)}
                      className={`choice${frameMotion === m.id ? ' is-on' : ''}`}
                      style={{ flex: 1 }}>
                <div className="choice-t">{m.label}</div>
                <div className="choice-h">{m.hint}</div>
              </button>
            ))}
          </div>
        </>
      )}

      {frameMode === 'smart' && jenisKlip !== 'memuat' && peopleCount > 1 && onAimPerson && (
        <>
          <div style={{ height: '1px', background: 'var(--rule-2)', margin: '4px 0' }} />
          <div className="mark" style={{ color: 'var(--ink)' }}>{t('bingkai.arahkan')}</div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            <button className={`chip${aimedPerson === null ? ' is-on' : ''}`}
                    onClick={() => onAimPerson(null)}>
              {t('ulang.otomatis')}
            </button>
            {Array.from({ length: peopleCount }, (_, i) => (
              <button key={i} className={`chip${aimedPerson === i ? ' is-on' : ''}`}
                      onClick={() => onAimPerson(i)}>
                {t('bingkai.wajah_n', { n: i + 1 })}
              </button>
            ))}
          </div>
          <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.55, margin: '2px 0 0' }}>
            {t('bingkai.tanda_a')} <b>{t('bingkai.tanda_b')}</b> {t('bingkai.tanda_c')}{' '}
            <b>{t('bingkai.tanda_d')}</b> {t('bingkai.tanda_e')} <b>{t('bingkai.tanda_f')}</b>{' '}
            {t('bingkai.tanda_g')}
          </p>
          {keyCount > 0 && (
            <button className="btn-secondary" style={{ fontSize: '.75rem', alignSelf: 'start' }}
                    onClick={() => onClearKeys?.()}>
              {t('bingkai.lepas_tanda', { n: keyCount })}
            </button>
          )}
          <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.55, margin: '2px 0 0' }}>
            <b>{t('bingkai.otomatis_a')}</b> {t('bingkai.otomatis_b')}
          </p>
        </>
      )}

      {frameMode === 'gaming' && onGaming && (
        <GamingSetelan layout={layout} sibuk={gamingSibuk}
                       onGaming={onGaming} onUlang={onGamingUlang} />
      )}

      {frameMode !== 'layout' && frameMode !== 'gaming' && (
        <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.5, margin: '4px 0 0' }}>
          {t('bingkai.ikut_wajah_a')} <b>{t('mode.layout')}</b>.
        </p>
      )}

      {frameMode === 'layout' && layout && (
        <>
          <div style={{ height: '1px', background: 'var(--rule-2)', margin: '4px 0' }} />

          <div className="mark" style={{ color: 'var(--ink)' }}>{t('bingkai.mulai_susunan')}</div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {LAYOUT_PRESETS.map((p) => (
              <button key={p.id} className="chip" title={t(p.hint)}
                      onClick={() => {
                        const next = presetLayout(p.id);
                        onLayoutChange({ ...next, background: layout.background });
                        onSelectFrame(next.frames[0].id);
                      }}>
                {t(p.label)}
              </button>
            ))}
          </div>

          <div className="mark" style={{ color: 'var(--ink)', marginTop: '6px' }}>
            {t('bingkai.isi_celah')}
          </div>
          <div style={{ display: 'flex', gap: '6px' }}>
            {[['blur', t('bingkai.celah_blur')], ['black', t('bingkai.celah_hitam')]].map(([id, label]) => (
              <button key={id} className={`chip${layout.background === id ? ' is-on' : ''}`}
                      onClick={() => onLayoutChange({ ...layout, background: id })}>
                {label}
              </button>
            ))}
          </div>

          <div className="plate-head" style={{ marginTop: '8px', padding: '0 0 6px' }}>
            <span className="mark" style={{ color: 'var(--ink)' }}>
              {t('bingkai.n_daftar', { n: frames.length })}
            </span>
            <button className="btn-secondary" style={{ marginLeft: 'auto', fontSize: '.72rem', padding: '5px 8px' }}
                    onClick={() => {
                      const f = addedFrame(frames);
                      onLayoutChange({ ...layout, frames: [...frames, f] });
                      onSelectFrame(f.id);
                    }}>
              <Plus size={12} /> Tambah
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
            {frames.map((f, i) => (
              <div key={f.id}
                   className={`frame-row${f.id === selected?.id ? ' is-on' : ''}`}
                   onClick={() => onSelectFrame(f.id)}>
                <span className="frame-swatch" style={{ background: frameInk(i) }} />
                <input value={f.label} className="field"
                       onClick={(e) => e.stopPropagation()}
                       onChange={(e) => setField(f.id, { label: e.target.value })}
                       style={{ flex: 1, minWidth: 0, padding: '4px 7px', fontSize: '.78rem' }} />
                <IconBtn title={f.follow ? t('bingkai.berhenti_ikut') : t('bingkai.ikut_orang_kotak')}
                         active={f.follow}
                         onClick={(e) => { e.stopPropagation(); setField(f.id, { follow: !f.follow }); }}>
                  <ScanFace size={12} />
                </IconBtn>
                <IconBtn title={t('bingkai.naikkan')} onClick={(e) => { e.stopPropagation(); move(f.id, -1); }}>
                  <ArrowUp size={12} />
                </IconBtn>
                <IconBtn title={t('bingkai.turunkan')} onClick={(e) => { e.stopPropagation(); move(f.id, 1); }}>
                  <ArrowDown size={12} />
                </IconBtn>
                <IconBtn title={t('bingkai.hapus_bingkai')} danger
                         disabled={frames.length <= 1}
                         onClick={(e) => { e.stopPropagation(); remove(f.id); }}>
                  <Trash2 size={12} />
                </IconBtn>
              </div>
            ))}
          </div>

          <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.5, margin: '2px 0 0' }}>
            {t('bingkai.urutan_ket')}
          </p>

          {/* Ikuti orang. Ditaruh di sini, bukan sebagai mode tersendiri:
              "ikuti wajah" dan "susun sendiri" bukan dua pilihan yang saling
              meniadakan, bingkai reaksi yang mengikuti gamer di atas gameplay
              yang diam adalah satu susunan, bukan dua. */}
          <div style={{
            display: 'flex', gap: '9px', alignItems: 'flex-start',
            padding: '9px 11px', borderRadius: 'var(--r-sm)',
            border: '1px solid var(--rule-2)', background: 'var(--plate-3)',
          }}>
            <ScanFace size={15} style={{ flex: 'none', marginTop: '2px', color: 'var(--cue)' }} />
            <div style={{ fontSize: '.74rem', color: 'var(--ink-2)', lineHeight: 1.55 }}>
              <b style={{ color: 'var(--ink)' }}>{t('bingkai.ikut_orang')}</b> {t('bingkai.ikut_orang_a')}{' '}
              <i>{t('bingkai.ikut_orang_b')}</i> {t('bingkai.ikut_orang_c')}
              {!faceTrackAvailable && t('bingkai.belum_terlacak')}
            </div>
          </div>

          {selected && (
            <>
              <div style={{ height: '1px', background: 'var(--rule-2)', margin: '6px 0 2px' }} />
              <div className="mark" style={{ color: 'var(--ink)' }}>
                {t('bingkai.angka_bingkai', { nama: selected.label })}
              </div>

              <RectFields label={t('bingkai.dari_sumber')} rect={selected.src}
                          onChange={(r) => patch(selected.id, 'src', r)} />
              <RectFields label={t('bingkai.ke_kanvas')} rect={selected.dst}
                          onChange={(r) => patch(selected.id, 'dst', r)} />

              <div style={{ display: 'flex', gap: '6px', alignItems: 'center', marginTop: '2px' }}>
                <span style={{ fontSize: '.74rem', color: 'var(--ink-2)' }}>{t('bingkai.isi_kotak')}</span>
                {[['cover', t('bingkai.penuhi')], ['contain', t('bingkai.muat')]].map(([id, label]) => (
                  <button key={id} className={`chip${(selected.fit ?? 'cover') === id ? ' is-on' : ''}`}
                          onClick={() => setField(selected.id, { fit: id })}>
                    {label}
                  </button>
                ))}
              </div>
            </>
          )}
        </>
      )}

      {onFrameKeys && (
        <FrameKeysPanel keys={frameKeys} onKeys={onFrameKeys}
                        waktuSekarang={waktuSekarang ?? 0}
                        durasi={durasiKlip ?? 0} />
      )}
    </div>
  );
}

function IconBtn({ children, danger, active, ...rest }) {
  return (
    <button type="button" {...rest}
            aria-pressed={active === undefined ? undefined : !!active}
            style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: '24px', height: '24px', flex: 'none', cursor: 'pointer',
              background: active ? 'var(--cue)' : 'transparent',
              border: `1px solid ${active ? 'var(--cue)' : 'var(--rule-2)'}`,
              borderRadius: 'var(--r-sm)',
              color: active ? '#fff' : danger ? 'var(--danger)' : 'var(--ink-2)',
              opacity: rest.disabled ? 0.4 : 1,
            }}>
      {children}
    </button>
  );
}

/**
 * Empat angka satu persegi, dalam persen.
 *
 * Persen dan bukan piksel karena itulah satuan yang disimpan; menampilkan
 * piksel akan berarti angka yang terlihat di sini berubah sendiri saat video
 * sumber lain dibuka, padahal susunannya tidak diubah sama sekali.
 */
function RectFields({ label, rect, onChange }) {
  const t = useT();
  const set = (key) => (e) => {
    const v = parseFloat(e.target.value);
    onChange({ ...rect, [key]: Number.isFinite(v) ? v : rect[key] });
  };
  return (
    <div>
      <div style={{ fontSize: '.72rem', color: 'var(--ink-2)', marginBottom: '4px' }}>{label}</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '5px' }}>
        {[['x', t('bingkai.kiri')], ['y', t('bingkai.atas')], ['w', t('bingkai.lebar')], ['h', t('bingkai.tinggi')]].map(([k, name]) => (
          <label key={k} style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            <span style={{ fontSize: '.64rem', color: 'var(--ink-3)' }}>{name} %</span>
            <input type="number" className="field" value={rect[k]} step="0.5"
                   min="0" max="100" onChange={set(k)}
                   style={{ padding: '4px 6px', fontSize: '.76rem', width: '100%' }} />
          </label>
        ))}
      </div>
    </div>
  );
}

/**
 * Setelan Main game: seberapa besar wajah, dan bagaimana permainannya ditaruh.
 *
 * Letak kotaknya sendiri diatur di meja bingkai (seret dan tarik sudutnya);
 * di sini hanya ukuran bidang dan pilihan yang tidak bisa diseret.
 */
function GamingSetelan({ layout, sibuk, onGaming, onUlang }) {
  const t = useT();
  const g = layout?.gaming;
  const ada = !!layout?.frames?.length;
  // Kosong setelah kotak Permainan diubah sendiri: kedua tombol hanya titik
  // berangkat, bukan keadaan yang harus dipertahankan.
  const permainan = g?.permainan ?? 'isi';
  const wajah = Math.round(g?.wajah ?? 40);
  const maksWajah = 75;
  const pindah = Math.max(0, (layout?.reaksi?.length ?? 1) - 1);
  return (
    <>
      <div style={{ height: '1px', background: 'var(--rule-2)', margin: '4px 0' }} />
      <div className="mark" style={{ color: 'var(--ink)' }}>{t('game.judul')}</div>
      {!ada ? (
        <p style={{ fontSize: '.74rem', color: 'var(--ink-3)', lineHeight: 1.5, margin: 0 }}>
          {sibuk ? t('game.mencari') : t('game.tak_ditemukan')}
        </p>
      ) : (
        <>
          <div style={{ display: 'flex', gap: '6px' }}>
            {[
              { id: 'isi', label: t('game.penuhi'), hint: t('game.penuhi_ket') },
              { id: 'utuh', label: t('game.utuh'), hint: t('game.utuh_ket') },
            ].map((m) => (
              <button key={m.id} onClick={() => onGaming({ permainan: m.id })}
                      className={`choice${permainan === m.id ? ' is-on' : ''}`}
                      style={{ flex: 1 }}>
                <div className="choice-t">{m.label}</div>
                <div className="choice-h">{m.hint}</div>
              </button>
            ))}
          </div>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
            <span style={{ display: 'flex', fontSize: '.74rem', color: 'var(--ink-2)' }}>
              {t('game.tinggi_wajah')}
              <b style={{ marginLeft: 'auto', color: 'var(--ink)' }}>{wajah}%</b>
            </span>
            <input type="range" min="20" max={maksWajah} step="1"
                   value={Math.min(wajah, maksWajah)}
                   onChange={(e) => onGaming({ wajah: Number(e.target.value) })} />
          </label>

          <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.55, margin: '2px 0 0' }}>
            {t('game.seret_a')} <b>{t('game.seret_b')}</b>{t('game.seret_c')}
          </p>
          <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.55, margin: '2px 0 0' }}>
            {t('game.bebas_a')} <b>{t('mode.layout')}</b>{t('game.bebas_b')}{' '}
            <b>{t('game.bebas_c')}</b> {t('game.bebas_d')} <b>{t('game.bebas_e')}</b>{' '}
            {t('game.bebas_f')}
          </p>
          {pindah > 0 && (
            <p style={{ fontSize: '.72rem', color: 'var(--ink-2)', lineHeight: 1.55, margin: 0 }}>
              {t('game.pindah', { n: pindah })}
            </p>
          )}
          {onUlang && (
            <button className="btn-secondary" style={{ fontSize: '.75rem', alignSelf: 'start' }}
                    onClick={onUlang} disabled={sibuk}>
              {t('game.cari_ulang')}
            </button>
          )}
        </>
      )}
    </>
  );
}
