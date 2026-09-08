import React from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import Editor from '../features/studio/Editor';

/**
 * Editor untuk satu project.
 *
 * Data kartu dioper lewat state navigasi supaya judulnya langsung tampil, tapi
 * `video_id` dari URL yang jadi sumber kebenaran — halaman ini harus tetap
 * bekerja saat dibuka dari tautan langsung atau setelah reload.
 */
export default function EditorRoute() {
  const { videoId } = useParams();
  const { state } = useLocation();
  const navigate = useNavigate();

  return (
    <Editor
      project={{ ...(state?.project ?? {}), video_id: videoId }}
      onBack={() => navigate('/studio')}
    />
  );
}
