import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, ChevronDown, Settings2 } from 'lucide-react';
import { apiGet, pilihProfil } from '../lib/api';
import { Lencana } from '../routes/Profil';

/**
 * Profil aktif, selalu terlihat di kepala aplikasi.
 *
 * Folder klip, akun Google tujuan unggah, riwayat pencarian, dan beranda
 * semuanya berganti bersama profil — jadi profil yang sedang dipakai tidak
 * boleh tersembunyi di halaman Pengaturan. Mengunggah ke kanal yang salah
 * adalah kesalahan yang tidak bisa diurungkan.
 */
export default function ProfilPemilih() {
  const [data, setData] = useState(null);
  const [buka, setBuka] = useState(false);
  const ref = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    apiGet('/profil').then(setData).catch(() => {});
  }, []);

  useEffect(() => {
    if (!buka) return undefined;
    const tutup = (e) => { if (!ref.current?.contains(e.target)) setBuka(false); };
    document.addEventListener('mousedown', tutup);
    return () => document.removeEventListener('mousedown', tutup);
  }, [buka]);

  const aktif = data?.profil?.find((p) => p.id === data.aktif);
  if (!aktif) return null;

  return (
    <div ref={ref} style={{ position: 'relative', marginRight: '12px' }}>
      <button onClick={() => setBuka((v) => !v)} aria-expanded={buka}
              title={aktif.google.connected ? `Profil ${aktif.nama} · ${aktif.google.email}` : `Profil ${aktif.nama}`}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '7px', cursor: 'pointer',
                padding: '3px 9px 3px 3px', borderRadius: '999px', fontFamily: 'inherit',
                // Kepala aplikasi selalu gelap (var(--stage)), di tema apa pun.
                fontSize: '0.78rem', fontWeight: 800, color: '#E7EDF5',
                background: 'rgba(255,255,255,.06)', border: '1px solid rgba(255,255,255,.18)',
              }}>
        <Lencana profil={aktif} ukuran={24} />
        <span style={{ maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {aktif.nama}
        </span>
        <ChevronDown size={13} />
      </button>
      {buka && (
        <div role="menu" style={{
          position: 'absolute', right: 0, top: 'calc(100% + 6px)', zIndex: 50, minWidth: '240px',
          background: 'var(--plate)', border: '1px solid var(--rule-2)',
          borderRadius: 'var(--radius-md)', boxShadow: '0 12px 32px rgba(0,0,0,.18)', padding: '6px',
        }}>
          {data.profil.map((p) => (
            <button key={p.id} role="menuitem"
                    onClick={() => (p.id === data.aktif ? setBuka(false) : pilihProfil(p.id))}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '9px', width: '100%',
                      padding: '7px 8px', border: 0, borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                      background: p.id === data.aktif ? 'var(--hl-wash)' : 'transparent',
                      color: 'var(--ink)', fontFamily: 'inherit', textAlign: 'left',
                    }}>
              <Lencana profil={p} ukuran={26} />
              <span style={{ flex: 1, minWidth: 0 }}>
                <span style={{ display: 'block', fontWeight: 800, fontSize: '0.8rem' }}>{p.nama}</span>
                <span style={{ display: 'block', fontSize: '0.7rem', color: 'var(--text-secondary)',
                               overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {p.google.connected ? p.google.email : 'Belum tersambung ke Google'}
                </span>
              </span>
              {p.id === data.aktif && <Check size={14} />}
            </button>
          ))}
          <button onClick={() => { setBuka(false); navigate('/profil'); }}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '8px', width: '100%', marginTop: '4px',
                    padding: '8px', border: 0, borderTop: '1px solid var(--rule-2)', cursor: 'pointer',
                    background: 'transparent', color: 'var(--text-secondary)', fontFamily: 'inherit',
                    fontSize: '0.78rem', fontWeight: 700,
                  }}>
            <Settings2 size={14} />Kelola profil
          </button>
        </div>
      )}
    </div>
  );
}
