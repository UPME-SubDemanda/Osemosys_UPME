/**
 * Normaliza errores (Axios, Error, desconocidos) a ApiError.
 * Extrae mensajes del backend (detail, msg) o asigna mensajes genéricos por status.
 */
import axios from "axios";
import { createApiError, isApiError, type ApiError } from "@/shared/errors/ApiError";

/** Mensaje amigable según código HTTP cuando el backend no provee detalle */
function pickMessage(status?: number): string {
  if (!status) return "No se pudo conectar con el servidor.";
  if (status === 401) return "Sesión inválida. Por favor vuelve a ingresar.";
  if (status === 403) return "No tienes permisos para realizar esta acción.";
  if (status === 404) return "Recurso no encontrado.";
  if (status === 409) return "Conflicto al procesar la solicitud.";
  if (status === 413) return "El archivo es demasiado grande para el servidor.";
  if (status === 422) return "Datos inválidos. Revisa el formulario.";
  if (status >= 500) return "Error del servidor. Intenta más tarde.";
  return "Ocurrió un error inesperado.";
}

/** Extrae mensaje de error del body de respuesta (detail, msg, etc.) */
function readBackendDetail(dataObj?: Record<string, unknown>): string | undefined {
  const detail = dataObj?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    const first = detail[0];
    if (typeof first === "string") return first;
    if (typeof first === "object" && first !== null) {
      const msg = (first as Record<string, unknown>).msg;
      if (typeof msg === "string") return msg;
    }
  }
  if (typeof dataObj?.message === "string") {
    return dataObj.message;
  }
  return undefined;
}

/**
 * Normaliza errores a un formato estable para UI y logging.
 * - Evita acoplar el resto de la app a AxiosError.
 */
export function normalizeAxiosError(err: unknown): ApiError {
  if (isApiError(err)) return err;

  if (axios.isAxiosError(err)) {
    const status = err.response?.status;
    const data: unknown = err.response?.data;
    const dataObj = typeof data === "object" && data !== null ? (data as Record<string, unknown>) : undefined;

    const messageFromServer = readBackendDetail(dataObj);

    const base: Omit<ApiError, "name"> = {
      message: messageFromServer ?? pickMessage(status),
      details: {
        url: err.config?.url,
        method: err.config?.method,
        data: err.config?.data,
        response: data,
      },
    };

    if (typeof status === "number") {
      base.status = status;
    }

    const code = dataObj?.code;
    if (typeof code === "string") {
      base.code = code;
    }

    return createApiError(base);
  }

  if (err instanceof Error) {
    return createApiError({ message: err.message, details: { cause: err.cause } });
  }

  return createApiError({ message: "Error desconocido.", details: err });
}

