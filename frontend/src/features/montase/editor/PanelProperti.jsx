/**
 * Panel Properti editor Montase (JOB-4 M1.7, M2.2, M2.5-M2.7).
 *
 * Isinya mengikuti yang dipilih:
 *   - satu item: waktu, kecepatan (atau tanda bingkai beku), suara (volume,
 *     lembut masuk/keluar), isi bingkai, teks/props animasi, dan
 *     transformasi (posisi, skala, putar, transparansi, potong). Angka di
 *     layar dalam detik, persen, dan derajat; di dokumen dalam bingkai dan
 *     piksel kanvas;
 *   - beberapa item: jumlahnya, gandakan, hapus;
 *   - satu lajur: nama, volume, kunci/bisu/sembunyi, hapus lajur kosong;
 *   - tidak ada: pengaturan proyek, daftar penanda, dan daftar pintasan.
 *
 * Kolom props animasi dibuat dari contohProps modulnya (teks, angka, warna);
 * panel dari skema zod lengkap datang di M4.5.
 */
import React, { useState } from 'react';
import {
  AudioLines, Bookmark, ChevronLeft, ChevronRight, CopyPlus, Diamond, Lock, RotateCcw, Trash2,
} from 'lucide-react';
import { useT, angka } from '../../../lib/i18n';
import { formatTime } from '../../../utils/timeFormat';
import { BAWAAN } from '../komposisi/index.js';
import { kodeWaktu, useGaris } from './garisPutar.js';
import { bingkaiKeyframe, KURVA, SIFAT_KEYFRAME } from '../komposisi/keyframe.js';
import { nilaiSifat } from '../model/suntingan.js';
import PanelTeks from './PanelTeks.jsx';
import { KolomNarasi } from './PanelSuara.jsx';

const WARNA = /^#[0-9a-fA-F]{6}$/;
const KECEPATAN = [0.5, 1, 1.5, 2];
const PINTASAN = [
  ['Spasi', 'montase.pintasan.putar'],
  ['← / →', 'montase.pintasan.bingkai'],
  ['Shift + ← / →', 'montase.pintasan.detik'],
  ['Ctrl + B', 'montase.pintasan.belah'],
  ['Delete', 'montase.pintasan.hapus'],
  ['Shift + Delete', 'montase.pintasan.hapus_beriak'],
  ['Ctrl + Z / Ctrl + Shift + Z', 'montase.pintasan.batal'],
  ['Ctrl + C / V / D', 'montase.pintasan.salin'],
  ['Ctrl + A', 'montase.pintasan.pilih_semua'],
  ['M', 'montase.pintasan.penanda'],
  ['N', 'montase.pintasan.magnet'],
  ['+ / −', 'montase.pintasan.zoom'],
  ['Home / End', 'montase.pintasan.ujung'],
];

function Angka({ label, nilai, onUbah, langkah = 0.1, min = 0, max, akhiran, desimal = 3 }) {
  return (
    <label className="montase-kolom">
      <span>{label}</span>
      <span className="montase-isian-akhiran">
        <input type="number" step={langkah} min={min} max={max}
               value={Number.isFinite(nilai) ? Number(nilai.toFixed(desimal)) : ''}
               onChange={(e) => { if (e.target.value !== '') onUbah(Number(e.target.value)); }} />
        {akhiran && <small>{akhiran}</small>}
      </span>
    </label>
  );
}

function KolomProps({ props, onUbah }) {
  return Object.entries(props).map(([kunci, nilai]) => {
    if (typeof nilai === 'number') {
      return <Angka key={kunci} label={kunci} nilai={nilai} langkah={1}
                    onUbah={(v) => onUbah({ ...props, [kunci]: v })} />;
    }
    if (typeof nilai === 'string' && WARNA.test(nilai)) {
      return (
        <label key={kunci} className="montase-kolom">
          <span>{kunci}</span>
          <input type="color" value={nilai} onChange={(e) => onUbah({ ...props, [kunci]: e.target.value })} />
        </label>
      );
    }
    if (typeof nilai === 'string') {
      return (
        <label key={kunci} className="montase-kolom">
          <span>{kunci}</span>
          <input value={nilai} onChange={(e) => onUbah({ ...props, [kunci]: e.target.value })} />
        </label>
      );
    }
    return null;
  });
}

