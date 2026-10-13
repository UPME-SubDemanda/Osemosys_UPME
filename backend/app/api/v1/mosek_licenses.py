"""Upload and status endpoints for personal and global MOSEK licenses."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_system_settings_manager
from app.db.session import get_db
from app.models import User
from app.schemas.mosek_license import MosekLicenseStatus
from app.services.mosek_license_service import (
    GLOBAL_SCOPE,
    MAX_LICENSE_BYTES,
    MosekLicenseConfigurationError,
    MosekLicenseService,
)

router = APIRouter()


def _read_license_file(upload: UploadFile) -> bytes:
    content = upload.file.read(MAX_LICENSE_BYTES + 1)
    if not content:
        raise HTTPException(status_code=422, detail="El archivo de licencia está vacío.")
    if len(content) > MAX_LICENSE_BYTES:
        raise HTTPException(
            status_code=413, detail="El archivo de licencia supera el límite de 64 KB."
        )
    return content


def _status(db: Session, scope_key: str) -> MosekLicenseStatus:
    return MosekLicenseStatus(**MosekLicenseService.status(db, scope_key=scope_key))


def _upload(db: Session, *, upload: UploadFile, scope_key: str, user: User) -> MosekLicenseStatus:
    try:
        MosekLicenseService.put(
            db,
            content=_read_license_file(upload),
            scope_key=scope_key,
            updated_by=user.id,
        )
    except MosekLicenseConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _status(db, scope_key)


@router.get("/users/me/mosek-license", response_model=MosekLicenseStatus)
def get_personal_license_status(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> MosekLicenseStatus:
    return _status(db, MosekLicenseService.user_scope(current_user.id))


@router.post("/users/me/mosek-license", response_model=MosekLicenseStatus)
def upload_personal_license(
    license_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MosekLicenseStatus:
    return _upload(
        db,
        upload=license_file,
        scope_key=MosekLicenseService.user_scope(current_user.id),
        user=current_user,
    )


@router.delete("/users/me/mosek-license", response_model=MosekLicenseStatus)
def delete_personal_license(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> MosekLicenseStatus:
    scope_key = MosekLicenseService.user_scope(current_user.id)
    MosekLicenseService.delete(db, scope_key=scope_key)
    return _status(db, scope_key)


@router.get(
    "/admin/system-settings/mosek-license", response_model=MosekLicenseStatus
)
def get_global_license_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_system_settings_manager),
) -> MosekLicenseStatus:
    return _status(db, GLOBAL_SCOPE)


@router.post(
    "/admin/system-settings/mosek-license", response_model=MosekLicenseStatus
)
def upload_global_license(
    license_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_system_settings_manager),
) -> MosekLicenseStatus:
    return _upload(
        db,
        upload=license_file,
        scope_key=GLOBAL_SCOPE,
        user=current_user,
    )


@router.delete(
    "/admin/system-settings/mosek-license", response_model=MosekLicenseStatus
)
def delete_global_license(
    db: Session = Depends(get_db),
    _: User = Depends(get_system_settings_manager),
) -> MosekLicenseStatus:
    MosekLicenseService.delete(db, scope_key=GLOBAL_SCOPE)
    return _status(db, GLOBAL_SCOPE)
