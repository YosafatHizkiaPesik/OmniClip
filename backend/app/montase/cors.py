"""
CORS untuk jalur bertoken Montase (`/api/montase/t/...`).

Pembaca jalur ini datang dari asal yang tidak dikenal `CORSMiddleware` utama:
iframe kotak pasir beralamat `null`, dan halaman render Remotion di
`http://localhost:<port acak>`. `@remotion/media` membaca video dengan `fetch`
dan permintaan Range, jadi tanpa izin CORS videonya tidak pernah termuat.

Kenapa middleware sendiri, bukan menambah asal di `ALLOWED_ORIGINS`:
`CORSMiddleware` menjawab preflight SEBELUM permintaan sampai ke router, dan
menolaknya untuk asal yang tidak terdaftar. Mendaftarkan `null` di sana berarti
membuka SELURUH API bagi kotak pasir mana pun. Di sini izin `*` hanya untuk
jalur bertoken, yang isinya dibuktikan oleh tokennya sendiri, bukan oleh
cookie (`allow_credentials` tidak pernah dinyalakan).

Middleware ini harus dipasang PALING LUAR (sesudah CORSMiddleware di main.py),
supaya preflight-nya dijawab sebelum CORSMiddleware sempat menolaknya.
"""

from __future__ import annotations

AWALAN = "/api/montase/t/"

_KEPALA = [
    (b"access-control-allow-origin", b"*"),
    (b"access-control-expose-headers", b"Content-Length, Content-Range, Accept-Ranges"),
]
_KEPALA_PREFLIGHT = _KEPALA + [
    (b"access-control-allow-methods", b"GET, HEAD, OPTIONS"),
    (b"access-control-allow-headers", b"Range, Content-Type"),
    (b"access-control-max-age", b"600"),
]


class CorsBertoken:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith(AWALAN):
            await self.app(scope, receive, send)
            return
        if scope["method"] == "OPTIONS":
            await send({"type": "http.response.start", "status": 204,
                        "headers": list(_KEPALA_PREFLIGHT)})
            await send({"type": "http.response.body", "body": b""})
            return

        async def kirim(pesan):
            if pesan["type"] == "http.response.start":
                lama = [(k, v) for k, v in pesan.get("headers", [])
                        if k.lower() not in {k2 for k2, _ in _KEPALA}]
                pesan = {**pesan, "headers": lama + list(_KEPALA)}
            await send(pesan)

        await self.app(scope, receive, kirim)