function Bagian({ judul, children, aksi }) {
  return (
    <section className="montase-bagian">
      <h3>{judul}{aksi}</h3>
      {children}
    </section>
  );
}

function PanelProyek({ dokumen, onUbahProyek, onKe, onUbahPenanda, onHapusPenanda }) {
  const t = useT();
  const k = dokumen.kanvas;
  const fps = k.fps;
  const penanda = dokumen.penanda ?? [];
  return (
    <>
      <div className="montase-panel-kepala"><h2>{t('montase.properti.proyek')}</h2></div>
      <div className="montase-panel-isi">
        <label className="montase-kolom">
          <span>{t('montase.home.nama')}</span>
          <input value={dokumen.nama} maxLength={120}
                 onChange={(e) => onUbahProyek({ nama: e.target.value || dokumen.nama })} />
        </label>
        <dl className="montase-ringkas">
          <dt>{t('montase.home.ukuran')}</dt><dd>{k.lebar}×{k.tinggi}</dd>
          <dt>{t('montase.home.fps')}</dt><dd>{k.fps} fps</dd>
          <dt>{t('montase.properti.durasi_proyek')}</dt><dd>{formatTime(dokumen.durasi / fps)}</dd>
        </dl>
        <label className="montase-kolom">
          <span>{t('montase.properti.latar')}</span>
          <input type="color" value={k.latar}
                 onChange={(e) => onUbahProyek({ kanvas: { latar: e.target.value } })} />
        </label>
        <p className="montase-petunjuk">{t('montase.properti.petunjuk')}</p>

        <Bagian judul={t('montase.properti.penanda')}>
          {penanda.length === 0 && <p className="montase-petunjuk">{t('montase.properti.penanda_kosong')}</p>}
          <ul className="montase-daftar-penanda">
            {penanda.map((p) => (
              <li key={p.t}>
                <button type="button" className="btn-secondary montase-ikon" onClick={() => onKe(p.t)}
                        title={t('montase.linimasa.ke_penanda', { nama: p.label || kodeWaktu(p.t, fps) })}
                        aria-label={t('montase.linimasa.ke_penanda', { nama: p.label || kodeWaktu(p.t, fps) })}
                >
                  <Bookmark size={12} />
                </button>
                <small>{kodeWaktu(p.t, fps)}</small>
                <input value={p.label} maxLength={40} placeholder={t('montase.properti.nama_penanda')}
                       aria-label={t('montase.properti.nama_penanda')}
                       onChange={(e) => onUbahPenanda(p.t, e.target.value)} />
                <button type="button" className="btn-secondary montase-ikon" onClick={() => onHapusPenanda(p.t)}
                        title={t('montase.properti.hapus_penanda')} aria-label={t('montase.properti.hapus_penanda')}
                >
                  <Trash2 size={12} />
                </button>
              </li>
            ))}
          </ul>
        </Bagian>

        <details className="montase-pintasan">
          <summary>{t('montase.pintasan.judul')}</summary>
          <dl>
            {PINTASAN.map(([tombol, kunci]) => (
              <React.Fragment key={kunci}><dt><kbd>{tombol}</kbd></dt><dd>{t(kunci)}</dd></React.Fragment>
            ))}
          </dl>
        </details>
      </div>
    </>
  );
}

