"""
Entry point backend OmniClip.

Menjalankan file ini dari terminal VS Code menempatkan proses di dalam cgroup
editor. Bila memori sistem habis, OOM killer bisa menjatuhkan seluruh scope itu
— itulah yang membuat VS Code ikut tertutup saat transkripsi podcast panjang.

Dua lapis perlindungan dipasang di sini:
  1. `oom_score_adj` dinaikkan, sehingga bila memori benar-benar habis kernel
     memilih proses ini lebih dulu daripada editor.
  2. Peringatan bila RAM yang tersedia sudah tipis sejak awal.

Penyebab utamanya sendiri sudah ditangani: audio ditranskripsi per potongan
8 menit (lihat app/services/whisper.py), sehingga memori puncak tidak lagi
tumbuh mengikuti durasi video.
"""

import os
import sys


def _prefer_self_for_oom() -> None:
    """Jadikan proses ini korban pertama OOM killer, bukan editor pengguna."""
    try:
        with open(f"/proc/{os.getpid()}/oom_score_adj", "w") as f:
            f.write("400")
    except OSError:
        pass


def _warn_low_memory() -> None:
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    mb = int(line.split()[1]) // 1024
                    if mb < 1500:
                        print(f"[OmniClip] Peringatan: RAM tersedia hanya {mb} MB. "
                              "Tutup aplikasi lain sebelum menganalisis video panjang.",
                              file=sys.stderr)
                    else:
                        print(f"[OmniClip] RAM tersedia: {mb} MB")
                    return
    except OSError:
        pass


if __name__ == "__main__":
    import uvicorn

    from app.config import HOST, PORT

    _prefer_self_for_oom()
    _warn_low_memory()

    # Bawaannya tetap 127.0.0.1: hanya komputer ini. Untuk Cloudflare Tunnel
    # nilai ini TIDAK perlu diubah — `cloudflared` menyambung dari dalam mesin,
    # sehingga tidak ada port yang terbuka ke jaringan sama sekali. OMNICLIP_HOST
    # hanya dipakai bila Anda memang ingin dijangkau dari LAN atau Tailscale.
    if HOST not in ("127.0.0.1", "::1", "localhost"):
        print(f"[OmniClip] Mendengar di {HOST}:{PORT} — bukan hanya komputer ini.",
              file=sys.stderr)

    uvicorn.run(
        "app.main:app", host=HOST, port=PORT, reload=False,
        # Di balik terowongan, alamat peer selalu 127.0.0.1 dan skemanya selalu
        # http. Tanpa dua baris ini backend mengira sambungannya tidak aman,
        # lalu menerbitkan cookie sesi tanpa flag Secure. Dipercaya hanya dari
        # loopback, karena hanya dari sanalah `cloudflared` menyambung.
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
    )
