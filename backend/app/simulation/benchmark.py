from __future__ import annotations


def relative_error(reference: float, actual: float) -> float:
    """Calcula error relativo robusto para referencia cero/no-cero."""
    if reference == 0.0:
        return abs(actual - reference)
    return abs(actual - reference) / abs(reference)


def compare_with_tolerance(
    *,
    reference: dict[str, float],
    actual: dict[str, float],
    tolerance: float = 1e-4,
) -> tuple[bool, dict[str, float]]:
    """Compara métricas contra referencia con tolerancia configurable."""
    errors: dict[str, float] = {}
    for key, ref_value in reference.items():
        act_value = float(actual.get(key, 0.0))
        errors[key] = relative_error(float(ref_value), act_value)
    is_ok = all(error <= tolerance for error in errors.values())
    return is_ok, errors


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Funciones utilitarias para validación de paridad numérica.
#
# Posibles mejoras:
# - Soportar tolerancias por métrica (no única global).
#
# Riesgos en producción:
# - Tolerancia inadecuada puede ocultar regresiones o disparar falsos positivos.
#
# Escalabilidad:
# - CPU-bound mínimo.