function PanelLajur({ lajur, onUbahLajur, onHapusLajur, bisaHapus, onRendam }) {
  const t = useT();
  const [turun, setTurun] = useState(25);
  const ubah = (p) => onUbahLajur(lajur.id, p);
  const bersuara = lajur.jenis === 'video' || lajur.jenis === 'audio';
  return (
    <>
      <div className="montase-panel-kepala">
        <h2>{t('montase.properti.lajur', { jenis: t(`montase.lajur.${lajur.jenis}`) })}</h2>
        <button type="button" className="btn-secondary montase-ikon" disabled={!bisaHapus}
                onClick={() => onHapusLajur(lajur.id)}
                title={bisaHapus ? t('montase.properti.hapus_lajur') : t('montase.properti.hapus_lajur_tidak')}
                aria-label={t('montase.properti.hapus_lajur')}
        >
          <Trash2 size={13} />
        </button>
      </div>
      <div className="montase-panel-isi">
        <label className="montase-kolom">
          <span>{t('montase.linimasa.nama_lajur')}</span>
          <input value={lajur.nama} maxLength={60} onChange={(e) => ubah({ nama: e.target.value })} />
        </label>
        {bersuara && (
          <label className="montase-kolom">
            <span>{t('montase.properti.volume_lajur')}</span>
            <span className="montase-geser-angka">
              <input type="range" min={0} max={200} step={5} value={Math.round((lajur.volume ?? 1) * 100)}
                     onChange={(e) => ubah({ volume: Number(e.target.value) / 100 })} />
              <small>{Math.round((lajur.volume ?? 1) * 100)}%</small>
            </span>
          </label>
        )}
        <label className="montase-centang">
          <input type="checkbox" checked={Boolean(lajur.kunci)} onChange={(e) => ubah({ kunci: e.target.checked })} />
          {t('montase.linimasa.kunci')}
        </label>
        {bersuara && (
          <label className="montase-centang">
            <input type="checkbox" checked={Boolean(lajur.bisu)} onChange={(e) => ubah({ bisu: e.target.checked })} />
            {t('montase.linimasa.bisu')}
          </label>
        )}
        {lajur.jenis !== 'audio' && (
          <label className="montase-centang">
            <input type="checkbox" checked={Boolean(lajur.sembunyi)} onChange={(e) => ubah({ sembunyi: e.target.checked })} />
            {t('montase.linimasa.sembunyi')}
          </label>
        )}
        {!bisaHapus && <p className="montase-petunjuk">{t('montase.properti.hapus_lajur_tidak')}</p>}
        {lajur.jenis === 'audio' && (
          <Bagian judul={t('montase.rendam.judul')}>
            <p className="montase-petunjuk">{t('montase.rendam.ket')}</p>
            <label className="montase-kolom">
              <span>{t('montase.rendam.turun')}</span>
              <span className="montase-geser-angka">
                <input type="range" min={0} max={80} step={5} value={turun}
                       onChange={(e) => setTurun(Number(e.target.value))} />
                <small>{turun}%</small>
              </span>
            </label>
            <button type="button" className="btn-secondary" onClick={() => onRendam(lajur.id, turun / 100)}>
              <AudioLines size={13} />{t('montase.rendam.terapkan')}
            </button>
          </Bagian>
        )}
      </div>
    </>
  );
}

/**
 * Tombol wajik keyframe (M3.7): penuh = ada keyframe di garis putar, garis
 * tepi = sifat ini punya keyframe di tempat lain, pudar = belum ada.
 */
function Wajik({ status, onKlik, label }) {
  return (
    <button type="button" className={`montase-wajik ${status}`} onClick={onKlik}
            aria-pressed={status === 'di'} title={label} aria-label={label}
    >
      <Diamond size={11} />
    </button>
  );
}

function statusWajik(item, sifat, f) {
  const daftar = item.keyframe?.[sifat] ?? [];
  if (daftar.some((k) => k.t === f)) return 'di';
  return daftar.length ? 'ada' : 'tidak';
}

/** Sifat yang bisa diberi keyframe: angka + wajik, nilainya pada garis putar. */
function KolomSifat({ item, sifat, f, label, kali = 1, akhiran, langkah, min, max, desimal, onUbahSifat, onTombol }) {
  const t = useT();
  return (
    <div className="montase-kolom-wajik">
      <Angka label={label} nilai={nilaiSifat(item, sifat, f) * kali} langkah={langkah} min={min} max={max}
             akhiran={akhiran} desimal={desimal} onUbah={(v) => onUbahSifat({ [sifat]: v / kali })} />
      <Wajik status={statusWajik(item, sifat, f)} onKlik={() => onTombol(sifat)}
             label={t('montase.keyframe.wajik', { sifat: label })} />
    </div>
  );
}

