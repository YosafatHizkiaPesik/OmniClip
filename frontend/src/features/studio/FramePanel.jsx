import React, { useEffect, useState } from 'react';
import { Plus, Trash2, ArrowUp, ArrowDown, ScanFace, Loader2, Zap } from 'lucide-react';
import { apiGet, apiPost } from '../../lib/api';
import FrameKeysPanel from './FrameKeysPanel';
import {
  LAYOUT_PRESETS, addedFrame, clampRect, frameInk, presetLayout,
} from './frames';

/**
 * Sakelar pemanasan bingkai, plus tombol untuk video yang sudah terlanjur.
 *
 * Diminta 25 September 2026. Bingkai tiap klip dulu baru dihitung saat klipnya
 * dibuka, jadi menelusuri dua puluh klip berarti menunggu dua puluh kali.
 * Pemanasan otomatis sesudah auto-klip menghapus penungguan itu, tapi ia
 * memakai CPU di latar, dan pada mesin yang pas-pasan itu terasa. Jadi
 * sakelarnya ada di sini, di tempat orang memikirkan bingkai, bukan terkubur
 * di Pengaturan.
 */
function PemanasanBingkai({ videoId }) {
  const [aktif, setAktif] = useState(null);
  const [sibuk, setSibuk] = useState(false);
  const [kabar, setKabar] = useState(null);

  useEffect(() => {
    apiGet('/settings')
      .then((r) => setAktif(r?.pemanasan_bingkai !== false))
      .catch(() => setAktif(true));
  }, []);

  const ubah = async (nilai) => {
    const sebelum = aktif;
    setAktif(nilai);
    try {
      await apiPost('/settings/pemanasan-bingkai', { aktif: nilai });
    } catch (e) {
      setAktif(sebelum);
      setKabar(e.message);
    }
  };

  const siapkanSekarang = async () => {
    setSibuk(true);
    setKabar(null);
    try {
      const r = await apiPost(`/projects/${videoId}/siapkan-bingkai`, {});
      setKabar(`Bingkai ${r.klip} klip sedang disiapkan. Kemajuannya di halaman Partitur.`);
    } catch (e) {
      setKabar(e.message);
    } finally {
      setSibuk(false);
    }
  };

  return (
    <>
      <div style={{ height: '1px', background: 'var(--rule-2)', margin: '4px 0' }} />
      <label style={{ display: 'flex', alignItems: 'flex-start', gap: '9px',
                      cursor: aktif === null ? 'default' : 'pointer' }}>
        <input type="checkbox" checked={aktif === true} disabled={aktif === null}
               onChange={(e) => ubah(e.target.checked)}
               style={{ marginTop: '3px', width: '15px', height: '15px',
                        accentColor: 'var(--accent-cyan)', flex: 'none' }} />
        <span style={{ fontSize: '0.75rem', lineHeight: 1.5 }}>
          <b>Siapkan bingkai semua klip di awal.</b>{' '}
          <span style={{ color: 'var(--text-muted)' }}>
            Sesudah mengklip, bingkai dua puluh klip pertama dihitung lebih dulu di
            latar, jadi tiap klip yang dibuka langsung terbingkai. Dimatikan berarti
            bingkainya dihitung saat klipnya dibuka, beberapa detik tiap kali, dan
            CPU-nya bebas untuk hal lain.
          </span>
        </span>
      </label>
      <button className="btn-secondary" onClick={siapkanSekarang} disabled={sibuk}
              style={{ fontSize: '0.72rem', padding: '5px 9px', alignSelf: 'flex-start',
                       display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
        {sibuk ? <Loader2 size={12} className="animate-spin" /> : <Zap size={12} />}
        Siapkan bingkai video ini sekarang
      </button>
      {kabar && (
        <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', margin: 0,
                    lineHeight: 1.5 }}>{kabar}</p>
      )}
    </>
  );
}

