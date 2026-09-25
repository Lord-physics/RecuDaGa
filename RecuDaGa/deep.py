"""Extracción por firmas y puente opcional al motor PhotoRec."""
import os
from pathlib import Path
import subprocess
import time

from .validation import validate


SIGNATURES = {
    ".jpg": (b"\xff\xd8\xff", b"\xff\xd9"),
    ".png": (b"\x89PNG\r\n\x1a\n", b"IEND"),
    ".pdf": (b"%PDF-", b"%%EOF"),
}
MAX_FILE = 128 * 1024 * 1024


def carve(source, output, cancel, progress, max_bytes=None):
    """Small built-in signature scan; no filesystem metadata is recovered."""
    entries = []
    output = Path(output) / "firmas"
    output.mkdir(parents=True, exist_ok=True)
    with open(source, "rb", buffering=0) as stream:
        position = 0
        overlap = b""
        while not cancel.is_set() and (max_bytes is None or position < max_bytes):
            limit = 1024 * 1024 if max_bytes is None else min(1024 * 1024, max_bytes - position)
            if not limit:
                break
            try:
                stream.seek(position)
                block = stream.read(limit)
            except OSError as exc:
                entries.append({"origen": str(source), "offset": position, "destino": None,
                                "bytes": 0, "estado": "fallido", "evidencia": f"Error de lectura: {exc}"})
                break
            if not block:
                break
            window = overlap + block
            base = position - len(overlap)
            hits = []
            for extension, (header, _) in SIGNATURES.items():
                start = 0
                while (index := window.find(header, start)) >= 0:
                    offset = base + index
                    if offset >= 0:
                        hits.append((offset, extension))
                    start = index + len(header)
            for offset, extension in sorted(set(hits)):
                if cancel.is_set():
                    break
                footer = SIGNATURES[extension][1]
                try:
                    stream.seek(offset)
                    content = bytearray()
                    found = False
                    while not cancel.is_set() and len(content) < MAX_FILE:
                        chunk = stream.read(min(1024 * 1024, MAX_FILE - len(content)))
                        if not chunk:
                            break
                        previous_length = len(content)
                        content.extend(chunk)
                        end = content.find(footer, max(len(SIGNATURES[extension][0]),
                                                       previous_length - len(footer) + 1))
                        if end >= 0:
                            found = True
                            size = end + len(footer) + (4 if extension == ".png" else 0)
                            if len(content) < size:
                                content.extend(stream.read(size - len(content)))
                            target = output / f"offset_{offset:012x}{extension}"
                            if not target.exists():
                                target.write_bytes(content[:size])
                                valid, evidence = validate(target)
                                entries.append({"origen": str(source), "offset": offset,
                                                "destino": str(target), "bytes": size,
                                                "estado": "validado" if valid is True else "no_verificado" if valid is None else "dañado",
                                                "evidencia": evidence + "; nombre y carpeta originales no recuperables"})
                                progress(len(entries), target.name, entries[-1]["estado"])
                            break
                    if not found and content and not cancel.is_set():
                        partial = output / f"offset_{offset:012x}{extension}.parcial"
                        with open(partial, "wb") as destination:
                            destination.write(content)
                        entries.append({"origen": str(source), "offset": offset,
                                        "destino": str(partial), "bytes": len(content),
                                        "estado": "parcial",
                                        "evidencia": "Firma inicial hallada; no se encontró el marcador final dentro del límite"})
                        progress(len(entries), partial.name, "parcial")
                except OSError as exc:
                    entries.append({"origen": str(source), "offset": offset, "destino": None,
                                    "bytes": 0, "estado": "fallido", "evidencia": f"Error de lectura: {exc}"})
                    progress(len(entries), f"Offset {offset}", "fallido")
            position += len(block)
            overlap = window[-8:]
            progress(len(entries), f"Analizados {position // (1024 * 1024)} MiB", "analizando")
    return entries


def photorec(executable, source, output, cancel, progress):
    """Use the user's separate PhotoRec binary; do not ship GPL binaries."""
    executable = Path(executable)
    if executable.name.lower() not in {"photorec.exe", "photorec_win.exe"} or not executable.is_file():
        raise ValueError("Selecciona photorec_win.exe o photorec.exe de CGSecurity.")
    output = Path(output) / "photorec"
    output.mkdir(parents=True, exist_ok=True)
    command = [str(executable), "/d", str(output), "/cmd", str(source),
               "fileopt,everything,enable,wholespace,search"]
    environment = os.environ.copy()
    if Path(source).is_file():
        environment["__COMPAT_LAYER"] = "RunAsInvoker"
    proc = subprocess.Popen(command, cwd=str(output), stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            env=environment,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    while proc.poll() is None:
        if cancel.is_set():
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            break
        count = sum(len(files) for root, _, files in os.walk(output.parent)
                    if "recup_dir" in Path(root).name)
        progress(count, "PhotoRec analizando", "analizando")
        time.sleep(1)
    entries = []
    for root, _, files in os.walk(output.parent):
        if "recup_dir" not in Path(root).name:
            continue
        for name in files:
            path = Path(root) / name
            valid, evidence = validate(path)
            entries.append({"origen": str(source), "destino": str(path), "bytes": path.stat().st_size,
                            "estado": "validado" if valid is True else "dañado" if valid is False else "no_verificado",
                            "evidencia": evidence + "; PhotoRec no conserva siempre nombres o carpetas"})
    if proc.returncode not in (0, None) and not cancel.is_set():
        entries.append({"origen": str(source), "destino": None, "bytes": 0,
                        "estado": "fallido", "evidencia": f"PhotoRec terminó con código {proc.returncode}"})
    return entries
