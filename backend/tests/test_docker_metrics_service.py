from __future__ import annotations

from types import SimpleNamespace

import app.services.docker_metrics_service as docker_metrics_module
from app.services.docker_metrics_service import DockerMetricsService


def _reset_metrics_cache() -> None:
    DockerMetricsService._cached_service_memory = []
    DockerMetricsService._cache_expires_at = 0.0


def test_list_service_memory_uses_cache(monkeypatch) -> None:
    _reset_metrics_cache()
    calls: list[str] = []

    monkeypatch.setattr(
        docker_metrics_module,
        "get_settings",
        lambda: SimpleNamespace(
            docker_socket_path="/var/run/docker.sock",
            docker_metrics_timeout_seconds=0.1,
            docker_metrics_cache_ttl_seconds=60.0,
            docker_metrics_services_list=lambda: ["api"],
        ),
    )

    def _request_json(path: str):
        calls.append(path)
        if path == "/containers/json?all=0":
            return [
                {
                    "Id": "cid-1",
                    "Labels": {"com.docker.compose.service": "api"},
                }
            ]
        if path == "/containers/cid-1/stats?stream=false":
            return {"memory_stats": {"usage": 123}}
        raise AssertionError(path)

    monkeypatch.setattr(DockerMetricsService, "_request_json", staticmethod(_request_json))

    first = DockerMetricsService.list_service_memory()
    second = DockerMetricsService.list_service_memory()

    assert first == [{"service_name": "api", "memory_usage_bytes": 123}]
    assert second == first
    assert calls == ["/containers/json?all=0", "/containers/cid-1/stats?stream=false"]


def test_list_service_memory_returns_stale_cache_on_error(monkeypatch) -> None:
    _reset_metrics_cache()

    monkeypatch.setattr(
        docker_metrics_module,
        "get_settings",
        lambda: SimpleNamespace(
            docker_socket_path="/var/run/docker.sock",
            docker_metrics_timeout_seconds=0.1,
            docker_metrics_cache_ttl_seconds=60.0,
            docker_metrics_services_list=lambda: ["api"],
        ),
    )
    DockerMetricsService._set_cached_service_memory(
        [{"service_name": "api", "memory_usage_bytes": 456}]
    )
    DockerMetricsService._cache_expires_at = 0.0
    monkeypatch.setattr(
        DockerMetricsService,
        "_request_json",
        staticmethod(lambda _path: (_ for _ in ()).throw(OSError("docker slow"))),
    )

    result = DockerMetricsService.list_service_memory()

    assert result == [{"service_name": "api", "memory_usage_bytes": 456}]
