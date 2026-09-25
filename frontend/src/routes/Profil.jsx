import React, { useCallback, useEffect, useState } from 'react';
import {
  UserRound, Plus, Trash2, Check, FolderOpen, Sparkles, UploadCloud, Loader2, X,
} from 'lucide-react';
import { apiDelete, apiGet, apiPatch, apiPost, pilihProfil, profilAktif } from '../lib/api';
import GoogleAccountCard from '../components/GoogleAccountCard';
import TambahAkun from '../components/TambahAkun';

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

/** Lingkaran berwarna dengan huruf depan nama profil. */
export function Lencana({ profil, ukuran = 26 }) {
  return (
    <span aria-hidden style={{
      width: ukuran, height: ukuran, borderRadius: '50%', flexShrink: 0,
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      background: profil?.warna || '#E0473A', color: '#fff',
      fontSize: ukuran * 0.46, fontWeight: 800,
    }}>
      {(profil?.nama || '?').trim().charAt(0).toUpperCase()}
    </span>
  );
}

function PilihWarna({ nilai, onChange }) {
  return (
    <div style={{ display: 'flex', gap: '6px' }}>
      {WARNA.map((w) => (
        <button key={w} type="button" onClick={() => onChange(w)} aria-label={`Warna ${w}`}
                style={{ width: 22, height: 22, borderRadius: '50%', background: w, cursor: 'pointer',
                         border: nilai === w ? '2px solid var(--ink)' : '2px solid transparent' }} />
      ))}
    </div>
  );
}

