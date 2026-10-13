from __future__ import annotations

import os
import uuid
from types import SimpleNamespace

from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.models.core.solver_license import SolverLicense
from app.services import mosek_license_service as license_module


class _MemorySession:
    def __init__(self) -> None:
        self.rows: dict[str, SolverLicense] = {}

    def get(self, model, key):
        assert model is SolverLicense
        return self.rows.get(key)

    def add(self, row: SolverLicense) -> None:
        self.rows[row.scope_key] = row

    def delete(self, row: SolverLicense) -> None:
        self.rows.pop(row.scope_key, None)

    def commit(self) -> None:
        pass


def _configure_encryption(monkeypatch) -> None:
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setattr(
        license_module,
        "get_settings",
        lambda: SimpleNamespace(mosek_license_encryption_key=SecretStr(key)),
    )


def test_license_is_encrypted_and_personal_license_takes_precedence(monkeypatch) -> None:
    _configure_encryption(monkeypatch)
    db = _MemorySession()
    user_id = uuid.uuid4()
    global_license = b"GLOBAL_MOSEK_LICENSE"
    personal_license = b"PERSONAL_MOSEK_LICENSE"

    license_module.MosekLicenseService.put(
        db,
        content=global_license,
        scope_key=license_module.GLOBAL_SCOPE,
        updated_by=user_id,
    )
    user_scope = license_module.MosekLicenseService.user_scope(user_id)
    license_module.MosekLicenseService.put(
        db,
        content=personal_license,
        scope_key=user_scope,
        updated_by=user_id,
    )

    assert global_license not in db.rows[license_module.GLOBAL_SCOPE].encrypted_content
    assert personal_license not in db.rows[user_scope].encrypted_content
    assert license_module.MosekLicenseService._decrypt_for_user(db, user_id) == personal_license


def test_license_activation_uses_private_temp_file_and_restores_environment(
    monkeypatch,
) -> None:
    _configure_encryption(monkeypatch)
    db = _MemorySession()
    user_id = uuid.uuid4()
    content = b"PERSONAL_MOSEK_LICENSE"
    license_module.MosekLicenseService.put(
        db,
        content=content,
        scope_key=license_module.MosekLicenseService.user_scope(user_id),
        updated_by=user_id,
    )
    monkeypatch.setenv("MOSEKLM_LICENSE_FILE", "/existing/license.lic")

    path = None
    with license_module.MosekLicenseService.activate_for_user(db, user_id=user_id) as path:
        assert path.read_bytes() == content
        assert path.stat().st_mode & 0o777 == 0o600
        assert os.environ["MOSEKLM_LICENSE_FILE"] == str(path)

    assert path is not None and not path.exists()
    assert os.environ["MOSEKLM_LICENSE_FILE"] == "/existing/license.lic"


def test_license_activation_falls_back_to_global_license(monkeypatch) -> None:
    _configure_encryption(monkeypatch)
    db = _MemorySession()
    user_id = uuid.uuid4()
    global_license = b"GLOBAL_MOSEK_LICENSE"
    license_module.MosekLicenseService.put(
        db,
        content=global_license,
        scope_key=license_module.GLOBAL_SCOPE,
        updated_by=user_id,
    )

    assert license_module.MosekLicenseService._decrypt_for_user(db, user_id) == global_license
