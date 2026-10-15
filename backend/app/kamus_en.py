"""
Katalog pesan server Indonesia -> Inggris (JOB-3 J3-11). Lihat bahasa.py.

Tiap baris: (kalimat Indonesia persis seperti yang dikirim server, Inggrisnya).
`{nama}` menandai bagian yang berubah (angka, judul, nama layanan); isiannya
ikut diterjemahkan bila ia sendiri kalimat yang ada di katalog ini.

Kalimat yang belum ada di sini tetap tampil dalam bahasa Indonesia, jadi
menambah kalimat baru di backend tanpa menambahkannya ke sini tidak merusak
apa pun; hanya tampil belum terjemah.
"""

KATALOG = [
    # --- galat umum (errors.py, middleware) ---------------------------------
    ("Terjadi kesalahan.", "Something went wrong."),
    ("Data tidak ditemukan.", "Not found."),
    ("Masukan tidak valid.", "Invalid input."),
    ("Layanan eksternal sedang bermasalah.", "An external service is having problems."),
    ("Terlalu banyak permintaan. Coba lagi beberapa menit lagi.",
     "Too many requests. Try again in a few minutes."),
    ("Gagal merender klip. Cek log server untuk detail.",
     "Could not render the clip. Check the server log for details."),
    ("Terjadi kesalahan internal di server.", "An internal server error occurred."),
    ("Sesi berakhir. Masuk lagi dengan kata sandi.", "Session expired. Sign in again with your password."),
    ("Job tidak ditemukan.", "Job not found."),
    ("Profil tidak ditemukan.", "Account not found."),
    ("Video tidak dikenali.", "Video not recognized."),
    ("Channel tidak dikenali.", "Channel not recognized."),
    ("Channel ini tidak bisa dibuka sekarang.", "This channel cannot be opened right now."),
    ("Pencarian tidak menghasilkan apa pun.", "The search returned nothing."),
    ("File video sumber tidak ditemukan.", "The source video file was not found."),
    ("Kategori media tidak valid.", "Invalid media category."),
    ("Font tidak dikenali.", "Font not recognized."),
    ("Suara itu tidak dikenal.", "That voice is not recognized."),
    ("Belum ada kata sandi yang dipasang.", "No password has been set."),

    # --- antrean pekerjaan (services/jobs.py) -------------------------------
    ("Menunggu giliran, sebentar lagi mulai…", "Waiting in line, starting shortly…"),
    ("Menunggu giliran, {n} pekerjaan lain di depan.", "Waiting in line, {n} other jobs ahead."),
    ("Menunggu giliran, video lain sedang dianalisis…", "Waiting in line, another video is being analyzed…"),
    ("Dibatalkan oleh pengguna.", "Cancelled by the user."),
    ("Pekerjaan gagal.", "The job failed."),

    # --- unduh, transkrip, analisis (services/pipeline.py) ------------------
    ("Mengambil informasi video…", "Fetching video info…"),
    ("Membaca informasi video…", "Reading video info…"),
    ("Mengunduh «{judul}»…", "Downloading «{judul}»…"),
    ("Menunggu giliran mengunduh, unduhan lain sedang berjalan…",
     "Waiting to download, another download is running…"),
    ("Pengunduhan gagal.", "The download failed."),
    ("Menyimpan catatan unduhan…", "Saving download record…"),
    ("Resolusi {minta} tidak tersedia; yang diunduh {dapat}.",
     "Resolution {minta} is not available; downloaded {dapat} instead."),
    ("Video sumber belum diunduh. Unduh videonya dulu, lalu render klip.",
     "The source video is not downloaded yet. Download the video first, then render the clip."),
    ("Video sumber belum diunduh.", "The source video is not downloaded yet."),
    ("Proyek ini sudah disunting, jadi percobaan ulang Gemini dilewati. "
     "Tekan \"Cari ulang\" kalau memang ingin daftarnya diganti.",
     "This project has already been edited, so the Gemini retry was skipped. "
     "Press \"Search again\" if you do want the list replaced."),
    ("Berkas video impor ini sudah tidak ada di penyimpanan. Ambil lagi videonya dari komputer.",
     "This imported video file is no longer in storage. Pick the video again from your computer."),
    ("Video dari komputer siap dibaca.", "The video from your computer is ready to read."),
    ("Video sudah tersedia di penyimpanan lokal.", "The video is already in local storage."),
    ("Video dari komputer siap", "Video from computer ready"),
    ("Video sudah terunduh", "Video already downloaded"),
    ("Mencari transkrip…", "Looking for a transcript…"),
    ("Menyiapkan audio…", "Preparing audio…"),
    ("Audio video ini tidak bisa dibaca.", "This video's audio cannot be read."),
    ("Memakai transkrip tersimpan ({n} kata).", "Using the saved transcript ({n} words)."),
    ("Transkrip ditemukan ({n} kata).", "Transcript found ({n} words)."),
    ("Video tidak punya subtitle, menyalin ucapan dengan Whisper…",
     "The video has no subtitles, transcribing speech with Whisper…"),
    ("Mendengarkan bahasa yang dipakai…", "Detecting the spoken language…"),
    ("Menyalin ucapan… {waktu}", "Transcribing speech… {waktu}"),
    ("Video ini tidak punya transkrip.", "This video has no transcript."),
    ("Video ini tidak punya transkrip dan ucapannya tidak bisa disalin, jadi klip otomatis "
     "tidak bisa disusun. Anda masih bisa memotong manual di Studio.",
     "This video has no transcript and its speech cannot be transcribed, so automatic clips "
     "cannot be made. You can still cut clips manually in the Studio."),
    ("Selesai tanpa transkrip.", "Finished without a transcript."),
    ("Mengukur energi bicara…", "Measuring speech energy…"),
    ("Memakai penanda narasumber sebelumnya…", "Using the earlier speaker labels…"),
    ("Memperkirakan jumlah narasumber…", "Estimating the number of speakers…"),
    ("Mencari momen paling menarik…", "Finding the most interesting moments…"),
    ("Menyusun ulang peringkat dengan Gemini…", "Re-ranking with Gemini…"),
    ("Memakai kunci Gemini ke-{n} dari {total}…", "Using Gemini key {n} of {total}…"),
    ("Tidak ada kunci Gemini.", "No Gemini key."),
    ("Memeriksa awal dan akhir tiap klip…", "Checking the start and end of each clip…"),
    ("Gemini sedang sibuk atau tidak menjawab", "Gemini is busy or not answering"),
    ("Gemini gagal", "Gemini failed"),
    ("{alasan}. Mencoba OpenRouter…", "{alasan}. Trying OpenRouter…"),
    ("Dipilih OpenRouter ({model}).", "Picked by OpenRouter ({model})."),
    ("{alasan}, memakai mesin lokal.", "{alasan}, using the local engine."),
    ("Menyusun hasil…", "Putting the results together…"),
    ("Video sumbernya hanya {n}p, dan itu memang yang tertinggi disediakan YouTube untuk "
     "video ini. Klip tegaknya akan terlihat lebih lunak daripada biasanya.",
     "The source video is only {n}p, which is the highest YouTube offers for this video. "
     "The vertical clips will look softer than usual."),
    ("Menerjemahkan subtitle…", "Translating subtitles…"),
    ("{n} klip siap ditinjau", "{n} clips ready for review"),
    ("Kunci Gemini belum diisi di Pengaturan.", "No Gemini key has been set in Settings."),
    ("Video ini belum punya analisis.", "This video has not been analyzed yet."),
    ("Belum ada analisis untuk video ini.", "This video has not been analyzed yet."),
    ("Video ini belum punya transkrip.", "This video has no transcript yet."),
    ("Semua judul sudah ditulis Gemini.", "All titles were already written by Gemini."),
    ("Menulis ulang {n} judul…", "Rewriting {n} titles…"),
    ("{n} judul ditulis ulang oleh {model}.", "{n} titles rewritten by {model}."),
    ("Mengambil suara pembaca judul…", "Fetching the title narrator voice…"),
    ("Suara pembaca sudah ada.", "The narrator voice is already installed."),
    ("{nama} selesai diunduh.", "{nama} downloaded."),
    ("Gagal mengunduh suara pembaca judul.", "Could not download the title narrator voice."),
    ("Suara pembaca siap dipakai.", "The narrator voice is ready."),
    ("Memindai wajah klip {n} dari {total}…", "Scanning faces in clip {n} of {total}…"),
    ("Membaca audio video (sekali saja, lalu disimpan)…", "Reading the video's audio (once, then saved)…"),
    ("Memisahkan {n} narasumber…", "Separating {n} speakers…"),
    ("Mendengarkan suara tiap orang… {n}%", "Listening to each person's voice… {n}%"),
    ("Memeriksa apakah ini rekaman gameplay…", "Checking whether this is a gameplay recording…"),
    ("Rekaman gameplay dengan {n} orang di facecam", "Gameplay recording with {n} people on the face cam"),
    ("Rekaman gameplay dengan satu pemain", "Gameplay recording with one player"),
    ("Mencari siapa yang terlihat bicara…", "Finding who is visibly talking…"),
    ("Menambatkan suara ke wajah…", "Matching voices to faces…"),
    ("Memeriksa apakah ada wajah di video…", "Checking whether there are faces in the video…"),
    ("Menerapkan penanda ke subtitle…", "Applying labels to the subtitles…"),
    ("{n} narasumber ditandai.", "{n} speakers labeled."),
    ("Diminta {minta} orang, tapi {beda} kelompok ternyata suara orang yang sama, "
     "{n} narasumber ditandai.",
     "{minta} people were requested, but {beda} groups turned out to be the same person's "
     "voice; {n} speakers labeled."),

    # --- render ---------------------------------------------------------------
    ("Merender klip", "Rendering clip"),
    ("Merender {n} potongan gabungan", "Rendering {n} joined segments"),
    ("Membaca isi klip (game, wajah, atau tanpa wajah)…", "Reading the clip (game, faces, or no faces)…"),
    ("Melacak wajah pembicara…", "Tracking the speaker's face…"),
    ("Mencari kamera wajah pemain…", "Looking for the player's face cam…"),
    ("Menyusun {n} bingkai…", "Arranging {n} frames…"),
    ("Merender klip…", "Rendering clip…"),
    ("Merender {n} potongan gabungan…", "Rendering {n} joined segments…"),
    ("Merender klip… {n}%", "Rendering clip… {n}%"),
    ("Merender {k} potongan gabungan… {n}%", "Rendering {k} joined segments… {n}%"),
    ("Klip selesai dirender.", "Clip rendered."),
    ("{n} menit lagi", "{n} more minutes"),

    # --- unggah ---------------------------------------------------------------
    ("Memberi jeda antar unggahan… {n} dtk lagi", "Pausing between uploads… {n} s left"),
    ("Mengirim {berkas} ke {tujuan}… ({mb} MB)", "Sending {berkas} to {tujuan}… ({mb} MB)"),
    ("Mengirim ke {tujuan}… {n}%", "Sending to {tujuan}… {n}%"),
    ("Terunggah ke {tujuan}.", "Uploaded to {tujuan}."),
    ("Catatan isi klipnya tidak ada, jadi klip ini tidak bisa diperiksa.",
     "The clip's content record is missing, so this clip cannot be checked."),
    ("Deskripsinya tidak menyebut video sumber.", "The description does not credit the source video."),
    ("Belum ada komentar atau tambahan dari Anda sendiri. Tanpa itu YouTube menilainya sebagai "
     "potongan ulang; isi tab Komentar di Studio lalu render ulang.",
     "There is no commentary or addition of your own yet. Without it YouTube sees it as a "
     "re-upload; fill in the Commentary tab in the Studio and render again."),

    # --- nilai tambah dan punch-in ------------------------------------------
    ("{n} komentar, {d} detik, {s} dengan suara Anda", "{n} commentaries, {d} seconds, {s} with your voice"),
    ("{n} komentar, {d} detik", "{n} commentaries, {d} seconds"),
    ("reaksi kamera {d} detik", "camera reaction {d} seconds"),
    ("sisipan {d} detik", "inserts {d} seconds"),
    ("suara melonjak {n} dB", "audio spikes {n} dB"),

    # --- kesehatan sistem (routers/settings.py) -------------------------------
    ("Encoder video", "Video encoder"),
    ("Render tetap jalan memakai prosesor, sekitar 1,6 kali lebih lambat.",
     "Rendering still works on the CPU, about 1.6 times slower."),
    ("belum disiapkan", "not set up"),
    ("Tanpa ini YouTube bisa menolak unduhan dengan \"Sign in to confirm you're not a bot\".",
     "Without this, YouTube may refuse downloads with \"Sign in to confirm you're not a bot\"."),
    ("Runtime JavaScript (Deno)", "JavaScript runtime (Deno)"),
    ("terpasang", "installed"),
    ("Sama seperti PO Token: unduhan YouTube bisa ditolak.", "Same as the PO Token: YouTube downloads may be refused."),
    ("dipakai terus", "always on"),
    ("Dari jaringan yang sehat ini justru mengurangi pilihan resolusi. Pertimbangkan mode "
     "cadangan di Pengaturan.",
     "On a healthy network this actually reduces the resolution options. Consider standby "
     "mode in Settings."),
    ("siaga ({browser})", "standby ({browser})"),
    ("Sesi login sudah siap dan akan dipakai sendiri begitu YouTube menuduh bot.",
     "The signed-in session is ready and will be used automatically once YouTube suspects a bot."),
    ("Begitu YouTube menandai jaringan Anda sebagai bot, unduhan berhenti dan tidak ada sesi "
     "login untuk menembusnya. Siapkan di Pengaturan, bagian Cookies.",
     "Once YouTube flags your network as a bot, downloads stop and there is no signed-in "
     "session to get through. Set it up in Settings, under Cookies."),
    ("Cookies YouTube", "YouTube cookies"),
    ("Akun Google profil ini", "This account's Google account"),
    ("tersambung", "connected"),
    ("belum tersambung", "not connected"),
    ("Unggah ke YouTube dan Drive tidak bisa jalan.", "Uploads to YouTube and Drive cannot work."),
    ("Kunci AI", "AI key"),
    ("OpenRouter saja", "OpenRouter only"),
    ("belum diisi", "not set"),
    ("Pemilihan klip dan sutradara bingkai memakai mesin lokal.",
     "Clip selection and the framing director use the local engine."),
    ("Font aksara non-Latin", "Non-Latin script fonts"),
    ("belum ada (diunduh saat dipakai)", "none yet (downloaded when needed)"),
    ("Diunduh sendiri saat pertama kali ada subtitle Jepang, Korea, Mandarin, atau Arab.",
     "Downloaded automatically the first time there are Japanese, Korean, Chinese or Arabic subtitles."),
    ("Sisa ruang cakram", "Free disk space"),
    ("Render dan unduhan gagal di tengah jalan bila ruangnya habis.",
     "Renders and downloads fail halfway if the space runs out."),

    # --- pustaka --------------------------------------------------------------
    ("sudah mutakhir", "already up to date"),
]
