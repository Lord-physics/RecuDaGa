"""Informe JSON at�mico y legible."""
from datetime import datetime, timezone
import json
from pathlib import Path


def save_report(output_dir, mode, source, entries, cancelled=False):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "modo": mode,
        "origen": str(source),
        "cancelado": cancelled,
        "total": len(entries),
        "resultados": entries,
    }
    path = output_dir / "informe.json"
    temp = output_dir / "informe.json.tmp"
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    return path
