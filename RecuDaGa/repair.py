"""Reparaciones explícitas sobre copias; nunca sobre el origen."""
from pathlib import Path
import shutil
import tempfile
import zipfile

from .validation import validate


ZIP_EXTENSIONS = {".zip", ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp", ".epub", ".jar"}


def repair_zip(copy_path):
    """Rebuild an archive from individually readable entries, if some failed."""
    copy_path = Path(copy_path)
    if copy_path.suffix.lower() not in ZIP_EXTENSIONS:
        return None, "Sin reparación automática para este formato"
    target = copy_path.with_name(copy_path.stem + ".reparado" + copy_path.suffix)
    good = bad = 0
    try:
        with zipfile.ZipFile(copy_path) as source, zipfile.ZipFile(target, "w") as output:
            for info in source.infolist():
                if info.is_dir():
                    output.writestr(info, b"")
                    continue
                try:
                    with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as temporary:
                        with source.open(info) as entry:
                            shutil.copyfileobj(entry, temporary, 1024 * 1024)
                        temporary.seek(0)
                        with output.open(info, "w") as rebuilt:
                            shutil.copyfileobj(temporary, rebuilt, 1024 * 1024)
                except (OSError, RuntimeError, ValueError, zipfile.BadZipFile):
                    bad += 1
                    continue
                good += 1
        if not good or not bad:
            target.unlink(missing_ok=True)
            return None, "No hay entradas dañadas aislables o no quedan entradas sanas"
        valid, evidence = validate(target)
        if valid:
            return target, f"ZIP reconstruido con {good} entradas sanas; {bad} omitidas. {evidence}"
        target.unlink(missing_ok=True)
        return None, f"La copia reconstruida no pasó la validación: {evidence}"
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        target.unlink(missing_ok=True)
        return None, f"No se pudo reconstruir ZIP: {exc}"
