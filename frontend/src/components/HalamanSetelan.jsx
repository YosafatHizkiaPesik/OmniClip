import React from 'react';
import { useSearchParams } from 'react-router-dom';

/**
 * Tata letak halaman setelan (Akun, Pengaturan, Mesin), JOB-3.
 *
 * Dilaporkan pemiliknya 15 Oktober 2026: halaman-halaman ini penuh ruang
 * kosong. Sebabnya kartu ditata dua kolom per kelompok; kartu pendek di
 * sebelah kartu tinggi menyisakan lubang, dan tiap kelompok mengulanginya.
 *
 * Sekarang seperti setelan YouTube Studio: daftar bagian di kiri, isi satu
 * bagian di kanan dalam satu kolom selebar bacaan. Bagian yang dibuka
 * disimpan di alamat (`?bagian=`), jadi tombol kembali dan tautan langsung
 * tetap bekerja. Di layar sempit daftarnya menjadi baris pil yang digeser.
 *
 * `bagian`: [{ id, judul, nota?, Ikon?, isi }]
 */
export default function HalamanSetelan({ judul, sub, aksi = null, bagian, kelas = '' }) {
  const [params, setParams] = useSearchParams();
  const ada = bagian.filter(Boolean);
  const aktif = ada.find((b) => b.id === params.get('bagian')) ?? ada[0];

  const pilih = (id) => {
    const p = new URLSearchParams(params);
    p.set('bagian', id);
    setParams(p, { replace: true });
    window.scrollTo({ top: 0 });
  };

  return (
    <div className={`page halaman-setelan ${kelas}`}>
      <div className="work-block" style={{ alignItems: 'center' }}>
        <div style={{ minWidth: 0 }}>
          <h1 className="work-title">{judul}</h1>
          {sub && <div className="sub">{sub}</div>}
        </div>
        {aksi}
      </div>

      <div className="setelan-tata">
        <nav className="setelan-nav" aria-label={judul}>
          {ada.map(({ id, judul: j, Ikon }) => (
            <button key={id} type="button" onClick={() => pilih(id)}
                    className={`setelan-nav-item${aktif?.id === id ? ' is-on' : ''}`}
                    aria-current={aktif?.id === id ? 'page' : undefined}>
              {Ikon && <Ikon size={16} />}
              <span>{j}</span>
            </button>
          ))}
        </nav>

        {aktif && (
          <section className="setelan-isi" key={aktif.id}>
            <div className="setelan-isi-kepala">
              <h2>{aktif.judul}</h2>
              {aktif.nota && <p>{aktif.nota}</p>}
            </div>
            <div className="setelan-kartu">{aktif.isi}</div>
          </section>
        )}
      </div>
    </div>
  );
}
