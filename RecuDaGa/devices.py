"""Enumeración y comprobaciones de origen/destino en Windows."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import string


def _powershell(script):
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=25,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout).strip()[:400])
    return json.loads(completed.stdout or "[]")


def inventory():
    """Return disks and letter-to-disk map; fail closed if enumeration fails."""
    script = (
        "$ErrorActionPreference='Stop';"
        "$d=@(Get-Disk | Select-Object Number,FriendlyName,Size,OperationalStatus,BusType);"
        "$p=@(Get-Partition | Where-Object DriveLetter | Select-Object DiskNumber,DriveLetter);"
        "@{disks=$d;partitions=$p} | ConvertTo-Json -Depth 4 -Compress"
    )
    try:
        data = _powershell(script)
        disks = data.get("disks") or []
        parts = data.get("partitions") or []
        if isinstance(disks, dict):
            disks = [disks]
        if isinstance(parts, dict):
            parts = [parts]
        letters = {str(p["DriveLetter"]).upper(): int(p["DiskNumber"])
                   for p in parts if p.get("DriveLetter")}
        return disks, letters
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, RuntimeError) as exc:
        disks, letters = _inventory_native()
        if letters:
            return disks, letters
        raise RuntimeError(f"No se pudo consultar la información de discos: {exc}") from exc


def _inventory_native():
    """Fallback: map mounted drive letters through a read-only Windows IOCTL."""
    if os.name != "nt":
        return [], {}
    kernel = ctypes.windll.kernel32
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                    ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.DeviceIoControl.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p,
                                        ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
                                        ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
    kernel.DeviceIoControl.restype = ctypes.c_int
    letters = {}
    for letter in string.ascii_uppercase:
        if not os.path.isdir(f"{letter}:\\"):
            continue
        handle = kernel.CreateFileW("\\\\.\\" + letter + ":", 0, 3, None, 3, 0, None)
        if handle in (None, ctypes.c_void_p(-1).value):
            continue
        try:
            data = (ctypes.c_uint32 * 3)()
            returned = ctypes.c_uint32()
            ok = kernel.DeviceIoControl(handle, 0x2D1080, None, 0, ctypes.byref(data),
                                        ctypes.sizeof(data), ctypes.byref(returned), None)
            if ok and returned.value >= 12:
                letters[letter] = int(data[1])
        finally:
            kernel.CloseHandle(ctypes.c_void_p(handle))
    numbers = set(letters.values())
    for number in range(32):
        handle = kernel.CreateFileW(f"\\\\.\\PhysicalDrive{number}", 0, 3, None, 3, 0, None)
        if handle not in (None, ctypes.c_void_p(-1).value):
            numbers.add(number)
            kernel.CloseHandle(ctypes.c_void_p(handle))
    disks = [{"Number": number, "FriendlyName": "Disco físico (nombre no disponible)",
              "OperationalStatus": "Detectado"} for number in sorted(numbers)]
    return disks, letters


def disk_for_path(path, letters):
    drive = Path(path).resolve().drive
    if len(drive) < 2 or drive[1] != ":":
        raise ValueError("La ruta debe estar en una unidad local con letra.")
    if os.name == "nt":
        buffer = ctypes.create_unicode_buffer(1024)
        root = str(Path(path).resolve())
        if not ctypes.windll.kernel32.GetVolumePathNameW(root, buffer, len(buffer)):
            raise ValueError("No se pudo identificar el volumen de la ruta.")
        if buffer.value.upper() != drive.upper() + "\\":
            raise ValueError("Volumen montado en carpeta: no se puede verificar su disco físico.")
    disk = letters.get(drive[0].upper())
    if disk is None:
        raise ValueError(f"No se pudo identificar el disco físico de {drive}.")
    return disk


def check_destination(source_disk, destination, letters):
    dest = Path(destination).resolve()
    if not dest.is_dir():
        raise ValueError("El destino debe ser una carpeta existente.")
    if disk_for_path(dest, letters) == source_disk:
        raise ValueError("El destino está en el mismo disco físico que el origen.")
    return dest


def probe_physical(number):
    """Read one byte from a Windows physical device without writing to it."""
    path = rf"\\.\PhysicalDrive{int(number)}"
    try:
        with open(path, "rb", buffering=0) as stream:
            sample = stream.read(1)
        return "Lectura permitida" if sample else "Dispositivo sin datos legibles"
    except PermissionError:
        return "Detectado, pero Windows exige permisos de administrador para leerlo"
    except OSError as exc:
        return f"Detectado, pero no se pudo leer: {exc}"


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False
