from __future__ import annotations

from types import SimpleNamespace

import app.services.docker_metrics_service as docker_metrics_module
from app.services.docker_metrics_service import DockerMetricsService


def _reset_metrics_cache() -> None:
    DockerMetricsService._cached_service_memory = []
    DockerMetricsService._cache_expires_at = 0.0
    DockerMetricsService._detected_project = None


def _make_settings(*, project: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        docker_socket_path="/var/run/docker.sock",
        docker_metrics_timeout_seconds=0.1,
        docker_metrics_cache_ttl_seconds=60.0,
        docker_metrics_services_list=lambda: ["api"],
        docker_metrics_project=project,
    )


def test_list_service_memory_uses_cache(monkeypatch) -> None:
    _reset_metrics_cache()
    calls: list[str] = []

    monkeypatch.setattr(
        docker_metrics_module,
        "get_settings",
        lambda: _make_settings(project="osemosys"),
    )

    def _request_json(path: str, *, timeout: float | None = None):
        calls.append(path)
        if path == "/containers/json?all=0":
            return [
                {
                    "Id": "cid-1",
                    "Labels": {
                        "com.docker.compose.service": "api",
                        "com.docker.compose.project": "osemosys",
                    },
                }
            ]
        if path == "/containers/cid-1/stats?stream=false&one-shot=true":
            return {"memory_stats": {"usage": 123}}
        raise AssertionError(path)

    monkeypatch.setattr(DockerMetricsService, "_request_json", staticmethod(_request_json))

    first = DockerMetricsService.list_service_memory()
    second = DockerMetricsService.list_service_memory()

    assert first == [{"service_name": "api", "memory_usage_bytes": 123}]
    assert second == first
    assert calls == [
        "/containers/json?all=0",
        "/containers/cid-1/stats?stream=false&one-shot=true",
    ]


def test_list_service_memory_returns_stale_cache_on_error(monkeypatch) -> None:
    _reset_metrics_cache()

    monkeypatch.setattr(
        docker_metrics_module,
        "get_settings",
        lambda: _make_settings(project="osemosys"),
    )
    DockerMetricsService._set_cached_service_memory(
        [{"service_name": "api", "memory_usage_bytes": 456}]
    )
    DockerMetricsService._cache_expires_at = 0.0
    monkeypatch.setattr(
        DockerMetricsService,
        "_request_json",
        staticmethod(lambda _path, **_kw: (_ for _ in ()).throw(OSError("docker slow"))),
    )

    result = DockerMetricsService.list_service_memory()

    assert result == [{"service_name": "api", "memory_usage_bytes": 456}]


def test_list_service_memory_filters_by_compose_project(monkeypatch) -> None:
    """Contenedores de otros proyectos Compose no deben sumarse al total."""
    _reset_metrics_cache()

    monkeypatch.setattr(
        docker_metrics_module,
        "get_settings",
        lambda: _make_settings(project="osemosys"),
    )

    def _request_json(path: str, *, timeout: float | None = None):
        if path == "/containers/json?all=0":
            return [
                {
                    "Id": "ours",
                    "Labels": {
                        "com.docker.compose.service": "api",
                        "com.docker.compose.project": "osemosys",
                    },
                },
                {
                    "Id": "theirs",
                    "Labels": {
                        "com.docker.compose.service": "api",
                        "com.docker.compose.project": "other-stack",
                    },
                },
            ]
        if path == "/containers/ours/stats?stream=false&one-shot=true":
            return {"memory_stats": {"usage": 10}}
        if path == "/containers/theirs/stats?stream=false&one-shot=true":
            return {"memory_stats": {"usage": 99999}}
        raise AssertionError(path)

    monkeypatch.setattr(DockerMetricsService, "_request_json", staticmethod(_request_json))

    result = DockerMetricsService.list_service_memory()

    assert result == [{"service_name": "api", "memory_usage_bytes": 10}]
