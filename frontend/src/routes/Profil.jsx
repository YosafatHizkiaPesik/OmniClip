import React, { useCallback, useEffect, useState, useRef } from 'react';
import {
  UserRound, Plus, Trash2, Check, FolderOpen, Sparkles, UploadCloud, Loader2, X,
  Users, BadgeCheck, MessageSquareQuote,
} from 'lucide-react';
import { useT } from '../lib/i18n';
import HalamanSetelan from '../components/HalamanSetelan';
import { apiDelete, apiGet, apiPatch, apiPost, pilihProfil, profilAktif } from '../lib/api';
import GoogleAccountCard from '../components/GoogleAccountCard';
import StatistikCard from '../components/StatistikCard';
import TambahAkun from '../components/TambahAkun';
import GayaKomentar from '../components/GayaKomentar';
import IdentitasKanal from '../components/IdentitasKanal';

const card = { padding: '18px 20px', borderBottom: '1px solid var(--rule-2)' };
const sectionTitle = {
  display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.95rem',
  fontWeight: 800, color: 'var(--text-primary)', marginBottom: '6px',
};
const helpText = { fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.6 };
const masukan = {
  padding: '8px 10px', fontSize: '0.8rem', fontFamily: 'inherit',
  borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)',
  background: 'transparent', color: 'var(--ink)',
};
const WARNA = ['#E0473A', '#7C3AED', '#0EA5E9', '#16A34A', '#F59E0B', '#DB2777', '#475569'];

/**
 * Lencana profil: foto akun Google-nya, atau huruf depan namanya.
 *
 * Diminta pemiliknya 1 Oktober 2026: "daripada profilenya logonya hanya huruf
 * kapital saja mengapa tidak ambil informasi foto akun google".
 *
 * Fotonya dimuat langsung dari lh3.googleusercontent.com, jadi satu permintaan
 * memang keluar dari mesin ini. Yang dikirim cuma alamat gambarnya sendiri,
 * tanpa kuki (`referrerPolicy="no-referrer"`), dan hanya untuk akun yang
 * memang sudah tersambung ke Google atas kemauan pemiliknya.
 *
 * Huruf depannya TIDAK dibuang. Gambar yang gagal dimuat — luring, alamat
 * kedaluwarsa, foto akun dihapus — jatuh kembali ke huruf, bukan ke lingkaran
 * kosong.
 */
export function Lencana({ profil, ukuran = 26 }) {
  const [gagal, setGagal] = React.useState(false);
  const foto = (profil?.foto || '').trim();
  React.useEffect(() => { setGagal(false); }, [foto]);
  const dasar = {
    width: ukuran, height: ukuran, borderRadius: '50%', flexShrink: 0,
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    background: profil?.warna || '#E0473A', color: '#fff',
    fontSize: ukuran * 0.46, fontWeight: 800, overflow: 'hidden',
  };
  if (foto && !gagal) {
    return (
      <span aria-hidden style={dasar}>
        <img src={foto} alt="" width={ukuran} height={ukuran}
             referrerPolicy="no-referrer" onError={() => setGagal(true)}
             style={{ width: '100%', height: '100%', objectFit: 'cover',
                      display: 'block' }} />
      </span>
    );
  }
  return (
    <span aria-hidden style={dasar}>
      {(profil?.nama || '?').trim().charAt(0).toUpperCase()}
    </span>
  );
}

function PilihWarna({ nilai, onChange }) {
  const t = useT();
  return (
    <div style={{ display: 'flex', gap: '6px' }}>
      {WARNA.map((w) => (
        <button key={w} type="button" onClick={() => onChange(w)} aria-label={t('akun.warna_n', { w })}
                style={{ width: 22, height: 22, borderRadius: '50%', background: w, cursor: 'pointer',
                         border: nilai === w ? '2px solid var(--ink)' : '2px solid transparent' }} />
      ))}
    </div>
  );
}

