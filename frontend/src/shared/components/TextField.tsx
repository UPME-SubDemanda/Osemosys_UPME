/**
 * Campo de texto con etiqueta, icono opcional y mensaje de error.
 * Usado en formularios de login, búsqueda y edición de datos.
 */
import type { InputHTMLAttributes } from "react";
import type { ReactNode } from "react";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  /** Etiqueta visible del campo */
  label: string;
  /** Mensaje de error a mostrar debajo del input */
  error?: string;
  /** Icono opcional a la izquierda del input */
  startIcon?: ReactNode;
};

export function TextField({ label, error, style, startIcon, ...props }: Props) {
  return (
    <label className="field">
      <span className="field__label">{label}</span>
      <div className="field__control">
        {startIcon ? <span className="field__icon" aria-hidden="true">{startIcon}</span> : null}
        <input
          {...props}
          className={[
            "field__input",
            startIcon ? "field__input--with-icon" : undefined,
            error ? "field__input--error" : undefined,
          ]
            .filter(Boolean)
            .join(" ")}
          style={style}
        />
      </div>
      {error ? <span className="field__error">{error}</span> : null}
    </label>
  );
}

