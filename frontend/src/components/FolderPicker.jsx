import React, { useEffect, useRef, useState } from 'react';
import {
  AlertTriangle, ChevronRight, CornerLeftUp, Folder, FolderPlus, HardDrive,
  Home, Loader2, Monitor, Film,
} from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';

const IKON = { Home, Desktop: Monitor };

/**
 * Dialog memilih folder, disusun seperti dialog berkas sistem.
 *
 * Bentuknya sengaja meniru yang sudah dikenal orang — daftar tempat di kiri,
 * isi folder di kanan, jejak jalur di atas, tombol pilih di kanan bawah —
 * karena di dialog semacam ini orang tidak membaca apa pun: mereka mencari
 * bentuk yang sudah mereka hafal. Susunan yang benar tapi asing memaksa
 * membaca, dan membaca di tengah pekerjaan lain terasa seperti hambatan.
 *
 * Daftarnya datang dari backend, bukan dari peramban: peramban tidak pernah
 * memberi halaman web jalur berkas sungguhan. `<input webkitdirectory>` memberi
 * nama berkas DI DALAM folder, bukan letak foldernya, dan `showDirectoryPicker`
 * memberi pegangan yang tidak bisa dipakai ffmpeg. Dialog milik sistem operasi
 * juga bukan jawaban: ia muncul di komputer yang menjalankan backend, bukan di
 * perangkat yang sedang dipakai.
 */
