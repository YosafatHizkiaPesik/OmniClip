import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { BadgeCheck, Bell, BellOff, Loader2 } from 'lucide-react';
import { apiDelete, apiGet, apiPost } from '../lib/api';
import { angkaRingkas, useT } from '../lib/i18n';
import { simpanAvatar } from '../lib/avatarChannel';
import { ChannelAvatar } from '../components/VideoCards';
import KisiVideo from '../components/KisiVideo';

const TAB = [
  { id: 'videos', kunci: 'channel.tab_video' },
  { id: 'shorts', kunci: 'channel.tab_shorts' },
  { id: 'streams', kunci: 'channel.tab_live' },
];

/**
 * Halaman channel gaya YouTube (JOB-3 J3-4): banner, avatar, nama, @handle,
 * subscriber, deskripsi, tombol Ikuti, tab Video / Shorts / Live, urutan
 * Terbaru / Populer. Setiap kartu bisa dicentang lalu diklip bersama.
 */
export default function Channel() {
  const { ref } = useParams();
  const t = useT();
  const [tab, setTab] = useState('videos');
  const [urut, setUrut] = useState('terbaru');
  const [data, setData] = useState(null);
  const [galat, setGalat] = useState('');
  const [memuat, setMemuat] = useState(true);
  const [diikuti, setDiikuti] = useState(false);
  const [sibukIkuti, setSibukIkuti] = useState(false);
  const [deskripsiBuka, setDeskripsiBuka] = useState(false);

  useEffect(() => { setTab('videos'); setUrut('terbaru'); setData(null); }, [ref]);

  useEffect(() => {
    let batal = false;
    setMemuat(true); setGalat('');
    apiGet(`/channel/${encodeURIComponent(ref)}?tab=${tab}&urut=${urut}&batas=60`, { timeout: 90000 })
      .then((r) => {
        if (batal) return;
        setData(r);
        if (r?.info?.id) simpanAvatar(r.info.id, { avatar: r.info.avatar, nama: r.info.nama });
      })
      .catch((e) => { if (!batal) setGalat(e.message || t('channel.gagal')); })
      .finally(() => { if (!batal) setMemuat(false); });
    return () => { batal = true; };
  }, [ref, tab, urut]); // eslint-disable-line react-hooks/exhaustive-deps

  const info = data?.info;
  useEffect(() => {
    if (!info?.id) return;
    apiGet('/channel/ikuti').then((r) => setDiikuti((r.channel ?? []).some((c) => c.channel_id === info.id)))
      .catch(() => {});
  }, [info?.id]);

  const ubahIkuti = async () => {
    if (!info?.id) return;
    setSibukIkuti(true);
    try {
      if (diikuti) await apiDelete(`/channel/ikuti/${encodeURIComponent(info.id)}`);
      else await apiPost('/channel/ikuti', { channel_id: info.id, nama: info.nama, avatar: info.avatar });
      setDiikuti(!diikuti);
      window.dispatchEvent(new Event('omniclip:ikuti'));
    } finally { setSibukIkuti(false); }
  };

  if (galat && !data) {
    return <div className="page" style={{ padding: 40, textAlign: 'center', color: 'var(--danger)' }}>{galat}</div>;
  }

  return (
    <div className="page">
      {info?.banner ? (
        <div style={{ width: '100%', aspectRatio: '6.2 / 1', borderRadius: 16, overflow: 'hidden',
                      background: 'var(--plate-2)' }}>
          <img src={info.banner} alt="" referrerPolicy="no-referrer"
               style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>
      ) : !info && (
        <div style={{ width: '100%', aspectRatio: '6.2 / 1', borderRadius: 16, background: 'var(--plate-2)' }} />
      )}

      <div style={{ display: 'flex', gap: 22, alignItems: 'center', margin: '22px 0 10px', flexWrap: 'wrap' }}>
        {info ? <ChannelAvatar name={info.nama} src={info.avatar} size={150} />
          : <div style={{ width: 150, height: 150, borderRadius: '50%', background: 'var(--plate-2)' }} />}
        <div style={{ flex: 1, minWidth: 240 }}>
          <h1 style={{ fontSize: '2.1rem', fontWeight: 800, margin: 0, display: 'flex', gap: 8, alignItems: 'center' }}>
            {info?.nama || '…'}
            {info?.terverifikasi && <BadgeCheck size={22} style={{ color: 'var(--ink-3)' }} />}
          </h1>
          <div style={{ fontSize: '.88rem', color: 'var(--ink-2)', marginTop: 6 }}>
            {[info?.handle, info?.pelanggan != null && t('channel.subscriber', { n: angkaRingkas(info.pelanggan) })]
              .filter(Boolean).join(' · ')}
          </div>
          {info?.deskripsi && (
            <div onClick={() => setDeskripsiBuka((v) => !v)}
                 style={{ fontSize: '.84rem', color: 'var(--ink-2)', marginTop: 8, cursor: 'pointer',
                          maxWidth: 760, whiteSpace: 'pre-line',
                          ...(deskripsiBuka ? {} : { display: '-webkit-box', WebkitLineClamp: 1,
                                                     WebkitBoxOrient: 'vertical', overflow: 'hidden' }) }}>
              {info.deskripsi}
            </div>
          )}
          {info && (
            <button onClick={ubahIkuti} disabled={sibukIkuti}
                    className={diikuti ? 'btn-secondary' : 'btn-primary'}
                    style={{ marginTop: 14, borderRadius: 999, padding: '9px 18px',
                             display: 'inline-flex', gap: 8, alignItems: 'center' }}>
              {sibukIkuti ? <Loader2 size={15} className="animate-spin" />
                : diikuti ? <BellOff size={15} /> : <Bell size={15} />}
              {diikuti ? t('channel.berhenti_ikuti') : t('channel.ikuti')}
            </button>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border-color)', margin: '8px 0 16px',
                    alignItems: 'flex-end', flexWrap: 'wrap' }}>
        {TAB.map((x) => (
          <button key={x.id} onClick={() => setTab(x.id)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '12px 16px',
                           fontWeight: 700, fontSize: '.9rem', fontFamily: 'inherit',
                           color: tab === x.id ? 'var(--ink)' : 'var(--ink-3)',
                           borderBottom: `3px solid ${tab === x.id ? 'var(--ink)' : 'transparent'}` }}>
            {t(x.kunci)}
          </button>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6, paddingBottom: 8 }}>
          {['terbaru', 'populer'].map((u) => (
            <button key={u} onClick={() => setUrut(u)} className={`chip${urut === u ? ' is-on' : ''}`}>
              {t(`channel.urut_${u}`)}
            </button>
          ))}
        </div>
      </div>

      {memuat ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--ink-3)' }}>
          <Loader2 className="animate-spin" size={22} />
        </div>
      ) : (data?.video?.length ?? 0) === 0 ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--ink-3)' }}>{t('channel.kosong')}</div>
      ) : (
        <KisiVideo video={data.video} vertikal={tab === 'shorts'} />
      )}
    </div>
  );
}
