import React, { useEffect, useState } from 'react';
import {
  AlertTriangle, CheckCircle2, DatabaseBackup, HardDrive, Loader2, Trash2,
} from 'lucide-react';
import { apiDelete, apiGet, apiPost } from '../lib/api';

import { tebal, useT, lokal } from '../lib/i18n';
const gb = (n) => (n >= 1e9 ? `${(n / 1e9).toFixed(2)} GB` : `${Math.round(n / 1e6)} MB`);
const tanggal = (detik) => new Date(detik * 1000).toLocaleString(lokal(),
  { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });

/**
 * Ruang cakram dan cadangan basis data.
 *
 * Dua hal yang tidak menarik sama sekali, dan keduanya baru terasa penting
 * pada hari yang buruk: cakram yang penuh di tengah render, dan basis data
 * yang hilang bersama seluruh pekerjaan berbulan-bulan.
 *
 * Kartu ini tidak membuang apa pun sendiri: daftar ini hanya menunjukkan mana
 * yang besar dan mana yang klipnya sudah jadi. Pembuangan otomatis (atas
 * permintaan pemiliknya, 28 Oktober 2026) ada di BersihOtomatisCard.jsx dan
 * baru berjalan sesudah disetujui di sana.
 */
export default function PemeliharaanCard({ card, sectionTitle, helpText }) {
  const t = useT();
  const [ruang, setRuang] = useState(null);
  const [cadangan, setCadangan] = useState([]);
  const [pilih, setPilih] = useState(new Set());
  const [sibuk, setSibuk] = useState(null);
  const [kabar, setKabar] = useState(null);

  // Kegagalannya disimpan terpisah dari `kabar`, karena kartunya harus bisa
  // menawarkan "Hitung ulang" di tempat angkanya seharusnya berada. Sebelum
  // ini, permintaan yang tidak pernah dijawab meninggalkan kata "Menghitung…"
  // selamanya, tanpa galat dan tanpa jalan keluar.
  const [gagalRuang, setGagalRuang] = useState(null);

  const muat = () => {
    setGagalRuang(null);
    apiGet('/settings/ruang').then((r) => { setRuang(r); setGagalRuang(null); })
      .catch((e) => setGagalRuang(e.message));
    apiGet('/settings/cadangan').then((r) => setCadangan(r.cadangan || [])).catch(() => {});
  };
  useEffect(() => { muat(); }, []);

  const toggle = (nama) => setPilih((s) => {
    const n = new Set(s);
    if (n.has(nama)) n.delete(nama); else n.add(nama);
    return n;
  });

  const buang = async () => {
    const daftar = [...pilih];
    if (!daftar.length) return;
    if (!window.confirm(
      t('pelihara.yakin_hapus', { n: daftar.length }))) return;
    setSibuk('buang');
    try {
      const r = await apiPost('/settings/ruang/buang', { folder: 'unduhan', berkas: daftar },
                              { timeout: 300000 });
      setKabar({ ok: true, teks: t('pelihara.dihapus', { n: r.dibuang, ukuran: gb(r.ukuran) }) });
      setPilih(new Set());
      muat();
    } catch (e) {
      setKabar({ ok: false, teks: e.message });
    } finally {
      setSibuk(null);
    }
  };

  const cadangkan = async () => {
    setSibuk('cadang');
    try {
      const r = await apiPost('/settings/cadangan', {}, { timeout: 180000 });
      setKabar({ ok: true, teks: t('pelihara.cadangan_dibuat', { berkas: r.berkas, ukuran: gb(r.ukuran) }) });
      muat();
    } catch (e) {
      setKabar({ ok: false, teks: e.message });
    } finally {
      setSibuk(null);
    }
  };

  const pulihkan = async (berkas) => {
    if (!window.confirm(
      t('pelihara.yakin_pulih', { berkas }))) return;
    setSibuk(berkas);
    try {
      const r = await apiPost('/settings/cadangan/pulihkan', { berkas });
      setKabar({ ok: true, teks: r.pesan });
    } catch (e) {
      setKabar({ ok: false, teks: e.message });
    } finally {
      setSibuk(null);
    }
  };

  const batal = async () => {
    try {
      await apiDelete('/settings/cadangan/pulihkan');
      setKabar({ ok: true, teks: t('pelihara.batal_pulih') });
    } catch (e) {
      setKabar({ ok: false, teks: e.message });
    }
  };

  const terpilih = [...pilih].reduce(
    (n, nama) => n + (ruang?.sumber?.find((s) => s.berkas === nama)?.ukuran || 0), 0);

  return (
    <div style={card}>
      <div style={sectionTitle}>
        <HardDrive size={18} style={{ color: 'var(--reh)' }} />
        {t('pelihara.judul')}
      </div>
      {ruang ? (
        <>
          <p className="bantu" style={helpText}>
            {t('pelihara.terpakai', { total: gb(ruang.total), sisa: gb(ruang.sisa_ruang) })}
          </p>

          {/* Usulan, bukan penghapus otomatis. Mengklip ulang video yang sudah
              dihapus berarti mengunduhnya lagi, dan mesin tidak tahu mana yang
              masih akan dipakai. Yang ditambahkan cuma PERTANYAANNYA, supaya
              ruang yang bisa kembali tidak perlu dicari sendiri di antara enam
              puluh baris. */}
          {ruang.usul?.jumlah > 0 && (
            <div style={{
              marginTop: '10px', padding: '10px 12px', fontSize: '0.78rem',
              borderRadius: 'var(--radius-sm, 8px)', lineHeight: 1.5,
              background: 'color-mix(in srgb, var(--accent-cyan) 10%, transparent)',
              border: '1px solid color-mix(in srgb, var(--accent-cyan) 30%, transparent)',
            }}>
              <b>{t('pelihara.usul', { n: ruang.usul.jumlah, ukuran: gb(ruang.usul.ukuran) })}</b>
              <div style={{ ...helpText, marginTop: '4px' }}>
                {t('pelihara.usul_ket', { hari: ruang.usul.syarat.umur_hari, besar: gb(ruang.usul.syarat.besar_min) })}
              </div>
              <button className="btn-secondary" style={{ marginTop: '8px', fontSize: '0.76rem' }}
                      onClick={() => setPilih(new Set(ruang.usul.berkas))}>
                {t('pelihara.tandai')}
              </button>
            </div>
          )}
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '9px' }}>
            {ruang.folder.filter((f) => f.ukuran > 0).map((f) => (
              <span key={f.nama} className="chip" style={{ fontSize: '0.68rem' }}>
                {f.nama} {gb(f.ukuran)}
              </span>
            ))}
          </div>

          <p style={{ ...helpText, marginTop: '12px' }}>
            {tebal(t('pelihara.terbesar'))}
          </p>
          <div style={{ maxHeight: '220px', overflowY: 'auto', marginTop: '8px' }}>
            {(ruang.sumber || []).map((s) => (
              <label key={s.berkas} style={{
                display: 'flex', gap: '8px', alignItems: 'center', padding: '5px 0',
                borderTop: '1px solid var(--border-color)', cursor: 'pointer',
              }}>
                <input type="checkbox" checked={pilih.has(s.berkas)}
                       onChange={() => toggle(s.berkas)}
                       style={{ accentColor: 'var(--accent-cyan)' }} />
                <span style={{ fontSize: '0.72rem', minWidth: '72px', fontWeight: 700 }}>
                  {gb(s.ukuran)}
                </span>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)',
                               overflow: 'hidden', textOverflow: 'ellipsis',
                               whiteSpace: 'nowrap', flex: 1 }}>
                  {s.berkas}
                </span>
                <span style={{ fontSize: '0.68rem', color: s.klip ? 'var(--entry)' : 'var(--text-muted)' }}>
                  {s.klip ? t('pelihara.n_klip', { n: s.klip }) : t('pelihara.belum_klip')}
                </span>
              </label>
            ))}
          </div>
          <button className="btn-secondary" onClick={buang}
                  disabled={!pilih.size || sibuk === 'buang'}
                  style={{ marginTop: '10px', fontSize: '0.78rem', display: 'inline-flex',
                           gap: '6px', alignItems: 'center',
                           opacity: pilih.size ? 1 : 0.5 }}>
            {sibuk === 'buang' ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
            {t('pelihara.hapus_terpilih', { n: pilih.size || '' })}{terpilih ? ` (${gb(terpilih)})` : ''}
          </button>
        </>
      ) : gagalRuang ? (
        <div style={{ ...helpText, display: 'flex', flexWrap: 'wrap', alignItems: 'center',
                      gap: '8px' }}>
          <AlertTriangle size={14} style={{ color: 'var(--accent-red)', flexShrink: 0 }} />
          <span style={{ flex: '1 1 220px', minWidth: 0 }}>{gagalRuang}</span>
          <button className="btn-secondary" onClick={muat} style={{ fontSize: '0.76rem' }}>
            {t('pelihara.hitung_ulang')}
          </button>
        </div>
      ) : <p className="bantu" style={helpText}>{t('pelihara.menghitung')}</p>}

      <div style={{ ...sectionTitle, marginTop: '20px' }}>
        <DatabaseBackup size={18} style={{ color: 'var(--reh)' }} />
        {t('pelihara.cadangan')}
      </div>
      <p className="bantu" style={helpText}>
        {t('pelihara.cadangan_ket')}
      </p>
      <button className="btn-primary" onClick={cadangkan} disabled={sibuk === 'cadang'}
              style={{ marginTop: '10px', fontSize: '0.78rem', display: 'inline-flex',
                       gap: '6px', alignItems: 'center' }}>
        {sibuk === 'cadang' ? <Loader2 size={14} className="animate-spin" /> : <DatabaseBackup size={14} />}
        {t('pelihara.cadangkan')}
      </button>

      {cadangan.length > 0 && (
        <div style={{ marginTop: '10px' }}>
          {cadangan.map((c) => (
            <div key={c.berkas} style={{
              display: 'flex', gap: '8px', alignItems: 'center', padding: '5px 0',
              borderTop: '1px solid var(--border-color)', fontSize: '0.73rem',
            }}>
              <span style={{ flex: 1, color: 'var(--text-secondary)' }}>
                {tanggal(c.waktu)} · {gb(c.ukuran)}
              </span>
              <button onClick={() => pulihkan(c.berkas)} disabled={sibuk === c.berkas}
                      style={{ background: 'none', border: 'none', cursor: 'pointer',
                               fontSize: '0.73rem', fontWeight: 700, fontFamily: 'inherit',
                               color: 'var(--reh)' }}>
                {sibuk === c.berkas ? t('pelihara.menyiapkan') : t('pelihara.pulihkan')}
              </button>
            </div>
          ))}
          <button onClick={batal}
                  style={{ marginTop: '8px', background: 'none', border: 'none',
                           cursor: 'pointer', padding: 0, fontSize: '0.72rem',
                           fontFamily: 'inherit', color: 'var(--text-muted)' }}>
            {t('pelihara.batalkan_pulih')}
          </button>
        </div>
      )}

      {kabar && (
        <div style={{
          ...helpText, marginTop: '12px', display: 'flex', alignItems: 'center', gap: '7px',
          color: kabar.ok ? 'var(--entry)' : 'var(--accent-red)',
        }}>
          {kabar.ok ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
          {kabar.teks}
        </div>
      )}
    </div>
  );
}
