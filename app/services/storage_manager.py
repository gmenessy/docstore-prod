"""
Storage-Manager – Datei-Cleanup, TTL, Speicher-Monitoring.

Verwaltet den Lebenszyklus hochgeladener Dateien:
- Automatisches Aufraumen nach TTL (Standard: 30 Tage)
- Speicher-Limits pro Store
- Disk-Usage-Monitoring
- Orphan-Detection (Dateien ohne DB-Eintrag)
"""
import logging
import os
import shutil
import time
from pathlib import Path
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)

# Speicher-Limits aus Konfiguration
MAX_STORE_SIZE_MB = settings.max_store_size_mb
MAX_TOTAL_SIZE_MB = settings.max_total_size_mb
FILE_TTL_DAYS = settings.file_ttl_days
UPLOAD_TTL_HOURS = settings.upload_ttl_hours


@dataclass
class StorageStats:
    total_mb: float = 0.0
    used_mb: float = 0.0
    free_mb: float = 0.0
    usage_percent: float = 0.0
    stores_count: int = 0
    files_count: int = 0
    largest_store: str = ""
    largest_store_mb: float = 0.0


def get_storage_stats() -> dict:
    """Gesamtstatistiken zum Speicherverbrauch."""
    data_dir = settings.stores_dir
    upload_dir = settings.upload_dir

    # Disk-Statistiken
    try:
        disk = shutil.disk_usage(str(data_dir))
        total_mb = disk.total / (1024 * 1024)
        free_mb = disk.free / (1024 * 1024)
        used_mb = (disk.total - disk.free) / (1024 * 1024)
        usage_pct = (1 - disk.free / disk.total) * 100
    except OSError:
        total_mb = free_mb = used_mb = 0.0
        usage_pct = 0.0

    # Store-Groessen
    stores = {}
    total_files = 0
    if data_dir.exists():
        for store_dir in data_dir.iterdir():
            if store_dir.is_dir():
                size = _dir_size(store_dir)
                count = sum(1 for _ in store_dir.rglob("*") if _.is_file())
                stores[store_dir.name] = {"size_mb": size / (1024 * 1024), "files": count}
                total_files += count

    # Upload-Dir
    upload_files = 0
    upload_size = 0
    if upload_dir.exists():
        for f in upload_dir.rglob("*"):
            if f.is_file():
                upload_files += 1
                upload_size += f.stat().st_size

    largest = max(stores.items(), key=lambda x: x[1]["size_mb"]) if stores else ("", {"size_mb": 0})

    app_used_mb = sum(s["size_mb"] for s in stores.values()) + upload_size / (1024 * 1024)

    return {
        "disk_total_mb": round(total_mb, 1),
        "disk_free_mb": round(free_mb, 1),
        "disk_used_mb": round(used_mb, 1),
        "usage_percent": round(usage_pct, 1),
        "app_used_mb": round(app_used_mb, 1),
        "stores_count": len(stores),
        "total_files": total_files,
        "upload_pending": upload_files,
        "upload_pending_mb": round(upload_size / (1024 * 1024), 1),
        "largest_store": largest[0],
        "largest_store_mb": round(largest[1]["size_mb"], 1) if isinstance(largest[1], dict) else 0,
        "stores": stores,
        "limits": {
            "max_store_mb": MAX_STORE_SIZE_MB,
            "max_total_mb": MAX_TOTAL_SIZE_MB,
            "file_ttl_days": FILE_TTL_DAYS,
        },
    }


def cleanup_old_files(max_age_days: int = FILE_TTL_DAYS) -> dict:
    """
    Alte Dateien aufraeumen.
    - Upload-Dir: Dateien aelter als UPLOAD_TTL_HOURS
    - Store-Dirs: Nur explizit markierte Temp-Dateien
    """
    deleted_files = 0
    freed_bytes = 0
    errors = []
    now = time.time()

    # Upload-Dir: Nicht verarbeitete Uploads aufraeumen
    upload_cutoff = now - (UPLOAD_TTL_HOURS * 3600)
    if settings.upload_dir.exists():
        for f in settings.upload_dir.rglob("*"):
            if f.is_file() and f.stat().st_mtime < upload_cutoff:
                try:
                    size = f.stat().st_size
                    f.unlink()
                    deleted_files += 1
                    freed_bytes += size
                    logger.debug(f"Cleanup: {f.name} geloescht ({size // 1024} KB)")
                except OSError as e:
                    errors.append(str(e))

    # Temp-Dateien in Store-Dirs (mit .tmp Suffix)
    file_cutoff = now - (max_age_days * 86400)
    if settings.stores_dir.exists():
        for f in settings.stores_dir.rglob("*.tmp"):
            if f.is_file() and f.stat().st_mtime < file_cutoff:
                try:
                    size = f.stat().st_size
                    f.unlink()
                    deleted_files += 1
                    freed_bytes += size
                except OSError as e:
                    errors.append(str(e))

    result = {
        "deleted_files": deleted_files,
        "freed_bytes": freed_bytes,
        "freed_mb": round(freed_bytes / (1024 * 1024), 2),
        "errors": errors[:10],
    }
    if deleted_files > 0:
        logger.info(f"Cleanup: {deleted_files} Dateien geloescht, {result['freed_mb']:.1f} MB freigegeben")
    return result


def check_store_limit(store_id: str) -> dict:
    """Pruefen ob ein Store sein Speicher-Limit erreicht hat."""
    store_dir = settings.stores_dir / store_id
    if not store_dir.exists():
        return {"ok": True, "used_mb": 0, "limit_mb": MAX_STORE_SIZE_MB}

    used = _dir_size(store_dir) / (1024 * 1024)
    return {
        "ok": used < MAX_STORE_SIZE_MB,
        "used_mb": round(used, 1),
        "limit_mb": MAX_STORE_SIZE_MB,
        "percent": round(used / MAX_STORE_SIZE_MB * 100, 1),
    }


def find_orphan_files(store_id: str, known_paths: set[str]) -> list[str]:
    """Dateien finden, die in einem Store-Dir liegen aber keinem Dokument zugeordnet sind."""
    store_dir = settings.stores_dir / store_id
    if not store_dir.exists():
        return []

    orphans = []
    for f in store_dir.rglob("*"):
        if f.is_file() and str(f) not in known_paths:
            orphans.append(str(f))
    return orphans


def _dir_size(path: Path) -> int:
    """Gesamtgroesse eines Verzeichnisses in Bytes."""
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total
