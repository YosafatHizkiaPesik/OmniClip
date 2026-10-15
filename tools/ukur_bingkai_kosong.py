# Jalankan dari folder backend: python ../tools/ukur_bingkai_kosong.py kasus.json [-v]
# kasus.json = [["nama", "jalur video", detik_mulai, detik_akhir], ...]
# Memori ±200 MB per klip (bingkai dibaca beralir). Satu klip per proses disarankan.
"""
Alat ukur bingkai kosong, berdiri sendiri dari keputusan reframe.

Untuk tiap bingkai keluaran (30 Hz): deteksi wajah YuNet pada bingkai sumber
yang sama. Bingkai dihitung KOSONG bila ada wajah di gambar tapi tidak satu pun
pusat wajah berada di dalam jendela crop. Dipisah: kosong umum, kosong dalam
0,6 dtk sesudah potongan adegan, dan "luncur" = laju perpindahan crop di
sekitar potongan (px/bingkai rata2 di 4 bingkai sesudah potongan).
"""
import json, subprocess, sys, math
from pathlib import Path
import numpy as np, cv2
sys.path.insert(0, ".")
from app.services import reframe as R

DETAIL=[]
def ukur(src, segs, fps=30, lebar=1280):
    DETAIL.clear()
    plan = R.plan_reframe(str(src), segs, aspect_ratio="9:16")
    if plan is None or not plan.centers:
        return None
    sw, sh = plan.source_w, plan.source_h
    skala = lebar / sw
    tinggi = int(round(sh * skala / 2) * 2)
    det = cv2.FaceDetectorYN.create(str(R.MODEL_PATH), "", (lebar, tinggi), 0.6, 0.3, 50)
    # Dekode BERALIR, satu bingkai tiap kali. Versi sebelumnya memuat seluruh
    # klip ke memori (±2,5 GB per 30 dtk pada 1280 px) dan membuat laptop 8 GB
    # kehabisan RAM sampai VS Code ditutup paksa (15 Oktober 2026).
    def frames_iter():
        ukuran = lebar * tinggi * 3
        for s_ in segs:
            cmd = ["ffmpeg","-loglevel","error","-threads","2","-ss",f"{s_['start']:.3f}","-t",f"{s_['end']-s_['start']:.3f}",
                   "-i",str(src),"-vf",f"fps={fps},scale={lebar}:{tinggi}","-f","rawvideo","-pix_fmt","bgr24","-"]
            p_ = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            while True:
                buf = p_.stdout.read(ukuran)
                if len(buf) < ukuran: break
                yield np.frombuffer(buf, np.uint8).reshape(tinggi, lebar, 3)
            p_.stdout.close(); p_.wait()
    frames = frames_iter()
    cen = plan.centers
    ct = np.array([c[0] for c in cen]); cx = np.array([c[1] for c in cen])
    half = plan.crop_w / 2
    potong = plan.cut_times or []
    global R_cut; R_cut = potong
    kosong = ber = dekat = dekat_kosong = 0
    lompatan = []
    prev = None
    for k, img in enumerate(frames):
        t = k / fps
        x = float(np.interp(t, ct, cx))
        _, f = det.detect(img)
        if prev is not None:
            lompatan.append(abs(x - prev))
        prev = x
        if f is None or len(f) == 0: continue
        pus = [(ff[0] + ff[2]/2) / skala for ff in f if ff[2] / lebar > 0.02]
        if not pus: continue
        ber += 1
        isi = any(abs(p - x) <= half for p in pus)
        dkt = any(0 <= t - c <= 0.6 for c in potong)
        if dkt:
            dekat += 1
            if not isi: dekat_kosong += 1
        if not isi:
            kosong += 1
            DETAIL.append((round(t,2), round(x), [round(q) for q in pus], round(half)))
    lomp = np.array(lompatan) / sw * 100
    return {"bingkai": len(lompatan) + 1, "berwajah": ber, "kosong_%": round(100*kosong/max(1,ber),2),
            "potongan": len(potong), "kosong_dekat_potongan_%": round(100*dekat_kosong/max(1,dekat),2),
            "luncur_bingkai_>2%": int((lomp > 2).sum()),
            "gerak_rata_%lebar/bingkai": round(float(lomp.mean()),3)}

if __name__ == "__main__":
    kasus = json.loads(Path(sys.argv[1]).read_text())
    hasil = {}
    with R.di_latar():
        for nama, src, a, b in kasus:
            r = ukur(Path(src), [{"start": a, "end": b}])
            hasil[nama] = r
            print(nama, r, flush=True)
            if '-v' in sys.argv: print('  kosong:', DETAIL[:60]); print('  potong:', R_cut)
    tot_b = sum(r["berwajah"] for r in hasil.values() if r)
    print("TOTAL kosong%", round(sum(r["kosong_%"]*r["berwajah"] for r in hasil.values() if r)/tot_b, 2),
          "luncur", sum(r["luncur_bingkai_>2%"] for r in hasil.values() if r))