/** Kurva dan lompat ke keyframe sebelum/sesudah, bila item punya keyframe. */
function KendaliKeyframe({ item, f, onKurva, onKe }) {
  const t = useT();
  const semua = bingkaiKeyframe(item);
  if (!semua.length) return null;
  const sebelum = [...semua].reverse().find((x) => x < f);
  const sesudah = semua.find((x) => x > f);
  const kini = SIFAT_KEYFRAME.flatMap((s) => item.keyframe?.[s] ?? []).find((k) => k.t === f);
  return (
    <div className="montase-kendali-keyframe">
      <button type="button" className="btn-secondary montase-ikon" disabled={sebelum === undefined}
              onClick={() => onKe(item.mulai + sebelum)} title={t('montase.keyframe.sebelum')}
              aria-label={t('montase.keyframe.sebelum')}
      >
        <ChevronLeft size={12} />
      </button>
      <button type="button" className="btn-secondary montase-ikon" disabled={sesudah === undefined}
              onClick={() => onKe(item.mulai + sesudah)} title={t('montase.keyframe.sesudah')}
              aria-label={t('montase.keyframe.sesudah')}
      >
        <ChevronRight size={12} />
      </button>
      {kini && (
        <select value={kini.kurva ?? 'linear'} onChange={(e) => onKurva(e.target.value)}
                aria-label={t('montase.keyframe.kurva')} title={t('montase.keyframe.kurva')}
        >
          {KURVA.map((k) => <option key={k} value={k}>{t(`montase.keyframe.kurva_${k}`)}</option>)}
        </select>
      )}
    </div>
  );
}

function PanelTransform({ item, garis, onUbahSifat, onTombol, onKurva, onKe, onTransform, onAturUlang }) {
  const t = useT();
  const f = useGaris(garis) - item.mulai;
  const p = item.ubah?.potong ?? {};
  const bisaPotong = item.jenis !== 'teks';
  const sifat = { item, f, onUbahSifat, onTombol };
  return (
    <Bagian
      judul={t('montase.properti.transformasi')}
      aksi={(
        <button type="button" className="btn-secondary montase-ikon" onClick={onAturUlang}
                title={t('montase.pegangan.atur_ulang')} aria-label={t('montase.pegangan.atur_ulang')}
        >
          <RotateCcw size={12} />
        </button>
      )}
    >
      <KendaliKeyframe item={item} f={f} onKurva={onKurva} onKe={onKe} />
      <div className="montase-kolom-dua">
        <KolomSifat {...sifat} sifat="x" label="X" langkah={1} min={-20000} akhiran="px" desimal={0} />
        <KolomSifat {...sifat} sifat="y" label="Y" langkah={1} min={-20000} akhiran="px" desimal={0} />
        <KolomSifat {...sifat} sifat="skala" label={t('montase.properti.skala')} kali={100} langkah={5}
                    min={1} max={2000} akhiran="%" desimal={1} />
        <KolomSifat {...sifat} sifat="putar" label={t('montase.properti.putar')} langkah={1} min={-3600}
                    max={3600} akhiran="°" desimal={1} />
      </div>
      <KolomSifat {...sifat} sifat="opasitas" label={t('montase.properti.opasitas')} kali={100} langkah={5}
                  max={100} akhiran="%" desimal={0} />
      {bisaPotong && (
        <>
          <p className="montase-label-kecil">{t('montase.properti.potong')}</p>
          <div className="montase-kolom-dua">
            {['kiri', 'kanan', 'atas', 'bawah'].map((s) => (
              <Angka key={s} label={t(`montase.properti.sisi_${s}`)} nilai={p[s] ?? 0} langkah={1} max={95}
                     akhiran="%" desimal={1} onUbah={(v) => onTransform({ potong: { [s]: v } })} />
            ))}
          </div>
        </>
      )}
    </Bagian>
  );
}

