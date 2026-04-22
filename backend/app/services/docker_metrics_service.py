"""Consulta métricas de memoria de servicios Docker vía socket Unix."""

from __future__ import annotations

import http.client
import json
import os
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from time import monotonic
from urllib.parse import quote

from app.core.config import get_settings


class _UnixSocketHTTPConnection(http.client.HTTPConnection):
    """Conexión HTTP mínima contra el socket Unix del daemon Docker."""

    def __init__(self, socket_path: str, *, timeout: float) -> None:
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self) -> None:  # pragma: no cover
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


class DockerMetricsService:
    """Obtiene memoria por servicio del stack Docker actual.

    - Filtra por proyecto Compose del propio contenedor (evita contar RAM de
      otros stacks corriendo en el mismo host) + por lista de servicios.
    - Usa `?one-shot=true` en el endpoint de stats, que retorna al instante en
      lugar de bloquear ~1 s muestreando CPU.
    - Paraleliza las llamadas por contenedor con un ThreadPool.
    """

    _cache_lock = threading.Lock()
    _cached_service_memory: list[dict] = []
    _cache_expires_at: float = 0.0
    _detected_project: str | None = None

    @staticmethod
    def _request_json(path: str, *, timeout: float | None = None) -> object:
        settings = get_settings()
        t = timeout if timeout is not None else float(settings.docker_metrics_timeout_seconds)
        conn = _UnixSocketHTTPConnection(settings.docker_socket_path, timeout=max(0.05, t))
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            raw = response.read()
            if response.status >= 400:
                raise RuntimeError(
                    f"Docker API error {response.status}: {raw.decode('utf-8', errors='ignore')}"
                )
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
        finally:
            conn.close()

    @classmethod
    def _get_cached_service_memory(cls) -> list[dict]:
        now = monotonic()
        with cls._cache_lock:
            if now < cls._cache_expires_at:
                return [dict(item) for item in cls._cached_service_memory]
        return []

    @classmethod
    def _get_last_cached_service_memory(cls) -> list[dict]:
        with cls._cache_lock:
            return [dict(item) for item in cls._cached_service_memory]

    @classmethod
    def _set_cached_service_memory(cls, items: list[dict]) -> None:
        settings = get_settings()
        ttl = max(0.0, float(settings.docker_metrics_cache_ttl_seconds))
        with cls._cache_lock:
            cls._cached_service_memory = [dict(item) for item in items]
            cls._cache_expires_at = monotonic() + ttl

    @classmethod
    def _resolve_project(cls) -> str:
        """Retorna el proyecto Compose a filtrar.

        Prioridad: setting `docker_metrics_project` > auto-detección via
        etiqueta del propio contenedor > env `COMPOSE_PROJECT_NAME` > "" (sin
        filtro por proyecto).
        """
        settings = get_settings()
        explicit = (settings.docker_metrics_project or "").strip()
        if explicit:
            return explicit

        if cls._detected_project is not None:
            return cls._detected_project

        project = ""
        hostname = os.environ.get("HOSTNAME", "").strip()
        if hostname:
            try:
                info = cls._request_json(f"/containers/{quote(hostname, safe='')}/json")
                if isinstance(info, dict):
                    labels = ((info.get("Config") or {}).get("Labels")) or {}
                    project = str(labels.get("com.docker.compose.project") or "").strip()
            except (FileNotFoundError, OSError, RuntimeError, json.JSONDecodeError):
                project = ""

        if not project:
            project = os.environ.get("COMPOSE_PROJECT_NAME", "").strip()

        cls._detected_project = project
        return project

    @classmethod
    def _fetch_memory_usage(cls, container_id: str) -> int | None:
        """Obtiene `memory_stats.usage` con `one-shot=true` (no bloquea)."""
        try:
            stats = cls._request_json(
                f"/containers/{quote(container_id, safe='')}/stats?stream=false&one-shot=true"
            )
        except (OSError, RuntimeError, json.JSONDecodeError):
            return None
        if not isinstance(stats, dict):
            return None
        memory_stats = stats.get("memory_stats")
        if not isinstance(memory_stats, dict):
            return None
        usage = memory_stats.get("usage")
        if not isinstance(usage, (int, float)):
            return None
        return int(usage)

    @staticmethod
    def list_service_memory() -> list[dict]:
        """Retorna uso de memoria por servicio compose rastreado."""
        settings = get_settings()
        tracked = set(settings.docker_metrics_services_list())
        if not tracked:
            return []

        cached = DockerMetricsService._get_cached_service_memory()
        if cached:
            return cached

        project_filter = DockerMetricsService._resolve_project()

        try:
            containers = DockerMetricsService._request_json("/containers/json?all=0")
        except (FileNotFoundError, OSError, RuntimeError, json.JSONDecodeError):
            return DockerMetricsService._get_last_cached_service_memory()

        if not isinstance(containers, list):
            return DockerMetricsService._get_last_cached_service_memory()

        # Seleccionamos los contenedores a consultar respetando proyecto + servicio.
        targets: list[tuple[str, str]] = []
        for container in containers:
            labels = container.get("Labels") or {}
            service_name = labels.get("com.docker.compose.service")
            if service_name not in tracked:
                continue
            if project_filter:
                container_project = labels.get("com.docker.compose.project")
                if container_project != project_filter:
                    continue
            container_id = container.get("Id")
            if not container_id:
                continue
            targets.append((str(service_name), str(container_id)))

        if not targets:
            DockerMetricsService._set_cached_service_memory([])
            return []

        # `?one-shot=true` devuelve al instante: paralelizamos igual porque el
        # handshake + read del socket se beneficia y así acotamos latencia total.
        def _task(item: tuple[str, str]) -> dict | None:
            service_name, container_id = item
            usage = DockerMetricsService._fetch_memory_usage(container_id)
            if usage is None:
                return None
            return {"service_name": service_name, "memory_usage_bytes": usage}

        max_workers = max(1, min(8, len(targets)))
        stats_by_service: list[dict] = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            for result in pool.map(_task, targets):
                if result is not None:
                    stats_by_service.append(result)

        sorted_items = sorted(stats_by_service, key=lambda item: item["service_name"])
        DockerMetricsService._set_cached_service_memory(sorted_items)
        return sorted_items