/** Daftar kata kunci yang bisa ditambah/dibuang satu per satu. */
function DaftarKata({ nilai, onChange, contoh }) {
  const t = useT();
  const [draf, setDraf] = useState('');
  const tambah = () => {
    const k = draf.trim();
    if (!k || nilai.some((x) => x.toLowerCase() === k.toLowerCase())) { setDraf(''); return; }
    onChange([...nilai, k]);
    setDraf('');
  };
  return (
    <div>
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: nilai.length ? '8px' : 0 }}>
        {nilai.map((k) => (
          <span key={k} className="chip is-on" style={{ display: 'inline-flex', gap: '5px', alignItems: 'center' }}>
            {k}
            <button type="button" onClick={() => onChange(nilai.filter((x) => x !== k))}
                    aria-label={t('akun.buang_n', { k })}
                    style={{ background: 'none', border: 0, cursor: 'pointer', color: 'inherit', padding: 0 }}>
              <X size={12} />
            </button>
          </span>
        ))}
      </div>
      <div style={{ display: 'flex', gap: '6px' }}>
        <input value={draf} onChange={(e) => setDraf(e.target.value)} placeholder={contoh}
               onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); tambah(); } }}
               style={{ ...masukan, flex: 1 }} />
        <button type="button" className="btn-secondary" onClick={tambah}>{t('akun.tambah')}</button>
      </div>
    </div>
  );
}

/**
 * Profil: satu akun Google, satu folder klip, satu minat.
 *
 * Pemiliknya ingin banyak akun Google — Drive yang lebih lega, dan tiap akun
 * fokus ke satu jenis konten — dengan hasil, riwayat pencarian, dan beranda
 * yang ikut berpindah bersama profilnya. Semua yang tampil di halaman ini
 * milik profil AKTIF; berpindah profil memuat ulang aplikasi.
 */