/** Daftar kata kunci yang bisa ditambah/dibuang satu per satu. */
function DaftarKata({ nilai, onChange, contoh }) {
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
                    aria-label={`Buang ${k}`}
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
        <button type="button" className="btn-secondary" onClick={tambah}>Tambah</button>
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
      setSimpan('Tersimpan.');
      setTimeout(() => setSimpan(null), 2500);
      await muat();
    } catch (e) {
      setGalat(e.message);
    } finally {
      setSibuk(false);
    }
  };

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
    if (!window.confirm(`Hapus akun "${p.nama}" dari OmniClip?\n\nKlip yang sudah dirender TIDAK dihapus, tetap ada di:\n${p.folder_klip}\n\nYang diputus hanya sambungannya ke OmniClip; akun Google, TikTok, dan Meta Anda sendiri tidak disentuh.`)) return;
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

  if (!data) {
    return (
      <div className="page" style={{ maxWidth: '780px' }}>
        {galat ? <p style={helpText}>{galat}</p> : <Loader2 className="animate-spin" size={20} />}
      </div>
    );
  }

  const ubahUnggah = (patch) => setDraf((d) => ({ ...d, unggah: { ...d.unggah, ...patch } }));
  const u = draf?.unggah ?? {};

  return (
    <div className="page" style={{ maxWidth: '780px' }}>
      <div className="work-block">
        <div style={{ minWidth: 0 }}>
          <h1 className="work-title">Akun</h1>
          <div className="sub">
            Tiap akun punya folder klip, riwayat pencarian, beranda, dan kanal
            unggahannya sendiri, jadi satu akun bisa fokus pada satu jenis konten.
          </div>
        </div>
      </div>

      <div className="plate" style={{ overflow: 'hidden' }}>
        {/* --- Semua profil --- */}
        <div style={card}>
          <div style={sectionTitle}><UserRound size={18} style={{ color: 'var(--reh)' }} />Akun Anda</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '7px', marginTop: '8px' }}>
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
                    {p.google.connected ? p.google.email : 'Akun Google belum tersambung'}
                    {p.unggah?.otomatis ? ' · unggah otomatis menyala' : ''}
                  </div>
                </div>
                {p.id === data.aktif
                  ? <span className="chip is-on" style={{ display: 'inline-flex', gap: '4px' }}><Check size={12} />Aktif</span>
                  : <button className="btn-secondary" onClick={() => pilihProfil(p.id)}>Pakai</button>}
                {p.id !== 1 && (
                  <button className="btn-secondary" onClick={() => hapus(p)} disabled={sibuk}
                          title="Hapus akun dari OmniClip (klipnya tetap ada)" aria-label={`Hapus ${p.nama}`}>
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            ))}
          </div>

          <div style={{ marginTop: '14px', paddingTop: '12px', borderTop: '1px dashed var(--rule-2)' }}>
            {/* Menambah akun sekarang berarti MASUK, bukan mengarang nama.
                Membuat ruang kerja tanpa akun tetap bisa, tapi ia jalan
                sampingan, tanpa akun, klipnya tidak bisa diunggah ke mana
                pun, dan itu yang membuat pemiliknya bertanya "di mana saya
                menambahkan akun?". */}
            {tanpaAkun ? (
              <>
                <div style={{ fontWeight: 800, fontSize: '0.82rem', marginBottom: '8px' }}>
                  Ruang kerja tanpa akun
                </div>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                  <input value={baru.nama} onChange={(e) => setBaru((b) => ({ ...b, nama: e.target.value }))}
                         placeholder="Nama, mis. Horor atau Podcast" maxLength={40}
                         style={{ ...masukan, flex: '1 1 200px' }} />
                  <PilihWarna nilai={baru.warna} onChange={(w) => setBaru((b) => ({ ...b, warna: w }))} />
                </div>
                <div style={{ marginTop: '8px' }}>
                  <DaftarKata nilai={baru.minat} onChange={(m) => setBaru((b) => ({ ...b, minat: m }))}
                              contoh="Minat untuk beranda, mis. gameplay horor indonesia" />
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '10px' }}>
                  <button className="btn-primary" onClick={buat} disabled={sibuk || !baru.nama.trim()}
                          style={{ display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
                    <Plus size={14} />Buat dan pakai
                  </button>
                  <button onClick={() => setTanpaAkun(false)}
                          style={{ background: 'none', border: 0, cursor: 'pointer', padding: 0,
                                   fontSize: '0.76rem', fontFamily: 'inherit', color: 'var(--text-muted)' }}>
                    Kembali
                  </button>
                </div>
              </>
            ) : (
              <button onClick={() => setTanpaAkun(true)}
                      style={{ background: 'none', border: 0, cursor: 'pointer', padding: 0,
                               fontSize: '0.76rem', fontFamily: 'inherit', color: 'var(--text-muted)' }}>
                Buat ruang kerja tanpa akun Google
              </button>
            )}
          </div>
        </div>

        <TambahAkun card={card} sectionTitle={sectionTitle} helpText={helpText}
                    onSelesai={() => window.location.reload()} />

        {draf && (
          <>
            {/* --- Profil aktif: identitas dan minat --- */}
            <div style={card}>
              <div style={sectionTitle}><Lencana profil={draf} />Akun aktif: {aktif?.nama}</div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', marginTop: '8px' }}>
                <input value={draf.nama} maxLength={40}
                       onChange={(e) => setDraf((d) => ({ ...d, nama: e.target.value }))}
                       style={{ ...masukan, flex: '1 1 200px' }} />
                <PilihWarna nilai={draf.warna} onChange={(w) => setDraf((d) => ({ ...d, warna: w }))} />
              </div>
              <div style={{ ...sectionTitle, fontSize: '0.84rem', marginTop: '16px' }}>
                <Sparkles size={15} style={{ color: 'var(--reh)' }} />Minat untuk beranda
              </div>
              <p style={{ ...helpText, margin: '0 0 8px' }}>
                Beranda (halaman Cari video) dibuka dengan video dari kata kunci ini, lalu dari
                pencarian terakhir profil ini. Kosongkan untuk beranda umum.
              </p>
              <DaftarKata nilai={draf.minat ?? []} onChange={(m) => setDraf((d) => ({ ...d, minat: m }))}
                          contoh="mis. podcast bisnis indonesia" />
              <div style={{ ...helpText, marginTop: '12px', display: 'flex', gap: '6px', alignItems: 'flex-start' }}>
                <FolderOpen size={14} style={{ flexShrink: 0, marginTop: '3px' }} />
                <span>Klip hasil render profil ini tersimpan di <code>{aktif?.folder_klip}</code></span>
              </div>
            </div>

            {/* --- Akun Google profil aktif --- */}
            <GoogleAccountCard card={card} sectionTitle={sectionTitle} helpText={helpText} />

            {/* --- Unggah otomatis --- */}
            <div style={card}>
              <div style={sectionTitle}><UploadCloud size={18} style={{ color: 'var(--reh)' }} />Unggah otomatis setelah render</div>
              <p style={helpText}>
                Klip yang selesai dirender langsung diantrekan ke akun Google profil ini, tetap
                berjalan walau halaman Studio sudah ditutup. Unggahan diberi jeda antar video
                supaya kanal tidak terlihat seperti bot.
              </p>
              <label className="studio-check" style={{ marginTop: '10px' }}>
                <input type="checkbox" checked={!!u.otomatis} onChange={(e) => ubahUnggah({ otomatis: e.target.checked })} />
                Nyalakan unggah otomatis
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
                <select value={u.privasi || 'private'} onChange={(e) => ubahUnggah({ privasi: e.target.value })}
                        style={{ ...masukan, padding: '5px 8px' }}>
                  <option value="private">YouTube: Pribadi</option>
                  <option value="unlisted">YouTube: Tidak publik</option>
                  <option value="public">YouTube: Publik</option>
                </select>
                <select value={u.jadwal_jam ?? 0}
                        onChange={(e) => ubahUnggah({ jadwal_jam: Number(e.target.value) })}
                        title="Jarak waktu antar unggahan. Sepuluh klip yang naik dalam sepuluh menit adalah pola yang membuat kanal ditandai."
                        style={{ ...masukan, padding: '5px 8px' }}>
                  <option value={0}>Naik langsung, semuanya</option>
                  <option value={1}>Berjarak 1 jam</option>
                  <option value={3}>Berjarak 3 jam</option>
                  <option value={6}>Berjarak 6 jam</option>
                  <option value={12}>Berjarak 12 jam</option>
                  <option value={24}>Berjarak 1 hari</option>
                </select>
              </div>
              <div style={{ ...helpText, marginTop: '12px', marginBottom: '4px' }}>
                Deskripsi video. <code>{'{judul}'}</code> dan <code>{'{hashtag}'}</code> diganti otomatis:
              </div>
              <textarea value={u.deskripsi ?? ''} rows={3} maxLength={4000}
                        onChange={(e) => ubahUnggah({ deskripsi: e.target.value })}
                        style={{ ...masukan, width: '100%', resize: 'vertical' }} />
              <div style={{ ...helpText, marginTop: '10px', marginBottom: '4px' }}>
                Hashtag yang selalu ditambahkan (hashtag klip ikut di belakangnya):
              </div>
              <DaftarKata nilai={u.hashtag ?? []} onChange={(h) => ubahUnggah({ hashtag: h })} contoh="#shorts" />
              <p style={{ ...helpText, marginTop: '10px' }}>
                Catatan dari Google: selama aplikasi OAuth Anda belum lolos audit, video yang
                diunggah lewat API selalu berstatus <b>Pribadi</b>, dan kuota harian (±6 video per
                hari) dihitung per project Google Cloud, dibagi oleh semua profil.
              </p>
            </div>

            <div style={{ ...card, display: 'flex', gap: '10px', alignItems: 'center', borderBottom: 0 }}>
              <button className="btn-primary" onClick={simpanDraf} disabled={sibuk}>
                {sibuk ? <Loader2 size={14} className="animate-spin" /> : null}
                Simpan profil
              </button>
              {simpan && <span style={helpText}>{simpan}</span>}
              {galat && <span style={{ ...helpText, color: 'var(--danger)' }}>{galat}</span>}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
