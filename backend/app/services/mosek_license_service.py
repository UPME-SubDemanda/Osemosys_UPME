"""Encrypted storage and per-simulation activation of MOSEK license files."""

from __future__ import annotations

import os
import tempfile
import threading
import uuid
from contextlib import AbstractContextManager, contextmanager, nullcontext
from pathlib import Path
from typing import Iterator

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.core.solver_license import SolverLicense

GLOBAL_SCOPE = "global"
MAX_LICENSE_BYTES = 64 * 1024
_environment_lock = threading.RLock()


class MosekLicenseConfigurationError(RuntimeError):
    """License storage is not configured or its encrypted data is unreadable."""


class MosekLicenseService:
    @staticmethod
    def _fernet() -> Fernet:
        configured = get_settings().mosek_license_encryption_key
        key = configured.get_secret_value().strip() if configured else ""
        if not key:
            raise MosekLicenseConfigurationError(
                "El servidor no tiene configurada la clave de cifrado de licencias MOSEK."
            )
        try:
            return Fernet(key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise MosekLicenseConfigurationError(
                "La clave de cifrado MOSEK no tiene un formato válido."
            ) from exc

    @staticmethod
    def user_scope(user_id: uuid.UUID) -> str:
        return f"user:{user_id}"

    @classmethod
    def put(
        cls,
        db: Session,
        *,
        content: bytes,
        scope_key: str,
        updated_by: uuid.UUID,
    ) -> None:
        if not content:
            raise ValueError("El archivo de licencia está vacío.")
        if len(content) > MAX_LICENSE_BYTES:
            raise ValueError("El archivo de licencia supera el límite de 64 KB.")

        ciphertext = cls._fernet().encrypt(content)
        row = db.get(SolverLicense, scope_key)
        if row is None:
            row = SolverLicense(
                scope_key=scope_key,
                encrypted_content=ciphertext,
                updated_by=updated_by,
            )
            db.add(row)
        else:
            row.encrypted_content = ciphertext
            row.updated_by = updated_by
        db.commit()

    @staticmethod
    def delete(db: Session, *, scope_key: str) -> bool:
        row = db.get(SolverLicense, scope_key)
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True

    @staticmethod
    def status(db: Session, *, scope_key: str) -> dict[str, object]:
        row = db.get(SolverLicense, scope_key)
        return {
            "configured": row is not None,
            "updated_at": row.updated_at if row is not None else None,
        }

    @classmethod
    def _decrypt_for_user(cls, db: Session, user_id: uuid.UUID) -> bytes:
        user_scope = cls.user_scope(user_id)
        user_row = db.get(SolverLicense, user_scope)
        row = user_row
        if row is None:
            row = db.get(SolverLicense, GLOBAL_SCOPE)
        if row is None:
            raise MosekLicenseConfigurationError(
                "No hay una licencia MOSEK personal ni global configurada."
            )
        try:
            return cls._fernet().decrypt(row.encrypted_content)
        except InvalidToken as exc:
            raise MosekLicenseConfigurationError(
                "No se pudo descifrar la licencia MOSEK. Verifica que la clave de cifrado "
                "del servidor coincida con la usada al cargarla."
            ) from exc

    @classmethod
    @contextmanager
    def activate_for_user(cls, db: Session, *, user_id: uuid.UUID) -> Iterator[Path]:
        """Materialize a private temporary license file and set MOSEK's file env var."""
        # MOSEK reads MOSEKLM_LICENSE_FILE when creating its environment. The lock
        # prevents overlapping sync simulations in a process from swapping it.
        with _environment_lock:
            content = cls._decrypt_for_user(db, user_id)
            previous = os.environ.get("MOSEKLM_LICENSE_FILE")
            path: Path | None = None
            try:
                fd, raw_path = tempfile.mkstemp(prefix="mosek-", suffix=".lic")
                path = Path(raw_path)
                with os.fdopen(fd, "wb") as license_file:
                    os.fchmod(license_file.fileno(), 0o600)
                    license_file.write(content)
                os.environ["MOSEKLM_LICENSE_FILE"] = str(path)
                yield path
            finally:
                if previous is None:
                    os.environ.pop("MOSEKLM_LICENSE_FILE", None)
                else:
                    os.environ["MOSEKLM_LICENSE_FILE"] = previous
                if path is not None:
                    path.unlink(missing_ok=True)

    @classmethod
    def for_simulation(
        cls, db: Session, *, solver_name: str, user_id: uuid.UUID
    ) -> AbstractContextManager[Path | None]:
        if str(solver_name).lower() != "mosek":
            return nullcontext(None)
        return cls.activate_for_user(db, user_id=user_id)
