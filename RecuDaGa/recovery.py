"""Rescate de archivos accesibles preservando �rbol y estado real de lectura."""
import os
from pathlib import Path

from .repair import repair_zip
from .validation import validate


def recover_tree(source, output, cancel, progress):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_dir():
        raise ValueError("Selecciona una carpeta o unidad accesible.")
    if output == source or source in output.parents:
        raise ValueError("El destino no puede estar dentro del origen.")
    entries = []
    for root, dirs, files in os.walk(source, followlinks=False):
        if cancel.is_set():
            break
        dirs[:] = [d for d in dirs if not (Path(root) / d).is_symlink()]
        for filename in files:
            if cancel.is_set():
                break
            original = Path(root) / filename
            if original.is_symlink():
                continue
            relative = original.relative_to(source)
            target = output / "archivos" / relative
            copied = 0
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(original, "rb") as src, open(target, "xb") as dst:
                    while not cancel.is_set():
                        block = src.read(1024 * 1024)
                        if not block:
                            break
                        dst.write(block)
                        copied += len(block)
                if cancel.is_set():
                    status, evidence = "parcial", "Operaci�n cancelada antes de completar la lectura"
                else:
                    valid, evidence = validate(target)
                    status = "validado" if valid is True else "da�ado" if valid is False else "no_verificado"
                item = {"origen": str(original), "destino": str(target), "bytes": copied,
                        "estado": status, "evidencia": evidence}
                if status == "da�ado" and not cancel.is_set():
                    repaired, detail = repair_zip(target)
                    item["reparacion"] = detail
                    if repaired:
                        item["estado"] = "reparado_parcialmente"
                        item["archivo_reparado"] = str(repaired)
                entries.append(item)
            except (OSError, ValueError) as exc:
                entries.append({"origen": str(original), "destino": str(target) if copied else None,
                                "bytes": copied, "estado": "parcial" if copied else "fallido",
                                "evidencia": str(exc)})
            progress(len(entries), str(relative), entries[-1]["estado"])
    return entries
