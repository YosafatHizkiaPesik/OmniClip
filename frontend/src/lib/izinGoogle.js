/**
 * Membuka tab izin Google.
 *
 * SENGAJA tanpa `noopener`. Halaman balik dari Google, yang asalnya sama
 * dengan aplikasi ini, mengabarkan dirinya selesai lewat
 * `window.opener.postMessage` lalu menutup tab itu sendiri. `noopener`
 * menjamin `window.opener` kosong di sana, jadi kabarnya tidak pernah terkirim
 * dan halaman yang menunggu menggantung tanpa batas di "Menunggu izin dari
 * Google" walaupun izinnya sudah berhasil. Terlapor pemiliknya 27 September
 * 2026, lengkap dengan buktinya: "akun sudah tersambung youtube tapi masih
 * saja loading".
 *
 * Yang dibuka hanyalah halaman izin Google, dan `window.opener` yang ia terima
 * tidak memberi akses ke isi halaman ini, hanya kemampuan mengarahkannya.
 * Pemanggil tetap WAJIB punya jalan pulang sendiri (menanyakan status berkala),
 * karena tab itu bisa saja ditutup sebelum sempat mengabarkan.
 */
export function bukaIzinGoogle(url) {
  return window.open(url, '_blank');
}

/** Pesan yang dikirim halaman balik Google saat izinnya selesai. */
export const PESAN_TERSAMBUNG = 'omniclip:google-tersambung';
