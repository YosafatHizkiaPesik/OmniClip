import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { apiGet } from '../lib/api';
import { useT } from '../lib/i18n';
import { ChannelAvatar } from '../components/VideoCards';
import KisiVideo from '../components/KisiVideo';

/** Video terbaru dari channel yang diikuti akun ini (JOB-3 J3-5). */
export default function Langganan() {
  const t = useT();
  const [data, setData] = useState(null);
  const [galat, setGalat] = useState('');

  useEffect(() => {
    apiGet('/langganan', { timeout: 120000 }).then(setData)
      .catch((e) => setGalat(e.message || t('editor.gagal')));
  }, []);

  return (
    <div className="page">
      <h1 style={{ fontSize: '1.6rem', fontWeight: 800, margin: '4px 0 16px' }}>{t('nav.langganan')}</h1>
      {data?.channel?.length > 0 && (
        <div style={{ display: 'flex', gap: 18, overflowX: 'auto', paddingBottom: 12, marginBottom: 14 }}>
          {data.channel.map((c) => (
            <Link key={c.channel_id} to={`/channel/${encodeURIComponent(c.channel_id)}`}
                  style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
                           width: 86, flex: 'none', textDecoration: 'none', color: 'var(--ink-2)' }}>
              <ChannelAvatar name={c.nama} src={c.avatar} size={64} />
              <span style={{ fontSize: '.74rem', textAlign: 'center', overflow: 'hidden',
                             textOverflow: 'ellipsis', whiteSpace: 'nowrap', width: '100%' }}>{c.nama}</span>
            </Link>
          ))}
        </div>
      )}
      {galat ? <div style={{ color: 'var(--danger)' }}>{galat}</div>
        : !data ? <div style={{ padding: 40, textAlign: 'center' }}><Loader2 className="animate-spin" size={22} /></div>
          : data.video.length === 0
            ? <div style={{ padding: 40, textAlign: 'center', color: 'var(--ink-3)' }}>{t('langganan.kosong')}</div>
            : <KisiVideo video={data.video} />}
    </div>
  );
}
