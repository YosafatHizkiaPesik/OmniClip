"""
Skema dokumen proyek Montase (JOB-4 bagian 16), divalidasi setiap kali disimpan.

Satu proyek = satu JSON. Server memeriksanya di sini, bukan di peramban saja,
karena dokumen ini juga yang dibaca mesin render: dokumen yang lolos ke basis
data harus bisa dirender, atau ditolak dengan alasan yang bisa dibaca orang.

Yang dijaga:
  - bentuk dan rentang setiap kolom (waktu dalam BINGKAI, bilangan bulat);
  - id lajur dan item unik, dan setiap item bergambar/bersuara merujuk bahan
    yang tercatat di `dokumen.bahan`;
  - ukuran: dokumen raksasa ditolak sebelum menyentuh basis data.

Kolom yang tidak dikenal DIPERTAHANKAN (extra="allow"), bukan dibuang. Dokumen
dari versi OmniClip yang lebih baru tidak boleh kehilangan isinya hanya karena
dibuka di versi yang lebih lama dan disimpan ulang. Versi dokumen yang LEBIH
BARU dari yang dikenal ditolak dengan pesan jelas.

`durasi` proyek tidak dipercaya dari klien: dihitung ulang dari ujung item
terakhir (sama seperti CapCut, panjang video = isi linimasanya).
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

VERSI_DOKUMEN = 1
BATAS_BITA = 2_000_000
BATAS_ITEM = 2000

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_ID = re.compile(r"^[A-Za-z0-9_\-]{1,40}$")

PRESET_KANVAS = {
    "shorts": (1080, 1920),
    "youtube": (1920, 1080),
    "persegi": (1080, 1080),
    "potret": (1080, 1350),
}
FPS_BOLEH = (24, 25, 30, 50, 60)


class GagalSkema(ValueError):
    """Dokumen tidak sah. `pesan` berisi alasan per kolom, siap ditampilkan."""

    def __init__(self, pesan: list[str]):
        super().__init__("; ".join(pesan))
        self.pesan = pesan


class _Dasar(BaseModel):
    model_config = ConfigDict(extra="allow")


class Kanvas(_Dasar):
    lebar: int = Field(1080, ge=16, le=7680)
    tinggi: int = Field(1920, ge=16, le=7680)
    fps: int = 30
    latar: str = "#000000"

    @field_validator("lebar", "tinggi")
    @classmethod
    def _genap(cls, v: int) -> int:
        # H.264 dengan yuv420p menuntut ukuran genap; ukuran ganjil baru gagal
        # di tengah render, jadi ditolak di sini.
        if v % 2:
            raise ValueError("harus bilangan genap")
        return v

    @field_validator("fps")
    @classmethod
    def _fps(cls, v: int) -> int:
        if v not in FPS_BOLEH:
            raise ValueError(f"harus salah satu dari {FPS_BOLEH}")
        return v

    @field_validator("latar")
    @classmethod
    def _warna(cls, v: str) -> str:
        if not _HEX.match(v):
            raise ValueError("warna harus #RRGGBB")
        return v


class BahanMeta(_Dasar):
    jenis: Literal["video", "audio", "gambar"]
    nama: str = ""
    durasi: Optional[float] = Field(None, ge=0)
    lebar: Optional[int] = None
    tinggi: Optional[int] = None
    fps: Optional[float] = None
    ada_suara: bool = False


class Item(_Dasar):
    id: str
    jenis: Literal["video", "gambar", "teks", "motion", "audio"]
    mulai: int = Field(0, ge=0)
    durasi: int = Field(1, ge=1)
    bahan: Optional[str] = None
    potong_awal: int = Field(0, ge=0)
    kecepatan: float = Field(1.0, ge=0.25, le=4.0)
    volume: float = Field(1.0, ge=0.0, le=2.0)
    teks: Optional[str] = Field(None, max_length=500)
    komponen: Optional[str] = None
    versi: Optional[int] = Field(None, ge=1)
    props: dict[str, Any] = Field(default_factory=dict)
    asal: Literal["tangan", "ai"] = "tangan"
    alasan: Optional[str] = Field(None, max_length=500)

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not _ID.match(v):
            raise ValueError("id hanya huruf, angka, _ dan -, paling panjang 40")
        return v


class Lajur(_Dasar):
    id: str
    jenis: Literal["video", "teks", "motion", "audio"]
    nama: str = Field("", max_length=60)
    kunci: bool = False
    bisu: bool = False
    sembunyi: bool = False
    volume: float = Field(1.0, ge=0.0, le=2.0)
    item: list[Item] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not _ID.match(v):
            raise ValueError("id hanya huruf, angka, _ dan -, paling panjang 40")
        return v


class Dokumen(_Dasar):
    versi: int = VERSI_DOKUMEN
    id: str
    nama: str = Field(..., min_length=1, max_length=120)
    kanvas: Kanvas = Field(default_factory=Kanvas)
    durasi: int = Field(1, ge=1)
    bahan: dict[str, BahanMeta] = Field(default_factory=dict)
    lajur: list[Lajur] = Field(default_factory=list)
    penanda: list[dict[str, Any]] = Field(default_factory=list)
    ekspor: dict[str, Any] = Field(default_factory=dict)


# Jenis item yang boleh berada di lajur tertentu. Video dan gambar sama-sama
# lajur gambar; audio hanya di lajur audio, supaya urutan tumpuk dan suara
# tidak saling tertukar.
_ITEM_PER_LAJUR = {
    "video": {"video", "gambar"},
    "teks": {"teks"},
    "motion": {"motion"},
    "audio": {"audio"},
}
_PERLU_BAHAN = {"video", "gambar", "audio"}


def migrasi(data: dict) -> dict:
    """
    Menaikkan dokumen lama ke VERSI_DOKUMEN. Satu-satunya tempat migrasi:
    frontend selalu menerima versi terbaru (JOB-4 M1.2).
    """
    versi = data.get("versi", 1)
    if not isinstance(versi, int) or versi < 1:
        raise GagalSkema(["versi: tidak sah"])
    if versi > VERSI_DOKUMEN:
        raise GagalSkema([f"versi: dokumen dibuat OmniClip yang lebih baru (versi {versi})"])
    # Belum ada versi lama; tangga migrasi ditulis di sini saat versi 2 lahir:
    #   if versi == 1: data = _v1_ke_v2(data); versi = 2
    return {**data, "versi": VERSI_DOKUMEN}


def _pesan_pydantic(e: ValidationError) -> list[str]:
    hasil = []
    for galat in e.errors()[:20]:
        jalur = ".".join(str(x) for x in galat["loc"])
        hasil.append(f"{jalur}: {galat['msg']}")
    return hasil


def durasi_isi(dokumen: dict) -> int:
    """Ujung item terakhir di semua lajur, minimal satu bingkai."""
    ujung = 1
    for lajur in dokumen.get("lajur", []):
        for item in lajur.get("item", []):
            ujung = max(ujung, int(item.get("mulai", 0)) + int(item.get("durasi", 1)))
    return ujung


def periksa(data: Any) -> dict:
    """Dokumen mentah -> dokumen sah (dict). Melempar GagalSkema."""
    if not isinstance(data, dict):
        raise GagalSkema(["dokumen harus objek JSON"])
    if len(json.dumps(data, ensure_ascii=False)) > BATAS_BITA:
        raise GagalSkema([f"dokumen lebih dari {BATAS_BITA // 1_000_000} MB"])
    data = migrasi(data)
    try:
        dok = Dokumen.model_validate(data)
    except ValidationError as e:
        raise GagalSkema(_pesan_pydantic(e)) from None

    pesan: list[str] = []
    id_lajur: set[str] = set()
    id_item: set[str] = set()
    jumlah = 0
    for i, lajur in enumerate(dok.lajur):
        if lajur.id in id_lajur:
            pesan.append(f"lajur.{i}.id: '{lajur.id}' dipakai dua kali")
        id_lajur.add(lajur.id)
        for j, item in enumerate(lajur.item):
            jumlah += 1
            tempat = f"lajur.{i}.item.{j}"
            if item.id in id_item:
                pesan.append(f"{tempat}.id: '{item.id}' dipakai dua kali")
            id_item.add(item.id)
            if item.jenis not in _ITEM_PER_LAJUR[lajur.jenis]:
                pesan.append(f"{tempat}: item {item.jenis} tidak boleh di lajur {lajur.jenis}")
            if item.jenis in _PERLU_BAHAN:
                if not item.bahan:
                    pesan.append(f"{tempat}.bahan: wajib untuk item {item.jenis}")
                elif item.bahan not in dok.bahan:
                    pesan.append(f"{tempat}.bahan: '{item.bahan}' tidak ada di dokumen.bahan")
            if item.jenis == "motion" and not item.komponen:
                pesan.append(f"{tempat}.komponen: wajib untuk item motion")
    if jumlah > BATAS_ITEM:
        pesan.append(f"lajur: lebih dari {BATAS_ITEM} item")
    if pesan:
        raise GagalSkema(pesan)

    hasil = dok.model_dump(mode="json")
    hasil["durasi"] = durasi_isi(hasil)
    return hasil


def dokumen_baru(proyek_id: str, nama: str, *, lebar: int, tinggi: int, fps: int) -> dict:
    """Proyek kosong dengan lajur bawaan: satu lajur gambar, teks, animasi, suara."""
    return periksa({
        "versi": VERSI_DOKUMEN,
        "id": proyek_id,
        "nama": nama,
        "kanvas": {"lebar": lebar, "tinggi": tinggi, "fps": fps, "latar": "#000000"},
        "durasi": 1,
        "bahan": {},
        "lajur": [
            {"id": "L1", "jenis": "video", "nama": "Video 1", "item": []},
            {"id": "L2", "jenis": "motion", "nama": "Animasi", "item": []},
            {"id": "L3", "jenis": "teks", "nama": "Teks", "item": []},
            {"id": "L4", "jenis": "audio", "nama": "Suara", "item": []},
        ],
        "penanda": [],
        "ekspor": {},
    })
