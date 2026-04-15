"""routers/backup.py - Backup e restauração do banco de dados (somente admin)."""

import gzip
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth import ROLE_ADMIN, require_roles

router = APIRouter(prefix="/backup", tags=["Backup"])

_REQUIRE_ADMIN = Depends(require_roles(ROLE_ADMIN))

# ============================================
# Config persistida em disco
# ============================================

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_CONFIG_FILE = _BACKEND_DIR / "backup_config.json"
_DEFAULT_BACKUP_DIR = str(_BACKEND_DIR / "backups")


def _load_config() -> dict:
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_config(cfg: dict):
    _CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def _get_config() -> dict:
    cfg = _load_config()
    db_url = os.getenv("DATABASE_URL", "")
    return {
        "backup_dir": cfg.get("backup_dir", _DEFAULT_BACKUP_DIR),
        "backup_keep_dias": cfg.get("backup_keep_dias", 30),
        "postgres_container": cfg.get("postgres_container", "postgres-radio"),
        "cron_agendamento": "Todo dia às 02:00 (cron: 0 2 * * *)",
        "db_url_configurada": bool(db_url),
    }


# ============================================
# Helpers: pg_dump / psql via Docker ou local
# ============================================

def _parse_db_url() -> dict:
    raw = os.getenv("DATABASE_URL", "")
    if not raw:
        raise HTTPException(status_code=500, detail="DATABASE_URL não configurada.")
    # Remove driver prefix: postgresql+psycopg2:// → postgresql://
    clean = re.sub(r"^\w+\+\w+://", "postgresql://", raw)
    p = urlparse(clean)
    return {
        "user": p.username or "",
        "password": p.password or "",
        "host": p.hostname or "localhost",
        "port": str(p.port or 5432),
        "dbname": (p.path or "").lstrip("/"),
    }


def _container_running(name: str) -> bool:
    try:
        r = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=5,
        )
        return name in r.stdout.splitlines()
    except Exception:
        return False


def _run_backup(backup_dir: str, container: str) -> Path:
    db = _parse_db_url()
    Path(backup_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out = Path(backup_dir) / f"radio_ads_{ts}.sql.gz"

    if _container_running(container):
        result = subprocess.run(
            ["docker", "exec", container,
             "pg_dump", "-U", db["user"], "-d", db["dbname"]],
            capture_output=True, timeout=120,
        )
    else:
        env = os.environ.copy()
        env["PGPASSWORD"] = db["password"]
        result = subprocess.run(
            ["pg_dump", "-h", db["host"], "-p", db["port"],
             "-U", db["user"], "-d", db["dbname"], "--no-password"],
            capture_output=True, env=env, timeout=120,
        )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"pg_dump falhou: {result.stderr.decode(errors='replace')[:400]}",
        )

    with gzip.open(out, "wb") as gz:
        gz.write(result.stdout)

    return out


def _run_restore(filepath: Path, container: str):
    db = _parse_db_url()

    with gzip.open(filepath, "rb") as gz:
        sql_bytes = gz.read()

    if _container_running(container):
        result = subprocess.run(
            ["docker", "exec", "-i", container,
             "psql", "-U", db["user"], "-d", db["dbname"]],
            input=sql_bytes, capture_output=True, timeout=300,
        )
    else:
        env = os.environ.copy()
        env["PGPASSWORD"] = db["password"]
        result = subprocess.run(
            ["psql", "-h", db["host"], "-p", db["port"],
             "-U", db["user"], "-d", db["dbname"], "--no-password"],
            input=sql_bytes, capture_output=True, env=env, timeout=300,
        )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"Restauração falhou: {result.stderr.decode(errors='replace')[:400]}",
        )


def _purge_old(backup_dir: str, keep_dias: int):
    from datetime import timedelta
    limite = datetime.now(timezone.utc) - timedelta(days=keep_dias)
    removidos = 0
    for f in Path(backup_dir).glob("radio_ads_*.sql.gz"):
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        if mtime < limite:
            f.unlink()
            removidos += 1
    return removidos


# ============================================
# Schemas
# ============================================

class BackupConfig(BaseModel):
    backup_dir: str = Field(..., description="Caminho absoluto para a pasta de backups")
    backup_keep_dias: int = Field(30, ge=1, le=365, description="Dias de retenção")
    postgres_container: str = Field("postgres-radio", description="Nome do container Docker do PostgreSQL")


class BackupConfigResponse(BackupConfig):
    cron_agendamento: str
    db_url_configurada: bool


class BackupArquivo(BaseModel):
    arquivo: str
    tamanho_mb: float
    data_criacao: str


class BackupRestaurarPayload(BaseModel):
    arquivo: str = Field(..., description="Nome do arquivo de backup (apenas o nome, sem path)")
    confirmacao: str = Field(..., description="Digite CONFIRMAR para prosseguir")


# ============================================
# Endpoints
# ============================================

@router.get("/config", response_model=BackupConfigResponse)
def obter_config(_=_REQUIRE_ADMIN):
    return _get_config()


@router.put("/config", response_model=BackupConfigResponse)
def salvar_config(payload: BackupConfig, _=_REQUIRE_ADMIN):
    cfg = _load_config()
    cfg["backup_dir"] = payload.backup_dir
    cfg["backup_keep_dias"] = payload.backup_keep_dias
    cfg["postgres_container"] = payload.postgres_container
    _save_config(cfg)
    return _get_config()


@router.post("/executar")
def executar_backup(_=_REQUIRE_ADMIN):
    cfg = _get_config()
    out = _run_backup(cfg["backup_dir"], cfg["postgres_container"])
    _purge_old(cfg["backup_dir"], cfg["backup_keep_dias"])
    size_mb = round(out.stat().st_size / 1024 / 1024, 3)
    return {
        "success": True,
        "arquivo": out.name,
        "tamanho_mb": size_mb,
        "mensagem": f"Backup criado: {out.name} ({size_mb} MB)",
    }


@router.get("/listar", response_model=List[BackupArquivo])
def listar_backups(_=_REQUIRE_ADMIN):
    cfg = _get_config()
    pasta = Path(cfg["backup_dir"])
    if not pasta.exists():
        return []
    arquivos = sorted(pasta.glob("radio_ads_*.sql.gz"), reverse=True)
    result = []
    for f in arquivos:
        stat = f.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        result.append(BackupArquivo(
            arquivo=f.name,
            tamanho_mb=round(stat.st_size / 1024 / 1024, 3),
            data_criacao=mtime,
        ))
    return result


@router.post("/restaurar")
def restaurar_backup(payload: BackupRestaurarPayload, _=_REQUIRE_ADMIN):
    if payload.confirmacao != "CONFIRMAR":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Digite CONFIRMAR no campo de confirmação para prosseguir.",
        )

    cfg = _get_config()
    # Segurança: só permite nomes de arquivo simples (sem path traversal)
    nome = Path(payload.arquivo).name
    if nome != payload.arquivo or not nome.endswith(".sql.gz"):
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")

    filepath = Path(cfg["backup_dir"]) / nome
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Arquivo não encontrado: {nome}")

    _run_restore(filepath, cfg["postgres_container"])
    return {
        "success": True,
        "mensagem": f"Banco restaurado a partir de {nome}. Reinicie a API para garantir consistência.",
    }
