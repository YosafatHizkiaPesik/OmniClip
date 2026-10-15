import React, { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { History, Search, X } from 'lucide-react';
import { apiDelete, apiGet } from '../lib/api';
import { useT } from '../lib/i18n';

/**
 * Kotak cari di header, seperti YouTube dan Google (JOB-3 J3-2).
 *
 * Dipindahkan utuh dari Beranda: riwayat pencarian akun aktif tampil sebagai
 * dropdown yang menempel di bawah kotaknya, bisa dipilih dengan panah atas,
 * panah bawah, Enter, ditutup dengan Escape, dan tiap baris bisa dihapus.
 * Diminta pemiliknya: "buat search bar itu mirip milik youtube atau google
 * karena lebih bagus seperti itu dan clean". Hasilnya dibuka di Beranda lewat
 * `/?q=...`, jadi tombol back browser tetap mengembalikan pencarian lama.
 */
export default function KotakCari() {
  const t = useT();
  const navigate = useNavigate();
  const location = useLocation();
  const q = location.pathname === '/' ? (new URLSearchParams(location.search).get('q') ?? '') : null;
  const [draft, setDraft] = useState(q ?? '');
  const [riwayat, setRiwayat] = useState([]);
  const [cariAktif, setCariAktif] = useState(false);
  const [sorot, setSorot] = useState(-1);

  useEffect(() => { if (q !== null) setDraft(q); }, [q]);
  useEffect(() => {
    apiGet('/riwayat-cari').then((r) => setRiwayat(r.riwayat ?? [])).catch(() => {});
  }, [q]);

  const buangRiwayat = (kueri) => {
    setRiwayat((r) => r.filter((x) => x.query !== kueri));
    apiDelete(`/riwayat-cari?q=${encodeURIComponent(kueri)}`).catch(() => {});
  };

  // Riwayat yang cocok dengan yang sedang diketik; kosong = terbaru dulu.
  const saran = useMemo(() => {
    const k = draft.trim().toLowerCase();
    const cocok = k ? riwayat.filter((r) => r.query.toLowerCase().includes(k)
                                         && r.query.toLowerCase() !== k)
                    : riwayat;
    return cocok.slice(0, 8);
  }, [riwayat, draft]);
  useEffect(() => { setSorot(-1); }, [draft, cariAktif]);

  const buka = (kueri) => {
    const v = (kueri ?? '').trim();
    setCariAktif(false);
    navigate(v ? `/?q=${encodeURIComponent(v)}` : '/');
  };
  const pilihSaran = (kueri) => { setDraft(kueri); buka(kueri); };

  const tombolCari = (e) => {
    if (!cariAktif || !saran.length) {
      if (e.key === 'ArrowDown' && saran.length) { setCariAktif(true); e.preventDefault(); }
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSorot((i) => (i + 1) % saran.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSorot((i) => (i <= 0 ? saran.length - 1 : i - 1));
    } else if (e.key === 'Enter' && sorot >= 0) {
      e.preventDefault();
      pilihSaran(saran[sorot].query);
    } else if (e.key === 'Escape') {
      setCariAktif(false);
    }
  };

  return (
    <form className="header-cari" role="search" onSubmit={(e) => { e.preventDefault(); buka(draft); }}>
      <div className="cari-kotak">
        <input
          type="text"
          className="search-input"
          placeholder={t('header.cari')}
          aria-label={t('header.cari')}
          value={draft}
          role="combobox"
          aria-expanded={cariAktif && saran.length > 0}
          aria-controls="cari-saran"
          aria-activedescendant={sorot >= 0 ? `saran-${sorot}` : undefined}
          autoComplete="off"
          onChange={(e) => { setDraft(e.target.value); setCariAktif(true); }}
          onFocus={() => setCariAktif(true)}
          onBlur={() => setCariAktif(false)}
          onKeyDown={tombolCari}
        />
        {draft && (
          <button type="button" className="cari-hapus" aria-label={t('cari.kosongkan')}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => { setDraft(''); setCariAktif(true); }}>
            <X size={16} />
          </button>
        )}
        {cariAktif && saran.length > 0 && (
          <ul id="cari-saran" className="cari-saran" role="listbox">
            {saran.map((r, i) => {
              const k = draft.trim();
              const at = k ? r.query.toLowerCase().indexOf(k.toLowerCase()) : -1;
              return (
                <li key={r.query} id={`saran-${i}`} role="option" aria-selected={i === sorot}
                    className={i === sorot ? 'is-on' : undefined}
                    // Tekan tetikus menjalankan pilihan SEBELUM kotak kehilangan
                    // fokus; jeda 180 ms yang dulu dipakai membuat klik hilang.
                    onMouseDown={(e) => { e.preventDefault(); pilihSaran(r.query); }}
                    onMouseEnter={() => setSorot(i)}>
                  <History size={15} className="cari-saran-ikon" aria-hidden="true" />
                  <span className="cari-saran-teks">
                    {at < 0 ? r.query : (
                      <>
                        {r.query.slice(0, at)}
                        <b>{r.query.slice(at, at + k.length)}</b>
                        {r.query.slice(at + k.length)}
                      </>
                    )}
                  </span>
                  <button type="button" className="cari-saran-buang"
                          aria-label={t('cari.hapus_riwayat', { q: r.query })}
                          onMouseDown={(e) => { e.preventDefault(); e.stopPropagation(); buangRiwayat(r.query); }}>
                    {t('cari.hapus')}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <button type="submit" className="header-cari-tombol" aria-label={t('header.cari')}>
        <Search size={17} />
      </button>
    </form>
  );
}
