/**
 * Iconos SVG (stroke-only) para las acciones de tarjeta dentro de los editores
 * de reporte: Visualizar (👁), Reemplazar (swap) y Título (pencil).
 * Heredan `currentColor` del botón contenedor.
 */

type IconProps = { size?: number; className?: string };

const common = {
  fill: "none" as const,
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function IconEye({ size = 14, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={className}
      {...common}
    >
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

export function IconSwap({ size = 14, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={className}
      {...common}
    >
      <path d="M7 7h13" />
      <path d="M16 3l4 4-4 4" />
      <path d="M17 17H4" />
      <path d="M8 21l-4-4 4-4" />
    </svg>
  );
}

export function IconPencil({ size = 14, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={className}
      {...common}
    >
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
    </svg>
  );
}
