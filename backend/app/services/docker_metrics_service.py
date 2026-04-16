"""Consulta métricas de memoria de servicios Docker vía socket Unix."""

from __future__ import annotations

import http.client
import json
import socket
import threading
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
    """Obtiene memoria por servicio del stack Docker actual."""

    _cache_lock = threading.Lock()
    _cached_service_memory: list[dict] = []
    _cache_expires_at: float = 0.0

    @staticmethod
    def _request_json(path: str) -> object:
        settings = get_settings()
        conn = _UnixSocketHTTPConnection(
            settings.docker_socket_path,
            timeout=max(0.05, float(settings.docker_metrics_timeout_seconds)),
        )
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            raw = response.read()
            if response.status >= 400:
                raise RuntimeError(f"Docker API error {response.status}: {raw.decode('utf-8', errors='ignore')}")
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

        try:
            containers = DockerMetricsService._request_json("/containers/json?all=0")
        except (FileNotFoundError, OSError, RuntimeError, json.JSONDecodeError):
            return DockerMetricsService._get_last_cached_service_memory()

        if not isinstance(containers, list):
            return DockerMetricsService._get_last_cached_service_memory()

        stats_by_service: list[dict] = []
        for container in containers:
            labels = container.get("Labels") or {}
            service_name = labels.get("com.docker.compose.service")
            if service_name not in tracked:
                continue

            container_id = container.get("Id")
            if not container_id:
                continue

            try:
                stats = DockerMetricsService._request_json(
                    f"/containers/{quote(str(container_id), safe='')}/stats?stream=false"
                )
            except (OSError, RuntimeError, json.JSONDecodeError):
                continue

            memory_stats = stats.get("memory_stats") if isinstance(stats, dict) else {}
            if not isinstance(memory_stats, dict):
                memory_stats = {}

            stats_by_service.append(
                {
                    "service_name": service_name,
                    "memory_usage_bytes": int(memory_stats.get("usage") or 0),
                }
            )

        sorted_items = sorted(stats_by_service, key=lambda item: item["service_name"])
        DockerMetricsService._set_cached_service_memory(sorted_items)
        return sorted_items
