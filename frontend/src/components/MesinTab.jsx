import React from 'react';
import KesehatanCard from './KesehatanCard';
import PemakaianAiCard from './PemakaianAiCard';
import PemeliharaanCard from './PemeliharaanCard';
import StorageCard from './StorageCard';
import SecurityCard from './SecurityCard';
import UpdateCard from './UpdateCard';
import KeluarCard from './KeluarCard';

/**
 * Mesin: keadaan aplikasinya sendiri, bukan cara klip dibuat.
 *
 * Dipisahkan dari Pengaturan 6 Oktober 2026 atas permintaan pemiliknya:
 * "pisahkan dan kelola lagi, halaman setting hanya berisi settingan sistem
 * saja". Ia benar, dan campurannya memang membingungkan — ruang cakram,
 * kesehatan, dan tombol mematikan aplikasi bukan setelan. Tidak ada satu pun
 * yang mengubah bagaimana sebuah klip dibuat; semuanya menjawab "bagaimana
 * keadaan aplikasinya sekarang".
 *
 * Batas pemisahnya satu pertanyaan: kalau diubah, apakah klip BERIKUTNYA jadi
 * berbeda? Kalau ya, ia setelan dan tinggal di Catatan main. Kalau tidak, ia
 * ada di sini.
 */

const card = {
  padding: '18px 20px',
};

const sectionTitle = {
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
  fontSize: '0.95rem',
  fontWeight: 800,
  color: 'var(--text-primary)',
  marginBottom: '6px',
};

const helpText = {
  fontSize: '0.78rem',
  color: 'var(--text-secondary)',
  lineHeight: 1.6,
};

function Kelompok({ judul, nota, children }) {
  return (
    <section className="setelan-kelompok">
      <div className="setelan-kelompok-kepala">
        <h2>{judul}</h2>
        {nota && <p>{nota}</p>}
      </div>
      <div className="petak-setelan">{children}</div>
    </section>
  );
}

export default function MesinTab() {
  const alat = { card, sectionTitle, helpText };
  return (
    <div className="page">
      <div className="work-block" style={{ alignItems: 'center' }}>
        <div style={{ minWidth: 0 }}>
          <h1 className="work-title">Mesin</h1>
          <div className="sub">
            Keadaan aplikasinya sendiri. Tidak ada di halaman ini yang mengubah
            cara klip dibuat.
          </div>
        </div>
      </div>

      <Kelompok judul="Ruang dan berkas"
                nota="Di mana semuanya tinggal, dan berapa yang tersisa.">
        <StorageCard {...alat} />
        <PemeliharaanCard {...alat} />
      </Kelompok>

      <Kelompok judul="Kesehatan dan pemakaian"
                nota="Apa yang sedang berjalan, dan berapa kuota AI yang sudah terpakai.">
        <KesehatanCard {...alat} />
        <PemakaianAiCard {...alat} />
      </Kelompok>

      <Kelompok judul="Aplikasi"
                nota="Versi, akses dari luar, dan cara mematikannya.">
        <UpdateCard {...alat} />
        <SecurityCard {...alat} />
        <KeluarCard {...alat} />
      </Kelompok>
    </div>
  );
}