// `modeVideo`: memilih SATU berkas video, bukan folder. Dipakai impor video
// dari komputer ini — berkasnya dibaca di tempatnya, tanpa disalin.
export default function FolderPicker({ judul, awal, onPilih, onTutup, modeVideo = false }) {
  const [isi, setIsi] = useState(null);
  const [galat, setGalat] = useState(null);
  const [sibuk, setSibuk] = useState(false);
  const [terpilih, setTerpilih] = useState(null);
  const [buatNama, setBuatNama] = useState('');
  const [sedangBuat, setSedangBuat] = useState(false);
  const daftarRef = useRef(null);

  const buka = async (jalur) => {
    setSibuk(true);
    setGalat(null);
    try {
      setIsi(await apiGet(`/settings/jelajah?jalur=${encodeURIComponent(jalur || '')}`
        + (modeVideo ? '&video=true' : '')));
      setTerpilih(null);
      setSedangBuat(false);
      setBuatNama('');
      if (daftarRef.current) daftarRef.current.scrollTop = 0;
    } catch (err) {
      setGalat(err.message);
    } finally {
      setSibuk(false);
    }
  };

  useEffect(() => { buka(awal || ''); /* eslint-disable-next-line */ }, []);

  useEffect(() => {
    const esc = (e) => { if (e.key === 'Escape') onTutup(); };
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [onTutup]);

  const buat = async (e) => {
    e.preventDefault();
    if (!buatNama.trim()) return;
    setSibuk(true);
    setGalat(null);
    try {
      const r = await apiPost('/settings/jelajah/buat', { induk: isi.jalur, nama: buatNama.trim() });
      await buka(r.jalur);
    } catch (err) {
      setGalat(err.message);
      setSibuk(false);
    }
  };

  // Jejak jalur yang bisa diklik, seperti bilah alamat pengelola berkas.
  const remah = () => {
    if (!isi?.jalur) return null;
    const pisah = isi.jalur.split('/').filter(Boolean);
    const potong = pisah.length > 4 ? pisah.slice(-4) : pisah;
    const lewat = pisah.length > 4;
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '2px', flexWrap: 'wrap',
                    fontSize: '0.76rem', minWidth: 0 }}>
        <button onClick={() => buka('/')} style={remahBtn} title="Akar">/</button>
        {lewat && <span style={{ color: 'var(--text-muted)' }}>…</span>}
        {potong.map((nama, i) => {
          const jalur = '/' + pisah.slice(0, pisah.length - potong.length + i + 1).join('/');
          const akhir = i === potong.length - 1;
          return (
            <React.Fragment key={jalur}>
              <ChevronRight size={12} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
              <button onClick={() => buka(jalur)} disabled={akhir}
                      style={{ ...remahBtn, fontWeight: akhir ? 700 : 500,
                               color: akhir ? 'var(--text-primary)' : 'var(--accent-cyan)',
                               cursor: akhir ? 'default' : 'pointer' }}>
                {nama}
              </button>
            </React.Fragment>
          );
        })}
      </div>
    );
  };

  const tujuan = terpilih || isi?.jalur;

  return (
    <div
      onClick={(e) => { if (e.target === e.currentTarget) onTutup(); }}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000, display: 'flex',
        alignItems: 'center', justifyContent: 'center', padding: '20px',
        background: 'rgba(0,0,0,0.55)',
      }}
    >
      <div style={{
        width: 'min(760px, 100%)', height: 'min(520px, 88vh)', display: 'flex',
        flexDirection: 'column', background: 'var(--bg-card, #fff)',
        border: '1px solid var(--border-color)', borderRadius: 'var(--radius-lg, 12px)',
        overflow: 'hidden', boxShadow: '0 18px 48px rgba(0,0,0,0.32)',
      }}>
        {/* Bilah judul + jejak jalur */}
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--rule-2, var(--border-color))' }}>
          <strong style={{ fontSize: '0.88rem' }}>{judul}</strong>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px' }}>
            <button onClick={() => isi?.induk && buka(isi.induk)}
                    disabled={!isi?.induk || sibuk} style={ikonBtn} title="Naik satu tingkat">
              <CornerLeftUp size={15} />
            </button>
            <div style={{ flex: 1, minWidth: 0, overflowX: 'auto' }}>{remah()}</div>
            {sibuk && <Loader2 size={14} className="animate-spin" style={{ color: 'var(--text-muted)' }} />}
          </div>
        </div>

        {/* Dua panel: tempat di kiri, isi folder di kanan */}
        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
          <div style={{
            width: '190px', flexShrink: 0, overflowY: 'auto', padding: '8px 0',
            borderRight: '1px solid var(--rule-2, var(--border-color))',
            background: 'var(--plate-3, rgba(0,0,0,0.02))',
          }}>
            <div style={{ padding: '2px 14px 6px', fontSize: '0.68rem', fontWeight: 700,
                          letterSpacing: '0.04em', textTransform: 'uppercase',
                          color: 'var(--text-muted)' }}>
              Tempat
            </div>
            {(isi?.tempat_umum || []).map((t) => {
              const Ikon = t.nama.startsWith('Cakram') ? HardDrive : (IKON[t.nama] || Folder);
              const aktif = isi?.jalur === t.jalur;
              return (
                <button key={t.jalur} onClick={() => buka(t.jalur)} disabled={sibuk}
                        style={{ ...sisiBtn,
                                 background: aktif ? 'var(--hl-wash, rgba(0,0,0,0.05))' : 'transparent',
                                 fontWeight: aktif ? 700 : 500 }}>
                  <Ikon size={14} style={{ flexShrink: 0, color: 'var(--accent-cyan)' }} />
                  <span style={potongTeks}>{t.nama.replace('Cakram: ', '')}</span>
                </button>
              );
            })}
          </div>

          <div ref={daftarRef} style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
            {isi?.folder?.map((f) => {
              const aktif = terpilih === f.jalur;
              return (
                <button key={f.jalur}
                        onClick={() => setTerpilih(f.jalur)}
                        onDoubleClick={() => buka(f.jalur)}
                        disabled={sibuk}
                        style={{ ...barisBtn,
                                 background: aktif ? 'var(--hl-wash, rgba(0,0,0,0.06))' : 'transparent' }}>
                  <Folder size={15} style={{ flexShrink: 0, color: 'var(--accent-cyan)' }} />
                  <span style={{ ...potongTeks, flex: 1, textAlign: 'left' }}>{f.nama}</span>
                  <ChevronRight size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                </button>
              );
            })}
            {modeVideo && isi?.berkas?.map((f) => {
              const aktif = terpilih === f.jalur;
              return (
                <button key={f.jalur}
                        onClick={() => setTerpilih(f.jalur)}
                        onDoubleClick={() => onPilih(f.jalur)}
                        disabled={sibuk}
                        style={{ ...barisBtn,
                                 background: aktif ? 'var(--hl-wash, rgba(0,0,0,0.06))' : 'transparent' }}>
                  <Film size={15} style={{ flexShrink: 0, color: 'var(--reh, var(--accent-red))' }} />
                  <span style={{ ...potongTeks, flex: 1, textAlign: 'left' }}>{f.nama}</span>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', flexShrink: 0 }}>
                    {f.mb} MB
                  </span>
                </button>
              );
            })}
            {isi && !isi.folder.length && !(modeVideo && isi.berkas?.length) && (
              <p style={{ padding: '18px 16px', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                {modeVideo ? 'Tidak ada video di folder ini.' : 'Folder ini kosong. Ia tetap bisa dipilih.'}
              </p>
            )}
          </div>
        </div>

        {galat && (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', padding: '8px 14px',
                        fontSize: '0.77rem', color: 'var(--accent-red, var(--danger))',
                        borderTop: '1px solid var(--rule-2, var(--border-color))' }}>
            <AlertTriangle size={14} style={{ flexShrink: 0 }} /> {galat}
          </div>
        )}

        {/* Bilah bawah: nama folder tujuan + tombol, seperti dialog sistem */}
        <div style={{ borderTop: '1px solid var(--rule-2, var(--border-color))',
                      padding: '10px 14px', display: 'flex', alignItems: 'center',
                      gap: '10px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)', flexShrink: 0 }}>
            {modeVideo ? 'Video' : 'Folder'}
          </span>
          <code style={{ flex: '1 1 220px', minWidth: 0, fontSize: '0.75rem',
                         padding: '6px 9px', borderRadius: 'var(--radius-sm, 6px)',
                         background: 'var(--plate-3, rgba(0,0,0,0.04))',
                         border: '1px solid var(--border-color)',
                         whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {tujuan || '…'}
          </code>
          {modeVideo ? null : sedangBuat ? (
            <form onSubmit={buat} style={{ display: 'flex', gap: '6px' }}>
              <input autoFocus value={buatNama} onChange={(e) => setBuatNama(e.target.value)}
                     placeholder="Nama folder baru" style={kolom} />
              <button type="submit" className="btn-secondary" disabled={sibuk || !buatNama.trim()}
                      style={{ fontSize: '0.78rem' }}>Buat</button>
            </form>
          ) : (
            <button className="btn-secondary" disabled={sibuk || !isi?.bisa_ditulis}
                    onClick={() => setSedangBuat(true)}
                    style={{ fontSize: '0.78rem' }} title="Buat folder baru di sini">
              <FolderPlus size={14} />
            </button>
          )}
          <button className="btn-secondary" onClick={onTutup} style={{ fontSize: '0.8rem' }}>
            Batal
          </button>
          {modeVideo ? (
            <button className="btn-primary"
                    disabled={sibuk || !terpilih || !(isi?.berkas ?? []).some((b) => b.jalur === terpilih)}
                    onClick={() => onPilih(terpilih)} style={{ fontSize: '0.8rem' }}>
              Pakai video ini
            </button>
          ) : (
            <button className="btn-primary" disabled={sibuk || !isi || !isi.bisa_ditulis}
                    onClick={() => onPilih(tujuan)} style={{ fontSize: '0.8rem' }}>
              Pilih folder
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

const potongTeks = {
  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
};

const sisiBtn = {
  display: 'flex', alignItems: 'center', gap: '9px', width: '100%',
  padding: '6px 14px', border: 'none', color: 'var(--text-primary)',
  fontSize: '0.79rem', fontFamily: 'inherit', cursor: 'pointer', textAlign: 'left',
};

const barisBtn = {
  display: 'flex', alignItems: 'center', gap: '10px', width: '100%',
  padding: '7px 14px', border: 'none', color: 'var(--text-primary)',
  fontSize: '0.82rem', fontFamily: 'inherit', cursor: 'pointer',
};

const remahBtn = {
  background: 'transparent', border: 'none', padding: '2px 4px',
  fontFamily: 'inherit', fontSize: '0.76rem', color: 'var(--accent-cyan)',
  cursor: 'pointer', whiteSpace: 'nowrap',
};

const ikonBtn = {
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  width: '28px', height: '28px', flexShrink: 0,
  border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm, 6px)',
  background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer',
};

const kolom = {
  width: '150px', padding: '6px 9px', fontSize: '0.78rem',
  background: 'var(--bg-card)', color: 'var(--text-primary)',
  border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm, 6px)',
  fontFamily: 'inherit', outline: 'none',
};
