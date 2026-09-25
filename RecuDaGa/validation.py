"""Validadores: devolver evidencia concreta, nunca inferir reparación por extensión."""
import bz2
import gzip
import lzma
from pathlib import Path
import tarfile
import wave
import zipfile
import zlib


def _png(path):
    with open(path, "rb") as f:
        if f.read(8) != b"\x89PNG\r\n\x1a\n":
            return False, "Firma PNG incorrecta"
        seen_end = False
        while True:
            size_raw = f.read(4)
            if len(size_raw) != 4:
                break
            size = int.from_bytes(size_raw, "big")
            if size > 256 * 1024 * 1024:
                return False, "Bloque PNG demasiado grande"
            name = f.read(4)
            data = f.read(size)
            crc_raw = f.read(4)
            if len(name) != 4 or len(data) != size or len(crc_raw) != 4:
                return False, "Bloque PNG truncado"
            if zlib.crc32(name + data) & 0xffffffff != int.from_bytes(crc_raw, "big"):
                return False, "CRC PNG incorrecto"
            if name == b"IEND":
                seen_end = True
                break
        return (seen_end, "Bloques PNG y CRC correctos" if seen_end else "Falta IEND")


def _archive(path, kind):
    try:
        if kind == "zip":
            with zipfile.ZipFile(path) as f:
                bad = f.testzip()
                return (bad is None, "Entradas ZIP y CRC correctos" if bad is None else f"Entrada ZIP dañada: {bad}")
        if kind == "tar":
            with tarfile.open(path) as f:
                for member in f:
                    if member.isfile():
                        stream = f.extractfile(member)
                        if stream:
                            while stream.read(1024 * 1024):
                                pass
            return True, "Entradas TAR legibles"
        opener = {"gz": gzip.open, "bz2": bz2.open, "xz": lzma.open}[kind]
        with opener(path, "rb") as f:
            while f.read(1024 * 1024):
                pass
        return True, f"Flujo {kind.upper()} descomprimido completamente"
    except (OSError, EOFError, ValueError, RuntimeError, zipfile.BadZipFile,
            tarfile.TarError, zlib.error, lzma.LZMAError) as exc:
        return False, f"No se pudo validar {kind}: {exc}"


def validate(path):
    path = Path(path)
    ext = path.suffix.lower()
    if ext in {".zip", ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp", ".epub", ".jar"}:
        return _archive(path, "zip")
    if ext in {".tar", ".tgz"}:
        return _archive(path, "tar")
    if ext in {".gz", ".bz2", ".xz"}:
        return _archive(path, ext[1:])
    if ext == ".png":
        return _png(path)
    try:
        with open(path, "rb") as f:
            head = f.read(32)
            size = path.stat().st_size
            f.seek(max(0, size - 4096))
            tail = f.read()
        if ext in {".jpg", ".jpeg"}:
            ok = head.startswith(b"\xff\xd8\xff") and b"\xff\xd9" in tail
            return (None if ok else False, "Marcadores JPEG presentes; decodificación no comprobada" if ok else "Marcadores JPEG incompletos")
        if ext == ".pdf":
            ok = head.startswith(b"%PDF-") and b"%%EOF" in tail
            return (None if ok else False, "Marcadores PDF presentes; estructura interna no comprobada" if ok else "Marcadores PDF incompletos")
        if ext == ".gif":
            ok = head[:6] in {b"GIF87a", b"GIF89a"} and b"\x3b" in tail
            return (None if ok else False, "Marcadores GIF presentes; imagen no decodificada" if ok else "Marcadores GIF incompletos")
        if ext == ".wav":
            with wave.open(str(path), "rb") as f:
                expected = f.getnframes() * f.getnchannels() * f.getsampwidth()
                actual = 0
                while actual < expected:
                    frames = f.readframes(min(65536, f.getnframes()))
                    if not frames:
                        break
                    actual += len(frames)
                if actual != expected:
                    return False, "Datos WAV truncados"
            return True, "Cabecera y fotogramas WAV legibles"
        if ext in {".mp3", ".mp4", ".mkv", ".avi", ".mov", ".flac", ".7z", ".rar", ".doc", ".xls", ".ppt"}:
            return None, "Formato reconocido; validación completa no implementada"
        return None, "Sin validador para este formato"
    except (OSError, EOFError, ValueError, wave.Error) as exc:
        return False, f"No se pudo leer o validar: {exc}"