export default function Profil() {
  const t = useT();
  const [data, setData] = useState(null);
  const [galat, setGalat] = useState(null);
  const [simpan, setSimpan] = useState(null);     // pesan singkat
  const [sibuk, setSibuk] = useState(false);
  const [baru, setBaru] = useState({ nama: '', warna: WARNA[1], minat: [] });
  const [draf, setDraf] = useState(null);         // salinan profil aktif yang sedang diubah
  const [tanpaAkun, setTanpaAkun] = useState(false);

  const muat = useCallback(async () => {
    try {
      const r = await apiGet('/profil');
      setData(r);
      const aktif = (r.profil ?? []).find((p) => p.id === r.aktif) ?? r.profil?.[0];
      setDraf(aktif ? JSON.parse(JSON.stringify(aktif)) : null);
    } catch (e) {
      setGalat(e.message);
    }
  }, []);
  useEffect(() => { muat(); }, [muat]);

  const aktif = data?.profil?.find((p) => p.id === data.aktif);

  const simpanDraf = async () => {
    if (!draf) return;
    setSibuk(true); setGalat(null);
    try {
      await apiPatch(`/profil/${draf.id}`,
        { nama: draf.nama, warna: draf.warna, minat: draf.minat, unggah: draf.unggah });
      setSimpan(t('akun.tersimpan'));
      setTimeout(() => setSimpan(null), 2500);
      await muat();
    } catch (e) {
      setGalat(e.message);
    } finally {
      setSibuk(false);
    }
  };

  /**
   * Perubahan di halaman ini tersimpan SENDIRI.
   *
   * Dulu tidak: nama, warna, minat, dan seluruh bagian unggah hidup sebagai
   * draf di peramban sampai tombol "Simpan profil" ditekan, dan tidak ada
   * tanda apa pun bahwa ada yang belum tersimpan. Ditanyakan pemiliknya
   * 9 Oktober 2026: "untuk apa tombol simpan jika sudah otomatis tersimpan
   * profilnya". Ia mengira begitu karena seluruh halaman lain memang begitu,
   * dan dugaan itulah yang seharusnya benar.
   *
   * Ditunda 800 milidetik: mengetik nama tidak boleh berarti satu permintaan
   * per huruf. Draf yang baru dimuat dilewati, supaya membuka halaman ini
   * tidak langsung menulis ulang apa yang baru saja dibacanya.
   */
  // Cap perubahan terakhir yang SUDAH tersimpan, per akun.
  const tersimpanRef = useRef({ id: null, cap: '' });

  const capDraf = (d) => JSON.stringify(
    { nama: d.nama, warna: d.warna, minat: d.minat, unggah: d.unggah });

  useEffect(() => {
    if (!draf) return undefined;
    const cap = capDraf(draf);
    // Akun yang baru dibuka: capnya dicatat apa adanya, tanpa menyimpan.
    // Tanpa ini, membuka halaman langsung menulis ulang apa yang baru dibaca.
    if (tersimpanRef.current.id !== draf.id) {
      tersimpanRef.current = { id: draf.id, cap };
      return undefined;
    }
    if (tersimpanRef.current.cap === cap) return undefined;
    const jeda = setTimeout(async () => {
      try {
        await apiPatch(`/profil/${draf.id}`,
          { nama: draf.nama, warna: draf.warna, minat: draf.minat, unggah: draf.unggah });
        tersimpanRef.current = { id: draf.id, cap };
        setGalat(null);
        setSimpan(t('akun.tersimpan'));
        setTimeout(() => setSimpan(null), 1800);
      } catch (e) {
        setGalat(e.message);
      }
    }, 800);
    return () => clearTimeout(jeda);
  }, [draf]);

  const buat = async () => {
    if (!baru.nama.trim()) return;
    setSibuk(true); setGalat(null);
    try {
      const p = await apiPost('/profil', baru);
      pilihProfil(p.id);   // langsung masuk ke profil baru
    } catch (e) {
      setGalat(e.message);
      setSibuk(false);
    }
  };

  const hapus = async (p) => {
    if (!window.confirm(t('akun.yakin_hapus', { nama: p.nama, folder: p.folder_klip }))) return;
    setSibuk(true);
    try {
      await apiDelete(`/profil/${p.id}`);
      if (p.id === profilAktif()) pilihProfil(1);
      else await muat();
    } catch (e) {
      setGalat(e.message);
    } finally {
      setSibuk(false);
    }
  };

  // Keterangan panjang dilipat secara BAWAAN.
  //
  // Halaman ini punya 2018 kata saat semuanya terbuka, dan hampir semuanya
  // penjelasan yang hanya perlu dibaca sekali. Yang dipakai tiap hari cuma
  // sakelar dan kotak isiannya. Pilihannya diingat, jadi yang memang ingin
  // membaca tidak perlu menekannya berulang kali.
  const [ringkas, setRingkas] = useState(
    () => localStorage.getItem('omniclip_setelan_ringkas') !== '0');
  const ubahRingkas = () => setRingkas((r) => {
    const n = !r;
    try { localStorage.setItem('omniclip_setelan_ringkas', n ? '1' : '0'); } catch { /* mode privat */ }
    return n;
  });

  if (!data) {
    return (
      <div className="page" style={{ maxWidth: '1280px' }}>
        {galat ? <p className="bantu" style={helpText}>{galat}</p> : <Loader2 className="animate-spin" size={20} />}
      </div>
    );
  }

  const ubahUnggah = (patch) => setDraf((d) => ({ ...d, unggah: { ...d.unggah, ...patch } }));
  const u = draf?.unggah ?? {};

  const tombolTeks = {
    background: 'none', border: 0, cursor: 'pointer', padding: 0,
    fontSize: '0.76rem', fontFamily: 'inherit', color: 'var(--text-muted)',
  };
  const pilihan = { ...masukan, padding: '6px 9px' };

  // Keadaan simpan otomatis, tampil di kepala halaman supaya terlihat dari
  // bagian mana pun. Halaman ini tidak punya tombol Simpan.
  const keadaan = (
    <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
      {galat ? (
        <span style={{ ...helpText, color: 'var(--danger)' }}>
          {t('akun.gagal_simpan', { pesan: galat })}{' '}
          <button className="btn-secondary" style={{ fontSize: '.75rem' }}
                  onClick={simpanDraf} disabled={sibuk}>
            {sibuk ? <Loader2 size={13} className="animate-spin" /> : null}
            {t('akun.coba_simpan')}
          </button>
        </span>
      ) : (
        <span style={{ ...helpText, display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
          <Check size={14} style={{ color: 'var(--ok, var(--accent-cyan))' }} />
          {simpan || t('akun.otomatis_tersimpan')}
        </span>
      )}
      <button className="tombol-ringkas" onClick={ubahRingkas}
              title={ringkas ? t('setelan.penjelasan_judul') : t('setelan.ringkas_judul')}>
        {ringkas ? t('setelan.tampil_penjelasan') : t('setelan.ringkas')}
      </button>
    </div>
  );

  const daftarAkun = (
    <>
      <div style={card}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
          {data.profil.map((p) => (
            <div key={p.id} style={{
              display: 'flex', alignItems: 'center', gap: '10px', padding: '9px 11px',
              borderRadius: 'var(--radius-md)',
              border: p.id === data.aktif ? '1px solid var(--border-active)' : '1px solid var(--border-color)',
              background: p.id === data.aktif ? 'var(--hl-wash)' : 'transparent',
            }}>
              <Lencana profil={p} ukuran={30} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 800, fontSize: '0.86rem' }}>{p.nama}</div>
                <div style={{ ...helpText, fontSize: '0.72rem' }}>
                  {p.google.connected ? p.google.email : t('akun.google_belum')}
                  {p.unggah?.otomatis ? t('akun.unggah_nyala') : ''}
                </div>
              </div>
              {p.id === data.aktif
                ? <span className="chip is-on" style={{ display: 'inline-flex', gap: '4px' }}><Check size={12} />{t('akun.aktif')}</span>
                : <button className="btn-secondary" onClick={() => pilihProfil(p.id)}>{t('akun.pakai')}</button>}
              {p.id !== 1 && (
                <button className="btn-secondary" onClick={() => hapus(p)} disabled={sibuk}
                        title={t('akun.hapus_judul')} aria-label={t('akun.hapus_n', { nama: p.nama })}>
                  <Trash2 size={14} />
                </button>
              )}
            </div>
          ))}
        </div>

        <div style={{ marginTop: '14px', paddingTop: '12px', borderTop: '1px dashed var(--rule-2)' }}>
          {/* Menambah akun berarti MASUK, bukan mengarang nama. Ruang kerja
              tanpa akun tetap bisa, sebagai jalan sampingan. */}
          {tanpaAkun ? (
            <>
              <div style={{ fontWeight: 800, fontSize: '0.82rem', marginBottom: '8px' }}>
                {t('akun.ruang_kerja')}
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                <input value={baru.nama} onChange={(e) => setBaru((b) => ({ ...b, nama: e.target.value }))}
                       placeholder={t('akun.nama_contoh')} maxLength={40}
                       style={{ ...masukan, flex: '1 1 200px' }} />
                <PilihWarna nilai={baru.warna} onChange={(w) => setBaru((b) => ({ ...b, warna: w }))} />
              </div>
              <div style={{ marginTop: '8px' }}>
                <DaftarKata nilai={baru.minat} onChange={(m) => setBaru((b) => ({ ...b, minat: m }))}
                            contoh={t('akun.minat_contoh')} />
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '10px' }}>
                <button className="btn-primary" onClick={buat} disabled={sibuk || !baru.nama.trim()}
                        style={{ display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
                  <Plus size={14} />{t('akun.buat')}
                </button>
                <button onClick={() => setTanpaAkun(false)} style={tombolTeks}>{t('umum.kembali')}</button>
              </div>
            </>
          ) : (
            <button onClick={() => setTanpaAkun(true)} style={tombolTeks}>{t('akun.buat_tanpa')}</button>
          )}
        </div>
      </div>

      <TambahAkun card={card} sectionTitle={sectionTitle} helpText={helpText}
                  onSelesai={() => window.location.reload()} />
    </>
  );

  const profilAktifIsi = draf && (
    <div style={card}>
      <div style={sectionTitle}><Lencana profil={draf} />{t('akun.aktif_n', { nama: aktif?.nama })}</div>
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', marginTop: '8px' }}>
        <input value={draf.nama} maxLength={40}
               onChange={(e) => setDraf((d) => ({ ...d, nama: e.target.value }))}
               style={{ ...masukan, flex: '1 1 200px' }} />
        <PilihWarna nilai={draf.warna} onChange={(w) => setDraf((d) => ({ ...d, warna: w }))} />
      </div>
      <div style={{ ...sectionTitle, fontSize: '0.84rem', marginTop: '16px' }}>
        <Sparkles size={15} style={{ color: 'var(--reh)' }} />{t('akun.minat')}
      </div>
      <p className="bantu" style={{ ...helpText, margin: '0 0 8px' }}>{t('akun.minat_ket')}</p>
      <DaftarKata nilai={draf.minat ?? []} onChange={(m) => setDraf((d) => ({ ...d, minat: m }))}
                  contoh={t('akun.minat_contoh2')} />
      <div style={{ ...helpText, marginTop: '12px', display: 'flex', gap: '6px', alignItems: 'flex-start' }}>
        <FolderOpen size={14} style={{ flexShrink: 0, marginTop: '3px' }} />
        <span>{t('akun.folder')} <code>{aktif?.folder_klip}</code></span>
      </div>
    </div>
  );

  // Kunci pembaca tayangan tinggal di sini, bukan di Pengaturan: ia kunci
  // untuk AKUN YouTube ini, bukan setelan cara klip dibuat.
  const googleIsi = (
    <>
      <GoogleAccountCard card={card} sectionTitle={sectionTitle} helpText={helpText} />
      <StatistikCard card={card} sectionTitle={sectionTitle} helpText={helpText} />
    </>
  );

  const unggahIsi = draf && (
    <div style={card}>
      <div style={sectionTitle}><UploadCloud size={18} style={{ color: 'var(--reh)' }} />{t('akun.unggah_judul')}</div>
      <p className="bantu" style={helpText}>{t('akun.unggah_ket')}</p>
      <label className="studio-check" style={{ marginTop: '10px' }}>
        <input type="checkbox" checked={!!u.otomatis} onChange={(e) => ubahUnggah({ otomatis: e.target.checked })} />
        {t('akun.unggah_nyalakan')}
      </label>
      <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap', marginTop: '8px', opacity: u.otomatis ? 1 : 0.55 }}>
        <label className="studio-check">
          <input type="checkbox" checked={!!u.youtube} onChange={(e) => ubahUnggah({ youtube: e.target.checked })} />
          YouTube
        </label>
        <label className="studio-check">
          <input type="checkbox" checked={!!u.drive} onChange={(e) => ubahUnggah({ drive: e.target.checked })} />
          Google Drive
        </label>
      </div>
      {/* Empat pilihan unggahan dalam kisi dua kolom: sebelumnya berderet
          dalam satu baris yang membungkus tak beraturan. */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
                    gap: '8px', marginTop: '10px', opacity: u.otomatis ? 1 : 0.55 }}>
        <select value={u.privasi || 'private'} onChange={(e) => ubahUnggah({ privasi: e.target.value })}
                style={pilihan}>
          <option value="private">{t('akun.yt_pribadi')}</option>
          <option value="unlisted">{t('akun.yt_tidak_publik')}</option>
          <option value="public">{t('akun.yt_publik')}</option>
        </select>
        <select value={u.jadwal_jam ?? 0}
                onChange={(e) => ubahUnggah({ jadwal_jam: Number(e.target.value) })}
                title={t('akun.jarak_judul')} style={pilihan}>
          <option value={0}>{t('akun.jarak_0')}</option>
          <option value={1}>{t('akun.jarak_1')}</option>
          <option value={3}>{t('akun.jarak_3')}</option>
          <option value={6}>{t('akun.jarak_6')}</option>
          <option value={12}>{t('akun.jarak_12')}</option>
          <option value={24}>{t('akun.jarak_24')}</option>
        </select>
        {/* Batas unggahan YouTube per hari (JOB-2 F0-5). Kelebihannya
            dijadwalkan ke hari berikutnya, bukan ditolak. */}
        <select value={u.batas_harian ?? 3}
                onChange={(e) => ubahUnggah({ batas_harian: Number(e.target.value) })}
                title={t('akun.batas_judul')} style={pilihan}>
          <option value={1}>{t('akun.maks_1')}</option>
          <option value={2}>{t('akun.maks_n', { n: 2 })}</option>
          <option value={3}>{t('akun.maks_n', { n: 3 })}</option>
          <option value={5}>{t('akun.maks_n', { n: 5 })}</option>
          <option value={0}>{t('akun.tanpa_batas')}</option>
        </select>
        {/* Kategori YouTube (JOB-2 F0-6). */}
        <select value={u.kategori ?? 'otomatis'}
                onChange={(e) => ubahUnggah({ kategori: e.target.value })}
                title={t('akun.kategori_judul')} style={pilihan}>
          <option value="otomatis">{t('akun.kat_otomatis')}</option>
          <option value="24">{t('akun.kat_hiburan')}</option>
          <option value="20">{t('akun.kat_game')}</option>
          <option value="23">{t('akun.kat_komedi')}</option>
          <option value="22">{t('akun.kat_blog')}</option>
          <option value="27">{t('akun.kat_pendidikan')}</option>
          <option value="25">{t('akun.kat_berita')}</option>
          <option value="17">{t('akun.kat_olahraga')}</option>
        </select>
      </div>
      <div style={{ ...helpText, marginTop: '14px', marginBottom: '4px' }}>
        {t('akun.deskripsi_a')} <code>{'{judul}'}</code>, <code>{'{sumber}'}</code>, {t('akun.deskripsi_b')}{' '}
        <code>{'{hashtag}'}</code> {t('akun.deskripsi_c')} <code>{'{sumber}'}</code> {t('akun.deskripsi_d')}
      </div>
      <textarea value={u.deskripsi ?? ''} rows={3} maxLength={4000}
                onChange={(e) => ubahUnggah({ deskripsi: e.target.value })}
                style={{ ...masukan, width: '100%', resize: 'vertical' }} />
      {/* JOB-2 F0-2 dan F0-7. Keduanya menyala bawaannya. */}
      <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap', marginTop: '8px' }}>
        <label className="studio-check" title={t('akun.kredit_judul')}>
          <input type="checkbox" checked={u.kredit !== false}
                 onChange={(e) => ubahUnggah({ kredit: e.target.checked })} />
          {t('akun.kredit')}
        </label>
        <label className="studio-check" title={t('akun.sintetis_judul')}>
          <input type="checkbox" checked={u.label_sintetis !== false}
                 onChange={(e) => ubahUnggah({ label_sintetis: e.target.checked })} />
          {t('akun.sintetis')}
        </label>
      </div>
      <div style={{ ...helpText, marginTop: '12px', marginBottom: '4px' }}>{t('akun.hashtag')}</div>
      <DaftarKata nilai={u.hashtag ?? []} onChange={(h) => ubahUnggah({ hashtag: h })} contoh="#shorts" />
      <p className="bantu" style={{ ...helpText, marginTop: '12px' }}>
        {t('akun.catatan_google_a')} <b>{t('akun.catatan_google_b')}</b>{t('akun.catatan_google_c')}
      </p>
    </div>
  );

  const kanalIsi = (
    <div style={card}>
      <GayaKomentar style={masukan} bantu={helpText} />
      <IdentitasKanal style={masukan} bantu={helpText} />
    </div>
  );

  return (
    <HalamanSetelan
      kelas={ringkas ? 'ringkas' : ''}
      judul={t('akun.judul')}
      sub={t('akun.sub')}
      aksi={keadaan}
      bagian={[
        { id: 'akun', judul: t('akun.b_daftar'), nota: t('akun.b_daftar_nota'), Ikon: Users, isi: daftarAkun },
        draf && { id: 'profil', judul: t('akun.b_profil'), nota: t('akun.b_profil_nota'), Ikon: UserRound, isi: profilAktifIsi },
        { id: 'google', judul: t('akun.b_google'), nota: t('akun.b_google_nota'), Ikon: BadgeCheck, isi: googleIsi },
        draf && { id: 'unggah', judul: t('akun.b_unggah'), nota: t('akun.b_unggah_nota'), Ikon: UploadCloud, isi: unggahIsi },
        { id: 'kanal', judul: t('akun.b_kanal'), nota: t('akun.b_kanal_nota'), Ikon: MessageSquareQuote, isi: kanalIsi },
      ]}
    />
  );
}
