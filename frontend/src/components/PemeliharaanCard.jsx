import React, { useEffect, useState } from 'react';
import {
  AlertTriangle, CheckCircle2, DatabaseBackup, HardDrive, Loader2, Trash2,
} from 'lucide-react';
import { apiDelete, apiGet, apiPost } from '../lib/api';

const gb = (n) => (n >= 1e9 ? `${(n / 1e9).toFixed(2)} GB` : `${Math.round(n / 1e6)} MB`);
const tanggal = (t) => new Date(t * 1000).toLocaleString('id-ID',
  { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });

/**
 * Ruang cakram dan cadangan basis data.
 *
 * Dua hal yang tidak menarik sama sekali, dan keduanya baru terasa penting
 * pada hari yang buruk: cakram yang penuh di tengah render, dan basis data
 * yang hilang bersama seluruh pekerjaan berbulan-bulan.
 *
 * Yang menghapus tetap orangnya. Video sumber tidak pernah dibuang sendiri,
 * karena mengklip ulang video yang sudah dihapus berarti mengunduhnya lagi —
 * daftar ini hanya menunjukkan mana yang besar dan mana yang klipnya sudah
 * jadi.
 */
export default function PemeliharaanCard({ card, sectionTitle, helpText }) {
  const [ruang, setRuang] = useState(null);
  const [cadangan, setCadangan] = useState([]);
  const [pilih, setPilih] = useState(new Set());
  const [sibuk, setSibuk] = useState(null);
  const [kabar, setKabar] = useState(null);

  const muat = () => {
    apiGet('/settings/ruang').then(setRuang).catch((e) => setKabar({ ok: false, teks: e.message }));
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
      `Hapus ${daftar.length} berkas video sumber?\n\nKlip yang sudah dirender TIDAK ikut terhapus. `
      + 'Untuk mengklip ulang videonya nanti, ia harus diunduh lagi.')) return;
    setSibuk('buang');
    try {
      const r = await apiPost('/settings/ruang/buang', { folder: 'unduhan', berkas: daftar });
      setKabar({ ok: true, teks: `${r.dibuang} berkas dihapus — ${gb(r.ukuran)} kembali.` });
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
      const r = await apiPost('/settings/cadangan', {});
      setKabar({ ok: true, teks: `Cadangan dibuat: ${r.berkas} (${gb(r.ukuran)}).` });
      muat();
    } catch (e) {
      setKabar({ ok: false, teks: e.message });
    } finally {
      setSibuk(null);
    }
  };

  const pulihkan = async (berkas) => {
    if (!window.confirm(
      `Pulihkan basis data dari ${berkas}?\n\nSemua analisis, klip, dan setelan akan kembali ke `
      + 'keadaan saat cadangan itu dibuat. Pertukarannya terjadi saat OmniClip dibuka berikutnya, '
      + 'dan keadaan sekarang tetap disimpan sebagai omniclip.db.sebelum-pulih.')) return;
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
      setKabar({ ok: true, teks: 'Rencana pemulihan dibatalkan.' });
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
        Ruang cakram
      </div>
      {ruang ? (
        <>
          <p style={helpText}>
            Terpakai {gb(ruang.total)}, sisa {gb(ruang.sisa_ruang)} di cakram ini.
          </p>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '9px' }}>
            {ruang.folder.filter((f) => f.ukuran > 0).map((f) => (
              <span key={f.nama} className="chip" style={{ fontSize: '0.68rem' }}>
                {f.nama} {gb(f.ukuran)}
              </span>
            ))}
          </div>

          <p style={{ ...helpText, marginTop: '12px' }}>
            Video sumber terbesar. <b>Klip</b> menunjukkan berapa klip jadi yang sudah
            dirender dari video itu — yang angkanya 0 dan sudah lama tidak dibuka
            biasanya sisa percobaan.
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
                  {s.klip ? `${s.klip} klip` : 'belum ada klip'}
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
            Hapus {pilih.size || ''} berkas terpilih{terpilih ? ` (${gb(terpilih)})` : ''}
          </button>
        </>
      ) : <p style={helpText}>Menghitung…</p>}

      <div style={{ ...sectionTitle, marginTop: '20px' }}>
        <DatabaseBackup size={18} style={{ color: 'var(--reh)' }} />
        Cadangan basis data
      </div>
      <p style={helpText}>
        Seluruh pekerjaan Anda — analisis, klip, transkrip, profil, dan setelan — ada
        di satu berkas. Cadangan dibuat dengan cara SQLite sendiri, bukan disalin
        begitu saja, supaya isinya utuh walau dibuat saat aplikasi sedang bekerja.
        Sepuluh cadangan terakhir disimpan.
      </p>
      <button className="btn-primary" onClick={cadangkan} disabled={sibuk === 'cadang'}
              style={{ marginTop: '10px', fontSize: '0.78rem', display: 'inline-flex',
                       gap: '6px', alignItems: 'center' }}>
        {sibuk === 'cadang' ? <Loader2 size={14} className="animate-spin" /> : <DatabaseBackup size={14} />}
        Cadangkan sekarang
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
                {sibuk === c.berkas ? 'Menyiapkan…' : 'Pulihkan'}
              </button>
            </div>
          ))}
          <button onClick={batal}
                  style={{ marginTop: '8px', background: 'none', border: 'none',
                           cursor: 'pointer', padding: 0, fontSize: '0.72rem',
                           fontFamily: 'inherit', color: 'var(--text-muted)' }}>
            Batalkan rencana pemulihan
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
