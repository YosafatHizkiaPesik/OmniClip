"""
Montase: studio penyunting video lengkap (JOB-4.md).

Modul ini sengaja terpisah dari Studio Klip. Ia boleh memakai layanan bersama
(`app.services.*` yang tercantum di JOB-4.md bagian 15), tapi tidak boleh
menyentuh pipeline, render klip, atau sutradara. Tes `test_montase_batas.py`
menjaga aturan itu.

Isi saat ini (Tahap 0, uji teknis):
  mesin.py   menemukan dan menjalankan Mesin Montase (Node + Remotion)
  unduh.py   mengunduh Node portabel saat pertama dipakai
  token.py   token bertanda tangan untuk bahan yang dibaca peramban/mesin
  cors.py    CORS untuk jalur bertoken (iframe kotak pasir, halaman render)
  uji.py     bahan dan dokumen uji Tahap 0
  router.py  /api/montase/*
"""