/** Volume item dengan wajik (keyframe volume, juga hasil perendam musik M3.4). */
function KolomVolume({ item, garis, onUbahSifat, onTombol }) {
  const t = useT();
  const f = useGaris(garis) - item.mulai;
  const v = Math.round(nilaiSifat(item, 'volume', f) * 100);
  return (
    <div className="montase-kolom-wajik">
      <label className="montase-kolom">
        <span>{t('montase.properti.volume')}</span>
        <span className="montase-geser-angka">
          <input type="range" min={0} max={200} step={5} value={v}
                 onChange={(e) => onUbahSifat({ volume: Number(e.target.value) / 100 })} />
          <small>{v}%</small>
        </span>
      </label>
      <Wajik status={statusWajik(item, 'volume', f)} onKlik={() => onTombol('volume')}
             label={t('montase.keyframe.wajik', { sifat: t('montase.properti.volume') })} />
    </div>
  );
}

export default function PanelProperti({
  dokumen, terpilih, jumlahPilihan, lajur, onUbahItem, onKecepatan, onTransform, onHapus,
  onGandakan, onUbahProyek, onUbahLajur, onHapusLajur, bisaHapusLajur, onKe, onUbahPenanda,
  onHapusPenanda, onBuatUlangNarasi, garis, onUbahSifat, onTombolKeyframe, onKurvaKeyframe,
  onAturUlangTransform, onRendam,
}) {
  const t = useT();
  const fps = dokumen.kanvas.fps;
  const keDetik = (b) => b / fps;
  const keBingkai = (d) => Math.round(d * fps);

  if (jumlahPilihan > 1) {
    return (
      <aside className="montase-panel montase-panel-properti" aria-label={t('montase.properti.judul')}>
        <div className="montase-panel-kepala"><h2>{t('montase.properti.banyak', { n: jumlahPilihan })}</h2></div>
        <div className="montase-panel-isi">
          <p className="montase-petunjuk">{t('montase.properti.banyak_ket')}</p>
          <div className="montase-baris-tombol">
            <button type="button" className="btn-secondary" onClick={onGandakan}>
              <CopyPlus size={13} />{t('montase.linimasa.gandakan')}
            </button>
            <button type="button" className="btn-secondary" onClick={onHapus}>
              <Trash2 size={13} />{t('montase.linimasa.hapus')}
            </button>
          </div>
        </div>
      </aside>
    );
  }
  if (!terpilih && lajur) {
    return (
      <aside className="montase-panel montase-panel-properti" aria-label={t('montase.properti.judul')}>
        <PanelLajur lajur={lajur} onUbahLajur={onUbahLajur} onHapusLajur={onHapusLajur} bisaHapus={bisaHapusLajur}
                    onRendam={onRendam} />
      </aside>
    );
  }
  if (!terpilih) {
    return (
      <aside className="montase-panel montase-panel-properti" aria-label={t('montase.properti.judul')}>
        <PanelProyek dokumen={dokumen} onUbahProyek={onUbahProyek} onKe={onKe}
                     onUbahPenanda={onUbahPenanda} onHapusPenanda={onHapusPenanda} />
      </aside>
    );
  }

  const { item } = terpilih;
  const kunci = Boolean(terpilih.lajur.kunci);
  const ubah = (perubahan) => onUbahItem(item.id, perubahan);
  const media = item.jenis === 'video' || item.jenis === 'audio';
  const bersuara = item.jenis === 'audio'
    || (item.jenis === 'video' && dokumen.bahan[item.bahan]?.ada_suara && !item.beku);
  return (
    <aside className="montase-panel montase-panel-properti" aria-label={t('montase.properti.judul')}>
      <div className="montase-panel-kepala">
        <h2>{t(`montase.jenis.${item.jenis}`)}</h2>
        <button type="button" className="btn-secondary montase-ikon" onClick={onHapus} disabled={kunci}
                title={t('montase.linimasa.hapus')} aria-label={t('montase.linimasa.hapus')}
        >
          <Trash2 size={13} />
        </button>
      </div>
      <div className="montase-panel-isi">
        {kunci && <p className="montase-label-kunci"><Lock size={12} />{t('montase.properti.terkunci')}</p>}
        <fieldset disabled={kunci} className="montase-kelompok">
          {item.asal === 'ai' && <p className="montase-label-ai">{t('montase.properti.ai', { alasan: item.alasan ?? '' })}</p>}
          <div className="montase-kolom-dua">
            <Angka label={t('montase.properti.mulai')} nilai={keDetik(item.mulai)} akhiran={t('montase.satuan.detik')}
                   onUbah={(v) => ubah({ mulai: keBingkai(v) })} />
            <Angka label={t('montase.properti.durasi')} nilai={keDetik(item.durasi)} akhiran={t('montase.satuan.detik')} min={0.05}
                   onUbah={(v) => ubah({ durasi: keBingkai(v) })} />
          </div>

          {item.jenis === 'audio' && item.narasi && (
            <KolomNarasi key={item.id} item={item} onBuatUlang={(n) => onBuatUlangNarasi(item.id, n)} />
          )}
          {media && (
            <Angka label={t('montase.properti.potong_awal')} nilai={keDetik(item.potong_awal || 0)}
                   akhiran={t('montase.satuan.detik')} onUbah={(v) => ubah({ potong_awal: keBingkai(v) })} />
          )}
          {media && item.beku && <p className="montase-petunjuk">{t('montase.properti.beku_ket')}</p>}
          {media && !item.beku && (
            <Bagian judul={t('montase.properti.kecepatan')}>
              <div className="montase-baris-tombol">
                {KECEPATAN.map((k) => (
                  <button key={k} type="button"
                          className={`btn-secondary ${(item.kecepatan ?? 1) === k ? 'aktif' : ''}`}
                          aria-pressed={(item.kecepatan ?? 1) === k} onClick={() => onKecepatan(item.id, k)}
                  >
                    {angka(k)}x
                  </button>
                ))}
              </div>
              <Angka label={t('montase.properti.kecepatan_tepat')} nilai={item.kecepatan ?? 1} langkah={0.05}
                     min={0.25} max={4} akhiran="x" desimal={2} onUbah={(v) => onKecepatan(item.id, v)} />
            </Bagian>
          )}
          {bersuara && (
            <Bagian judul={t('montase.properti.suara')}>
              <KolomVolume item={item} garis={garis} onUbahSifat={(s) => onUbahSifat(item.id, s)}
                           onTombol={(sifat) => onTombolKeyframe(item.id, sifat)} />
              <div className="montase-kolom-dua">
                <Angka label={t('montase.properti.fade_masuk')} nilai={keDetik(item.fade_masuk || 0)}
                       akhiran={t('montase.satuan.detik')} onUbah={(v) => ubah({ fade_masuk: keBingkai(v) })} />
                <Angka label={t('montase.properti.fade_keluar')} nilai={keDetik(item.fade_keluar || 0)}
                       akhiran={t('montase.satuan.detik')} onUbah={(v) => ubah({ fade_keluar: keBingkai(v) })} />
              </div>
            </Bagian>
          )}
          {(item.jenis === 'video' || item.jenis === 'gambar') && (
            <label className="montase-kolom">
              <span>{t('montase.properti.isi')}</span>
              <select value={item.isi ?? 'contain'} onChange={(e) => ubah({ isi: e.target.value })}>
                <option value="contain">{t('montase.properti.isi_muat')}</option>
                <option value="cover">{t('montase.properti.isi_penuh')}</option>
              </select>
            </label>
          )}
          {item.jenis === 'teks' && <PanelTeks item={item} onUbah={ubah} />}
          {item.jenis === 'motion' && (
            <>
              <p className="montase-petunjuk">{BAWAAN[item.komponen] ? t('montase.properti.bawaan') : item.komponen}</p>
              <KolomProps props={item.props ?? {}} onUbah={(props) => ubah({ props })} />
            </>
          )}
          {item.jenis !== 'audio' && (
            <PanelTransform item={item} garis={garis} onKe={onKe}
                            onTransform={(sebagian) => onTransform(item.id, sebagian)}
                            onUbahSifat={(s) => onUbahSifat(item.id, s)}
                            onTombol={(sifat) => onTombolKeyframe(item.id, sifat)}
                            onKurva={(k) => onKurvaKeyframe(item.id, k)}
                            onAturUlang={() => onAturUlangTransform(item.id)} />
          )}
        </fieldset>
      </div>
    </aside>
  );
}
