/**
 * Tab "Animasi" di panel Bahan (JOB-4 M4.2-M4.10).
 *
 *   - Pustaka bawaan (tanpa AI) dan pustaka saya (animasi AI yang disimpan);
 *   - Buat dengan AI, dua jalur dengan format yang sama:
 *       "Koneksi AI"  -> pekerjaan montase_motion (Pengaturan > AI, urutan
 *                        K-12, atau satu koneksi pilihan "AI untuk Montase");
 *       "Claude.ai"   -> salin permintaan, tempel ke Project Claude, tempel
 *                        balasannya kembali (untuk langganan Claude Pro);
 *   - hasil: lima bingkai contoh dari pemeriksa, masalah/peringatan, revisi
 *     lewat perintah (versi baru), riwayat versi, simpan ke pustaka.
 * "Sesuaikan dengan video" mengirim lembar fakta rentang terpilih (M4.7).
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  CheckCircle2, ClipboardCopy, Download, ExternalLink, Loader2, Plus, RefreshCw, Save, Search,
  Sparkles, XCircle,
} from 'lucide-react';
import { useT } from '../../../lib/i18n';
import { useJobRunner } from '../../../hooks/useJob';
import JobProgress from '../../../components/JobProgress';
import { BAWAAN } from '../komposisi/index.js';
import {
  ALAMAT_PAKET_CLAUDE, alamatGambarKomponen, ambilSetelan, daftarKomponen, permintaanClaude,
  simpanKePustaka, simpanSetelanAi, versiKomponen,
} from '../api.js';

function KartuHasil({ versi, token, onTambah, onSimpan, onRevisi, mode, onVersi, semuaVersi }) {
  const t = useT();
  const [nama, setNama] = useState(versi.nama);
  const [perintah, setPerintah] = useState('');
  const c = versi.catatan ?? {};
  const lolos = versi.status === 'lolos';
  return (
    <div className={`montase-hasil-ai ${lolos ? 'lolos' : 'gagal'}`}>
      <div className="montase-hasil-kepala">
        {lolos ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
        <b>{versi.nama}</b>
        <small>v{versi.versi} · {lolos ? t('montase.ai.lolos') : t('montase.ai.gagal')}</small>
        {semuaVersi.length > 1 && (
          <select value={versi.versi} onChange={(e) => onVersi(Number(e.target.value))}
                  aria-label={t('montase.ai.versi')}
          >
            {semuaVersi.map((v) => <option key={v.versi} value={v.versi}>v{v.versi} · {v.status}</option>)}
          </select>
        )}
      </div>
      {versi.gambar > 0 && token && (
        <div className="montase-hasil-bingkai">
          {Array.from({ length: versi.gambar }, (_, i) => (
            <img key={i} alt="" loading="lazy" src={alamatGambarKomponen(token, versi.id, versi.versi, i)} />
          ))}
        </div>
      )}
      {c.alasan && <p className="montase-petunjuk">{c.alasan}</p>}
      {(c.masalah ?? []).length > 0 && (
        <ul className="montase-daftar-masalah">{c.masalah.map((m) => <li key={m}>{m}</li>)}</ul>
      )}
      {(c.peringatan ?? []).length > 0 && (
        <ul className="montase-daftar-peringatan">{c.peringatan.map((m) => <li key={m}>{m}</li>)}</ul>
      )}
      {versi.pesan_perbaikan && (
        <button type="button" className="btn-secondary" onClick={() => navigator.clipboard?.writeText(versi.pesan_perbaikan)}>
          <ClipboardCopy size={13} />{t('montase.ai.salin_perbaikan')}
        </button>
      )}
      {lolos && (
        <div className="montase-baris-tombol">
          <button type="button" className="btn-primary" onClick={() => onTambah(versi)}>
            <Plus size={13} />{t('montase.ai.tambah')}
          </button>
          <input value={nama} maxLength={80} aria-label={t('montase.ai.nama')} onChange={(e) => setNama(e.target.value)} />
          <button type="button" className="btn-secondary" disabled={!nama.trim()} onClick={() => onSimpan(versi, nama.trim())}>
            <Save size={13} />{versi.disimpan ? t('montase.ai.tersimpan') : t('montase.ai.simpan')}
          </button>
        </div>
      )}
      <div className="montase-revisi">
        <input value={perintah} placeholder={t('montase.ai.revisi_contoh')} aria-label={t('montase.ai.revisi')}
               onChange={(e) => setPerintah(e.target.value)} />
        <button type="button" className="btn-secondary" disabled={perintah.trim().length < 3}
                onClick={() => { onRevisi(perintah.trim()); setPerintah(''); }}
        >
          <RefreshCw size={13} />{mode === 'claude' ? t('montase.ai.salin_revisi') : t('montase.ai.revisi')}
        </button>
      </div>
    </div>
  );
}

export default function PanelAnimasi({ token, proyekId, dokumen, garis, terpilih, onTambahBawaan, onTambahAi, onSimpanDulu }) {
  const t = useT();
  const fps = dokumen.kanvas.fps;
  const [mode, setMode] = useState('api');
  const [permintaan, setPermintaan] = useState('');
  const [sesuaikan, setSesuaikan] = useState(true);
  const [balasan, setBalasan] = useState('');
  const [teksClaude, setTeksClaude] = useState('');
  const [setelan, setSetelan] = useState(null);
  const [pustaka, setPustaka] = useState([]);
  const [cari, setCari] = useState('');
  const [hasil, setHasil] = useState(null);
  const [semuaVersi, setSemuaVersi] = useState([]);
  const [galat, setGalat] = useState(null);
  const kerja = useJobRunner();

  const muatPustaka = useCallback(() => {
    daftarKomponen({ pustaka: true, cari }).then(setPustaka).catch(() => {});
  }, [cari]);
  useEffect(() => { muatPustaka(); }, [muatPustaka]);
  useEffect(() => { ambilSetelan().then(setSetelan).catch(() => {}); }, []);

  // Rentang yang disesuaikan: item bergambar terpilih, atau 4 detik dari garis putar.
  const item = terpilih?.item;
  const rentang = item && item.jenis !== 'motion'
    ? { mulai: item.mulai, durasi: item.durasi }
    : { mulai: garis.get(), durasi: 4 * fps };
  const durasi = sesuaikan ? Math.min(rentang.durasi, 10 * fps) : 2 * fps;

  const terima = useCallback(async (v) => {
    setHasil(v);
    try { setSemuaVersi(await versiKomponen(v.id)); } catch { setSemuaVersi([v]); }
  }, []);
  useEffect(() => {
    if (kerja.result) terima(kerja.result);
  }, [kerja.result, terima]);

  const isi = (tambahan = {}) => ({
    permintaan: permintaan.trim(), proyek_id: proyekId, durasi,
    ...(sesuaikan ? { rentang } : {}), ...tambahan,
  });

  const jalankan = async (jalur, badan) => {
    setGalat(null);
    await onSimpanDulu();
    kerja.run(jalur, badan).catch((e) => setGalat(e.message));
  };
  const buat = () => jalankan('/montase/komponen/buat', isi());
  const revisi = async (perintah) => {
    if (!hasil) return;
    if (mode === 'claude') {
      const r = await permintaanClaude({ ...isi(), permintaan: perintah, komponen_id: hasil.id });
      setTeksClaude(r.teks);
      navigator.clipboard?.writeText(r.teks).catch(() => {});
      return;
    }
    jalankan('/montase/komponen/buat', { ...isi(), permintaan: perintah, komponen_id: hasil.id });
  };
  const salinPermintaan = async () => {
    setGalat(null);
    try {
      const r = await permintaanClaude(isi());
      setTeksClaude(r.teks);
      await navigator.clipboard?.writeText(r.teks).catch(() => {});
    } catch (e) {
      setGalat(e.message);
    }
  };
  const periksaBalasan = () => jalankan('/montase/komponen/tempel', {
    ...isi(), balasan, ...(hasil && teksClaude.includes('Kode versi sekarang') ? { komponen_id: hasil.id } : {}),
  });

  const tambah = (v) => {
    const taruh = v.catatan?.taruh_di;
    const mulai = sesuaikan && Number.isFinite(taruh) ? rentang.mulai + Math.round(taruh * fps) : garis.get();
    onTambahAi(v, { mulai, durasi: v.durasi_bawaan || durasi });
  };
  const simpan = async (v, nama) => {
    try {
      await simpanKePustaka(v.id, v.versi, nama);
      setHasil({ ...v, nama, disimpan: true });
      muatPustaka();
    } catch (e) {
      setGalat(e.message);
    }
  };

  return (
    <div className="montase-animasi">
      {galat && <p className="montase-galat" role="alert">{galat}</p>}
      <section className="montase-bagian">
        <h3>{t('montase.ai.bawaan')}</h3>
        <div className="montase-kisi-animasi">
          {Object.keys(BAWAAN).map((k) => (
            <button key={k} type="button" className="btn-secondary" onClick={() => onTambahBawaan(k)}>
              <Plus size={12} />{t(`montase.animasi.${k}`)}
            </button>
          ))}
        </div>
      </section>

      <section className="montase-bagian">
        <h3>{t('montase.ai.pustaka')}</h3>
        <label className="montase-cari">
          <Search size={12} />
          <input value={cari} placeholder={t('montase.ai.cari')} onChange={(e) => setCari(e.target.value)} />
        </label>
        {pustaka.length === 0 && <p className="montase-petunjuk">{t('montase.ai.pustaka_kosong')}</p>}
        <ul className="montase-daftar-pustaka">
          {pustaka.map((v) => (
            <li key={v.id}>
              {v.gambar > 0 && token && <img alt="" src={alamatGambarKomponen(token, v.id, v.versi, 2)} />}
              <span>{v.nama}<small>v{v.versi}</small></span>
              <button type="button" className="btn-secondary montase-ikon" onClick={() => onTambahAi(v, { mulai: garis.get(), durasi: v.durasi_bawaan || 2 * fps })}
                      title={t('montase.ai.tambah')} aria-label={t('montase.ai.tambah')}
              >
                <Plus size={12} />
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="montase-bagian">
        <h3><span><Sparkles size={13} /> {t('montase.ai.buat')}</span></h3>
        <div className="montase-tab" role="tablist">
          {['api', 'claude'].map((m) => (
            <button key={m} type="button" role="tab" aria-selected={mode === m} className={mode === m ? 'aktif' : ''}
                    onClick={() => setMode(m)}
            >
              {t(`montase.ai.mode_${m}`)}
            </button>
          ))}
        </div>
        <textarea rows={3} maxLength={2000} value={permintaan} placeholder={t('montase.ai.contoh')}
                  aria-label={t('montase.ai.permintaan')} onChange={(e) => setPermintaan(e.target.value)} />
        <label className="montase-centang">
          <input type="checkbox" checked={sesuaikan} onChange={(e) => setSesuaikan(e.target.checked)} />
          {t('montase.ai.sesuaikan', { detik: (rentang.durasi / fps).toFixed(1), mulai: (rentang.mulai / fps).toFixed(1) })}
        </label>
        {mode === 'api' && (
          <>
            {setelan && (
              <label className="montase-kolom">
                <span>{t('montase.ai.koneksi')}</span>
                <select value={setelan.ai_koneksi ?? ''} onChange={async (e) => setSetelan(await simpanSetelanAi(e.target.value))}>
                  <option value="">{t('montase.ai.koneksi_urutan')}</option>
                  {(setelan.koneksi ?? []).map((k) => <option key={k.id} value={k.id}>{k.nama}</option>)}
                </select>
              </label>
            )}
            {setelan && !(setelan.koneksi ?? []).length && <p className="montase-petunjuk">{t('montase.ai.tanpa_koneksi')}</p>}
            <button type="button" className="btn-primary" disabled={kerja.active || permintaan.trim().length < 3} onClick={buat}>
              {kerja.active ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}{t('montase.ai.buat_tombol')}
            </button>
          </>
        )}
        {mode === 'claude' && (
          <ol className="montase-langkah-claude">
            <li>
              {t('montase.ai.claude_1')}{' '}
              <a href={ALAMAT_PAKET_CLAUDE} download><Download size={12} /> {t('montase.ai.unduh_paket')}</a>
            </li>
            <li>
              <button type="button" className="btn-secondary" disabled={permintaan.trim().length < 3} onClick={salinPermintaan}>
                <ClipboardCopy size={13} />{t('montase.ai.salin_permintaan')}
              </button>
              <a className="btn-secondary" href="https://claude.ai/new" target="_blank" rel="noreferrer">
                <ExternalLink size={13} />{t('montase.ai.buka_claude')}
              </a>
              {teksClaude && <textarea rows={4} readOnly value={teksClaude} aria-label={t('montase.ai.salin_permintaan')} />}
            </li>
            <li>
              <textarea rows={5} value={balasan} placeholder={t('montase.ai.tempel_contoh')}
                        aria-label={t('montase.ai.tempel')} onChange={(e) => setBalasan(e.target.value)} />
              <button type="button" className="btn-primary" disabled={kerja.active || balasan.trim().length < 10} onClick={periksaBalasan}>
                {kerja.active ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}{t('montase.ai.periksa_balasan')}
              </button>
            </li>
          </ol>
        )}
        {(kerja.active || kerja.error) && <JobProgress job={kerja.job} error={kerja.error} onCancel={kerja.cancel} compact />}
        {hasil && (
          <KartuHasil versi={hasil} token={token} mode={mode} onTambah={tambah} onSimpan={simpan} onRevisi={revisi}
                      semuaVersi={semuaVersi}
                      onVersi={(n) => { const v = semuaVersi.find((x) => x.versi === n); if (v) setHasil(v); }} />
        )}
      </section>
    </div>
  );
}
