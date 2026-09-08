import React from 'react';
import { useNavigate } from 'react-router-dom';
import StudioHome from '../features/studio/StudioHome';

/** Daftar kartu project. Membuka satu kartu berpindah ke /studio/:videoId. */
export default function Studio() {
  const navigate = useNavigate();
  return (
    <StudioHome
      onOpen={(project) => navigate(`/studio/${project.video_id}`, { state: { project } })}
      onFindVideos={() => navigate('/')}
    />
  );
}
