/**
 * Componente Button reutilizable con variantes de estilo.
 * Soporta variantes "primary" (principal) y "ghost" (secundario/transparente).
 * Extiende los atributos nativos de HTML button para máxima flexibilidad.
 */
import type { ButtonHTMLAttributes, CSSProperties } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  /** Variante visual: primary (destacado) o ghost (discreto) */
  variant?: "primary" | "ghost";
};

export function Button({ variant = "primary", style, ...props }: Props) {
  const className = ["btn", variant === "primary" ? "btn--primary" : "btn--ghost", props.className]
    .filter(Boolean)
    .join(" ");

  const base: CSSProperties = {
    ...style,
  };

  return <button {...props} className={className} style={base} />;
}