export const FRAME_MODES = [
  { id: 'smart', label: 'Ikuti wajah', hint: 'Kamera mengikuti pembicara. Layar penuh, tanpa bilah kabur.' },
  { id: 'motion', label: 'Ikuti gerakan', hint: 'Untuk tokoh yang BUKAN manusia, kartun, maskot, hewan. Kamera mengikuti bagian yang paling banyak bergerak, tanpa perlu mengenali wajah.' },
  { id: 'gaming', label: 'Main game', hint: 'Wajah pemain di atas, permainan di bawah. Letak facecam dicari sendiri, lalu ukuran dan posisinya bisa Anda atur.' },
  { id: 'layout', label: 'Susun sendiri', hint: 'Satu bingkai atau lebih, masing-masing bisa diatur letak dan ukurannya.' },
  { id: 'blur', label: 'Bilah kabur', hint: 'Video utuh di tengah, sisi atas-bawah diisi versi kabur.' },
  { id: 'center', label: 'Potong tengah', hint: 'Ambil bagian tengah frame. Paling cepat, tanpa analisis.' },
  { id: 'original', label: 'Orisinal', hint: 'Bingkai video sumber apa adanya, tanpa dipotong sama sekali.' },
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
      <div className="mark" style={{ color: 'var(--ink)' }}>Cara membingkai</div>
      {jenisKlip === 'memuat' && !pilihanSendiri && (
        <div className="choice-h" style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <Loader2 size={12} className="animate-spin" />
          Membaca isi klip: game, wajah, atau tanpa wajah…
        </div>
      )}
      {jenisKlip?.mode && !pilihanSendiri && (
        <div className="choice-h">Dipilih otomatis: {jenisKlip.alasan}.</div>
      )}
      {pilihanSendiri && onOtomatis && (
        <div className="choice-h">
          Dipilih sendiri untuk klip ini.{' '}
          <button className="chip" onClick={onOtomatis} style={{ fontSize: '0.7rem' }}>
            Kembali ke otomatis
          </button>
        </div>
      )}
      {FRAME_MODES.map((m) => (
        <button key={m.id} onClick={() => onFrameModeChange(m.id)}
                className={`choice${frameMode === m.id ? ' is-on' : ''}`}>
          <div className="choice-t">{m.label}</div>
          <div className="choice-h">{m.hint}</div>
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
            Perbesar wajah, {Number(frameZoom).toFixed(2)}x
          </div>
          <input type="range" min="1" max="2" step="0.02" value={frameZoom}
                 onChange={(e) => onFrameZoom(Number(e.target.value))}
                 style={{ width: '100%', accentColor: 'var(--accent-cyan)' }} />
          <div className="mark" style={{ color: frameZoom > 1 ? 'var(--ink)' : 'var(--ink-3)' }}>
            Turunkan wajah, {frameGeserY > 0 ? `${Math.round(frameGeserY)} ke bawah`
              : frameGeserY < 0 ? `${Math.round(-frameGeserY)} ke atas` : 'tengah'}
          </div>
          <input type="range" min="-100" max="100" step="5" value={frameGeserY}
                 disabled={frameZoom <= 1}
                 onChange={(e) => onFrameGeserY(Number(e.target.value))}
                 style={{ width: '100%', accentColor: 'var(--accent-cyan)',
                          opacity: frameZoom <= 1 ? 0.4 : 1 }} />
          <p style={{ fontSize: '0.67rem', color: 'var(--text-muted)', margin: '2px 0 0',
                      lineHeight: 1.5 }}>
            {frameZoom <= 1
              ? 'Perbesar dulu sebelum bisa digeser: tanpa perbesaran, bingkainya sudah setinggi gambar aslinya, jadi tidak ada ruang tersisa.'
              : 'Berguna saat sisipan menutupi wajahnya. Perbesaran memakan ketajaman, jadi ambil secukupnya saja.'}
          </p>
          {frameZoom > 1 && (
            <button className="btn-secondary" style={{ fontSize: '0.7rem', padding: '4px 9px' }}
                    onClick={() => { onFrameZoom(1); onFrameGeserY(0); }}>
              Kembalikan
            </button>
          )}
        </>
      )}

      {(frameMode === 'smart' || frameMode === 'layout') && onFrameMotionChange && (
        <>
          <div style={{ height: '1px', background: 'var(--rule-2)', margin: '4px 0' }} />
          <div className="mark" style={{ color: 'var(--ink)' }}>Perpindahan bingkai</div>
          <div style={{ display: 'flex', gap: '6px' }}>
            {[
              { id: 'smooth', label: 'Mulus', hint: 'kamera mengikuti orangnya' },
              { id: 'cut', label: 'Seketika', hint: 'diam, lalu berpindah' },
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

      {videoId && <PemanasanBingkai videoId={videoId} />}

      {frameMode === 'smart' && peopleCount > 1 && onAimPerson && (
        <>
          <div style={{ height: '1px', background: 'var(--rule-2)', margin: '4px 0' }} />
          <div className="mark" style={{ color: 'var(--ink)' }}>Arahkan bingkai dari detik ini</div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            <button className={`chip${aimedPerson === null ? ' is-on' : ''}`}
                    onClick={() => onAimPerson(null)}>
              Otomatis
            </button>
            {Array.from({ length: peopleCount }, (_, i) => (
              <button key={i} className={`chip${aimedPerson === i ? ' is-on' : ''}`}
                      onClick={() => onAimPerson(i)}>
                Wajah {i + 1}
              </button>
            ))}
          </div>
          <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.55, margin: '2px 0 0' }}>
            Tombol ini memasang <b>tanda</b> di posisi playhead: mulai detik itu
            bingkai menoleh ke orang yang dipilih, sampai tanda berikutnya. Jadi
            satu bagian yang meleset bisa dibetulkan tanpa mengambil alih seluruh
            klip. Tandanya terlihat dan bisa dihapus di lajur <b>Wajah</b> pada
            linimasa klip. Nomornya diurut dari kiri ke kanan layar, bukan
            nomor <b>Orang</b> di partitur, yang itu hasil memisahkan suara.
          </p>
          {keyCount > 0 && (
            <button className="btn-secondary" style={{ fontSize: '.75rem', alignSelf: 'start' }}
                    onClick={() => onClearKeys?.()}>
              Lepas {keyCount} tanda, kembali otomatis penuh
            </button>
          )}
          <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.55, margin: '2px 0 0' }}>
            <b>Otomatis</b> mencocokkan wajah dengan suara: sistem sudah tahu
            kapan tiap orang bicara, lalu mencari mulut siapa yang ikut bergerak
            saat itu. Ia bisa keliru: mulut yang tertutup mikrofon hampir tidak
            bergerak di gambar. Kalau begitu, tunjuk saja orangnya.
          </p>
        </>
      )}

      {frameMode === 'gaming' && onGaming && (
        <GamingSetelan layout={layout} sibuk={gamingSibuk}
                       onGaming={onGaming} onUlang={onGamingUlang} />
      )}

      {frameMode !== 'layout' && frameMode !== 'gaming' && (
        <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.5, margin: '4px 0 0' }}>
          Mode ikut-wajah menganalisis klip sebelum render. Bila wajah jarang
          terlihat, misalnya rekaman layar, sistem otomatis memakai bilah kabur.
          Untuk klip main game atau reaksi streamer, pakai <b>Susun sendiri</b>.
        </p>
      )}

      {frameMode === 'layout' && layout && (
        <>
          <div style={{ height: '1px', background: 'var(--rule-2)', margin: '4px 0' }} />

          <div className="mark" style={{ color: 'var(--ink)' }}>Mulai dari susunan</div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {LAYOUT_PRESETS.map((p) => (
              <button key={p.id} className="chip" title={p.hint}
                      onClick={() => {
                        const next = presetLayout(p.id);
                        onLayoutChange({ ...next, background: layout.background });
                        onSelectFrame(next.frames[0].id);
                      }}>
                {p.label}
              </button>
            ))}
          </div>

          <div className="mark" style={{ color: 'var(--ink)', marginTop: '6px' }}>
            Isi celah antar bingkai
          </div>
          <div style={{ display: 'flex', gap: '6px' }}>
            {[['blur', 'Kabur dari sumber'], ['black', 'Hitam pekat']].map(([id, label]) => (
              <button key={id} className={`chip${layout.background === id ? ' is-on' : ''}`}
                      onClick={() => onLayoutChange({ ...layout, background: id })}>
                {label}
              </button>
            ))}
          </div>

          <div className="plate-head" style={{ marginTop: '8px', padding: '0 0 6px' }}>
            <span className="mark" style={{ color: 'var(--ink)' }}>
              Bingkai ({frames.length})
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
                <IconBtn title={f.follow ? 'Berhenti mengikuti' : 'Ikuti orang di kotak ini'}
                         active={f.follow}
                         onClick={(e) => { e.stopPropagation(); setField(f.id, { follow: !f.follow }); }}>
                  <ScanFace size={12} />
                </IconBtn>
                <IconBtn title="Naikkan" onClick={(e) => { e.stopPropagation(); move(f.id, -1); }}>
                  <ArrowUp size={12} />
                </IconBtn>
                <IconBtn title="Turunkan" onClick={(e) => { e.stopPropagation(); move(f.id, 1); }}>
                  <ArrowDown size={12} />
                </IconBtn>
                <IconBtn title="Hapus bingkai" danger
                         disabled={frames.length <= 1}
                         onClick={(e) => { e.stopPropagation(); remove(f.id); }}>
                  <Trash2 size={12} />
                </IconBtn>
              </div>
            ))}
          </div>

          <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.5, margin: '2px 0 0' }}>
            Urutan daftar adalah urutan tumpukan: yang paling bawah tergambar
            paling atas. Seret kotak di video sumber untuk memilih bagian yang
            diambil, dan kotak di kanvas hasil untuk menaruhnya.
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
              <b style={{ color: 'var(--ink)' }}>Ikuti orang:</b> taruh kotaknya
              di atas orang yang Anda mau, lalu tekan ikon wajah pada baris
              bingkai itu. Bingkainya akan membuntuti <i>orang itu</i> sepanjang
              klip, bukan siapa pun yang wajahnya kebetulan paling besar.
              Lebar, tinggi, dan posisi tegaknya tetap milik Anda.
              {!faceTrackAvailable && (
                <> Untuk klip ini wajah belum terlacak, jadi bingkai pengikut
                akan diam di tempat kotaknya.</>
              )}
            </div>
          </div>

          {selected && (
            <>
              <div style={{ height: '1px', background: 'var(--rule-2)', margin: '6px 0 2px' }} />
              <div className="mark" style={{ color: 'var(--ink)' }}>
                Angka bingkai “{selected.label}”
              </div>

              <RectFields label="Diambil dari video sumber" rect={selected.src}
                          onChange={(r) => patch(selected.id, 'src', r)} />
              <RectFields label="Ditaruh di kanvas hasil" rect={selected.dst}
                          onChange={(r) => patch(selected.id, 'dst', r)} />

              <div style={{ display: 'flex', gap: '6px', alignItems: 'center', marginTop: '2px' }}>
                <span style={{ fontSize: '.74rem', color: 'var(--ink-2)' }}>Isi kotak:</span>
                {[['cover', 'Penuhi (potong sisa)'], ['contain', 'Muat semua (sisakan bilah)']].map(([id, label]) => (
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
  const set = (key) => (e) => {
    const v = parseFloat(e.target.value);
    onChange({ ...rect, [key]: Number.isFinite(v) ? v : rect[key] });
  };
  return (
    <div>
      <div style={{ fontSize: '.72rem', color: 'var(--ink-2)', marginBottom: '4px' }}>{label}</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '5px' }}>
        {[['x', 'Kiri'], ['y', 'Atas'], ['w', 'Lebar'], ['h', 'Tinggi']].map(([k, name]) => (
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
      <div className="mark" style={{ color: 'var(--ink)' }}>Susunan main game</div>
      {!ada ? (
        <p style={{ fontSize: '.74rem', color: 'var(--ink-3)', lineHeight: 1.5, margin: 0 }}>
          {sibuk ? 'Mencari kamera wajah pemain di video ini…'
            : 'Kamera wajah pemain tidak ditemukan di klip ini. Coba klip lain, '
              + 'atau pakai Susun sendiri.'}
        </p>
      ) : (
        <>
          <div style={{ display: 'flex', gap: '6px' }}>
            {[
              { id: 'isi', label: 'Penuhi layar', hint: 'wajah di atas, game mengisi sisanya' },
              { id: 'utuh', label: 'Game utuh', hint: 'seluruh layar game, sisa diisi kabur' },
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
              Tinggi bidang wajah
              <b style={{ marginLeft: 'auto', color: 'var(--ink)' }}>{wajah}%</b>
            </span>
            <input type="range" min="20" max={maksWajah} step="1"
                   value={Math.min(wajah, maksWajah)}
                   onChange={(e) => onGaming({ wajah: Number(e.target.value) })} />
          </label>

          <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.55, margin: '2px 0 0' }}>
            Kedua bingkai bebas diatur seperti <b>Susun sendiri</b>: seret dan
            tarik sudut kotak di <b>video sumber</b> untuk memilih bagian yang
            diambil, dan di <b>layar hasil</b> untuk menentukan letak dan
            ukurannya. Garis putus-putus di dalam kotak menandai bagian yang
            benar-benar tampil. Tombol dan penggeser di atas menyusun ulang
            keduanya dari awal. Setelan ini milik klip ini saja.
          </p>
          {pindah > 0 && (
            <p style={{ fontSize: '.72rem', color: 'var(--ink-2)', lineHeight: 1.55, margin: 0 }}>
              Kamera wajah berpindah tempat {pindah}× di klip ini. Kotak Reaksi
              ikut pindah pada detiknya. Menyeret kotak Reaksi mengubah letak
              yang berlaku di posisi garis main saja.
            </p>
          )}
          {onUlang && (
            <button className="btn-secondary" style={{ fontSize: '.75rem', alignSelf: 'start' }}
                    onClick={onUlang} disabled={sibuk}>
              Cari ulang letak wajah otomatis
            </button>
          )}
        </>
      )}
    </>
  );
}
