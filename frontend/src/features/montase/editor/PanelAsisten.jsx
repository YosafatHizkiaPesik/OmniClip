/**
 * Tab "Asisten" di panel Bahan (JOB-4 M5.1-M5.4).
 *
 * Perintah tingkat proyek ("susun Top 5 momen paling lucu dari klip-klip
 * ini") dikirim bersama klip terpilih dari Bahan saya. Hasilnya daftar
 * OPERASI usulan: editor menampilkannya bergaris putus di linimasa (pratinjau
 * ikut memutarnya), dan pemilik memilih per operasi atau per peringkat untuk
 * diterima, atau menolak semuanya. Asisten tidak pernah menulis dokumen.
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  Check, CheckCheck, Loader2, Scissors, Sparkles, X,
} from 'lucide-react';
import { useT } from '../../../lib/i18n';
import { formatTime } from '../../../utils/timeFormat';
import { useJobRunner } from '../../../hooks/useJob';
import JobProgress from '../../../components/JobProgress';
import { daftarSuara } from '../api.js';
import { kelompokOperasi } from '../model/usulan.js';

export function DaftarUsulan({ usulan, onPilih, onTerima, onTolak, fps }) {
  const t = useT();
  const kelompok = useMemo(() => kelompokOperasi(usulan.operasi), [usulan.operasi]);
  const pilih = usulan.pilih;
  const ganti = (ids, nyala) => {
    const baru = new Set(pilih);
    ids.forEach((id) => (nyala ? baru.add(id) : baru.delete(id)));
    onPilih(baru);
  };
  const totalPotong = usulan.operasi.filter((o) => o.jenis === 'potong' && pilih.has(o.id))
    .reduce((n, o) => n + (o.sampai - o.dari), 0);
  return (
    <div className="montase-usulan" data-sumber={usulan.sumber}>
      <p className="montase-usulan-kepala">
        <Sparkles size={13} />
        {t(usulan.sumber === 'ai' ? 'montase.asisten.dari_ai' : 'montase.asisten.dari_lokal', { n: usulan.operasi.length })}
      </p>
      {usulan.peringatan?.length > 0 && (
        <ul className="montase-daftar-peringatan">{usulan.peringatan.map((p) => <li key={p}>{p}</li>)}</ul>
      )}
      {totalPotong > 0 && (
        <p className="montase-petunjuk">{t('montase.asisten.total_potong', { detik: (totalPotong / fps).toFixed(1) })}</p>
      )}
      <ul className="montase-usulan-kelompok">
        {kelompok.map(({ kelompok: k, ops }) => {
          const semua = ops.every((o) => pilih.has(o.id));
          return (
            <li key={k}>
              <label className="montase-centang montase-usulan-judul">
                <input type="checkbox" checked={semua} onChange={(e) => ganti(ops.map((o) => o.id), e.target.checked)} />
                <b>{k || t('montase.asisten.lain')}</b>
              </label>
              <ul>
                {ops.map((o) => (
                  <li key={o.id} className={`montase-usulan-op jenis-${o.jenis}`}>
                    <label className="montase-centang">
                      <input type="checkbox" checked={pilih.has(o.id)} onChange={(e) => ganti([o.id], e.target.checked)} />
                      <span>
                        <span className="montase-usulan-jenis">{t(`montase.asisten.op_${o.jenis}`)}</span>
                        {' '}{o.label}
                        {o.jenis === 'potong' ? ` (${formatTime(o.dari / fps)}, ${((o.sampai - o.dari) / fps).toFixed(1)} ${t('montase.satuan.detik')})` : ''}
                      </span>
                    </label>
                    {o.alasan && <small>{o.alasan}</small>}
                  </li>
                ))}
              </ul>
            </li>
          );
        })}
      </ul>
      <TombolUsulan usulan={usulan} onTerima={onTerima} onTolak={onTolak} />
    </div>
  );
}

export function TombolUsulan({ usulan, onTerima, onTolak, ringkas = false }) {
  const t = useT();
  const n = usulan.pilih.size;
  return (
    <div className="montase-baris-tombol montase-tombol-usulan">
      <button type="button" className="btn-primary" onClick={() => onTerima(null)}>
        <CheckCheck size={13} />{t('montase.asisten.terima_semua')}
      </button>
      <button type="button" className="btn-secondary" disabled={n === 0 || n === usulan.operasi.length}
              onClick={() => onTerima(usulan.pilih)}
      >
        <Check size={13} />{ringkas ? t('montase.asisten.terima_n', { n }) : t('montase.asisten.terima_pilih', { n })}
      </button>
      <button type="button" className="btn-secondary" onClick={onTolak}>
        <X size={13} />{t('montase.asisten.tolak')}
      </button>
    </div>
  );
}

export default function PanelAsisten({
  proyekId, bahan, terpilih, fps, usulan, onUsulan, onTerima, onTolak, onSimpanDulu,
}) {
  const t = useT();
  const [perintah, setPerintah] = useState('');
  const [pilih, setPilih] = useState(null);
  const [maks, setMaks] = useState(20);
  const [narasi, setNarasi] = useState(true);
  const [suara, setSuara] = useState('');
  const [daftar, setDaftar] = useState([]);
  const [galat, setGalat] = useState(null);
  const kerja = useJobRunner();
  const jeda = useJobRunner();

  const video = useMemo(() => bahan.filter((b) => b.jenis === 'video'), [bahan]);
  const dipilih = pilih ?? new Set(video.map((b) => b.id));
  useEffect(() => { daftarSuara().then((s) => { setDaftar(s); }).catch(() => {}); }, []);

  useEffect(() => {
    const h = kerja.result ?? jeda.result;
    if (!h) return;
    if (!h.operasi?.length) {
      setGalat(t('montase.asisten.tanpa_usulan'));
      return;
    }
    onUsulan({ ...h, pilih: new Set(h.operasi.map((o) => o.id)) });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kerja.result, jeda.result]);

  const susun = async () => {
    setGalat(null);
    await onSimpanDulu();
    kerja.run(`/montase/proyek/${proyekId}/asisten`, {
      perintah: perintah.trim(), bahan: video.filter((b) => dipilih.has(b.id)).map((b) => b.id),
      narasi, suara, maks_detik: Number(maks) || 20,
    }).catch((e) => setGalat(e.message));
  };
  const item = terpilih?.item;
  const bisaJeda = item && (item.jenis === 'video' || item.jenis === 'audio');
  const buangJeda = async () => {
    setGalat(null);
    await onSimpanDulu();
    jeda.run(`/montase/proyek/${proyekId}/jeda`, { item: item.id }).catch((e) => setGalat(e.message));
  };
  const centang = (id, nyala) => {
    const baru = new Set(dipilih);
    if (nyala) baru.add(id); else baru.delete(id);
    setPilih(baru);
  };
  const sibuk = kerja.active || jeda.active;

  if (usulan) {
    return (
      <div className="montase-asisten">
        <DaftarUsulan usulan={usulan} fps={fps} onPilih={(p) => onUsulan({ ...usulan, pilih: p })}
                      onTerima={onTerima} onTolak={onTolak} />
      </div>
    );
  }
  return (
    <div className="montase-asisten">
      {galat && <p className="montase-galat" role="alert">{galat}</p>}
      <section className="montase-bagian">
        <h3><span><Sparkles size={13} /> {t('montase.asisten.judul')}</span></h3>
        <textarea rows={3} maxLength={1000} value={perintah} placeholder={t('montase.asisten.contoh')}
                  aria-label={t('montase.asisten.perintah')} onChange={(e) => setPerintah(e.target.value)} />
        <p className="montase-petunjuk">{t('montase.asisten.pilih_klip')}</p>
        {video.length === 0 && <p className="montase-petunjuk">{t('montase.asisten.tanpa_klip')}</p>}
        <ul className="montase-asisten-klip">
          {video.map((b) => (
            <li key={b.id}>
              <label className="montase-centang">
                <input type="checkbox" checked={dipilih.has(b.id)} onChange={(e) => centang(b.id, e.target.checked)} />
                <span title={b.nama}>{b.nama}</span>
                <small>{b.durasi ? formatTime(b.durasi) : ''}</small>
              </label>
            </li>
          ))}
        </ul>
        <label className="montase-kolom">
          <span>{t('montase.asisten.maks_detik')}</span>
          <input type="number" min={3} max={120} value={maks} className="montase-angka-kecil"
                 onChange={(e) => setMaks(e.target.value)} />
        </label>
        <label className="montase-centang">
          <input type="checkbox" checked={narasi} onChange={(e) => setNarasi(e.target.checked)} />
          {t('montase.asisten.narasi')}
        </label>
        {narasi && daftar.length > 0 && (
          <label className="montase-kolom">
            <span>{t('montase.asisten.suara')}</span>
            <select value={suara} onChange={(e) => setSuara(e.target.value)}>
              <option value="">{t('montase.asisten.suara_bawaan')}</option>
              {daftar.map((s) => <option key={s.id} value={s.id} disabled={!s.siap}>{s.label}</option>)}
            </select>
          </label>
        )}
        <button type="button" className="btn-primary" onClick={susun}
                disabled={sibuk || perintah.trim().length < 3 || dipilih.size === 0}
        >
          {kerja.active ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
          {t('montase.asisten.susun')}
        </button>
        {(kerja.job || kerja.error) && <JobProgress job={kerja.job} error={kerja.error} onCancel={kerja.cancel} compact />}
      </section>
      <section className="montase-bagian">
        <h3><span><Scissors size={13} /> {t('montase.asisten.jeda_judul')}</span></h3>
        <p className="montase-petunjuk">{t(bisaJeda ? 'montase.asisten.jeda_ket' : 'montase.asisten.jeda_pilih')}</p>
        <button type="button" className="btn-secondary" onClick={buangJeda} disabled={!bisaJeda || sibuk}>
          {jeda.active ? <Loader2 size={13} className="animate-spin" /> : <Scissors size={13} />}
          {t('montase.asisten.jeda_tombol')}
        </button>
        {(jeda.job || jeda.error) && <JobProgress job={jeda.job} error={jeda.error} onCancel={jeda.cancel} compact />}
      </section>
    </div>
  );
}
