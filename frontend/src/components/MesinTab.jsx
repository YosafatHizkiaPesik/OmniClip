import React from 'react';
import {
  Activity, ArrowDownToLine, DatabaseBackup, Gauge, HardDrive, Lock,
} from 'lucide-react';
import { useT } from '../lib/i18n';
import HalamanSetelan from './HalamanSetelan';
import KesehatanCard from './KesehatanCard';
import PemakaianAiCard from './PemakaianAiCard';
import PemeliharaanCard from './PemeliharaanCard';
import SampahCard from './SampahCard';
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

export default function MesinTab() {
  const t = useT();
  const alat = { card, sectionTitle, helpText };
  return (
    <HalamanSetelan
      judul={t('mesin.judul')}
      sub={t('mesin.sub')}
      bagian={[
        { id: 'penyimpanan', judul: t('mesin.b_simpan'), nota: t('mesin.b_simpan_nota'), Ikon: HardDrive,
          isi: <><StorageCard {...alat} /><SampahCard {...alat} /></> },
        { id: 'ruang', judul: t('mesin.b_ruang'), nota: t('mesin.b_ruang_nota'), Ikon: DatabaseBackup,
          isi: <PemeliharaanCard {...alat} /> },
        { id: 'kesehatan', judul: t('mesin.b_sehat'), nota: t('mesin.b_sehat_nota'), Ikon: Activity,
          isi: <KesehatanCard {...alat} /> },
        { id: 'ai', judul: t('mesin.b_ai'), nota: t('mesin.b_ai_nota'), Ikon: Gauge,
          isi: <PemakaianAiCard {...alat} /> },
        { id: 'pembaruan', judul: t('mesin.b_perbarui'), nota: t('mesin.b_perbarui_nota'), Ikon: ArrowDownToLine,
          isi: <UpdateCard {...alat} /> },
        { id: 'keamanan', judul: t('mesin.b_aman'), nota: t('mesin.b_aman_nota'), Ikon: Lock,
          isi: <><SecurityCard {...alat} /><KeluarCard {...alat} /></> },
      ]}
    />
  );
}
