import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      // Halaman kedua: isi iframe kotak pasir pratinjau Montase (JOB-4.md
      // bagian 20). Halaman terpisah, bukan rute, karena ia harus dimuat
      // dengan sandbox tanpa allow-same-origin.
      input: {
        main: fileURLToPath(new URL('./index.html', import.meta.url)),
        pratinjau: fileURLToPath(new URL('./pratinjau.html', import.meta.url)),
      },
    },
  },
  server: {
    // Iframe kotak pasir beralamat `null`, dan skrip modulnya selalu dimuat
    // dengan CORS. Tanpa 'null' di sini pratinjau Montase kosong saat
    // pengembangan. Asal lain tetap dibatasi ke komputer ini, sama dengan
    // bawaan Vite.
    cors: {
      origin: [/^https?:\/\/(?:(?:[^:]+\.)?localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$/, 'null'],
    },
    port: 5173,
    // strictPort penting: tanpa ini Vite diam-diam pindah ke 5174 saat 5173
    // terpakai, sementara backend hanya mengizinkan CORS untuk 5173 — gejalanya
    // adalah request yang gagal tanpa penjelasan.
    strictPort: true,
    proxy: {
      // Semua panggilan API relatif (/api/...) diteruskan ke backend, sehingga
      // tidak ada satupun URL backend yang perlu di-hardcode di kode frontend.
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
})
