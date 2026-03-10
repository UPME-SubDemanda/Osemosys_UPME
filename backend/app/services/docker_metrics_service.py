"""Consulta métricas de memoria de servicios Docker vía socket Unix."""

from __future__ import annotations

import http.client
import json
import socket
from urllib.parse import quote

from app.core.config import get_settings


class _UnixSocketHTTPConnection(http.client.HTTPConnection):
    """Conexión HTTP mínima contra el socket Unix del daemon Docker."""

    def __init__(self, socket_path: str) -> None:
        super().__init__("localhost")
        self.socket_path = socket_path

    def connect(self) -> None:  # pragma: no cover
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.socket_path)


class DockerMetricsService:
    """Obtiene memoria por servicio del stack Docker actual."""

    @staticmethod
    def _request_json(path: str) -> object:
        settings = get_settings()
        conn = _UnixSocketHTTPConnection(settings.docker_socket_path)
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

    @staticmethod
    def list_service_memory() -> list[dict]:
        """Retorna uso de memoria por servicio compose rastreado."""
        settings = get_settings()
        tracked = set(settings.docker_metrics_services_list())
        if not tracked:
            return []

        try:
            containers = DockerMetricsService._request_json("/containers/json?all=0")
        except (FileNotFoundError, OSError, RuntimeError, json.JSONDecodeError):
            return []

        if not isinstance(containers, list):
            return []

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

        return sorted(stats_by_service, key=lambda item: item["service_name"])
