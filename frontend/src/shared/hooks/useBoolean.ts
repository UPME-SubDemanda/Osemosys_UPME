/**
 * Hook para manejar estado booleano con helpers on, off, toggle.
 * Útil para modales, acordeones, switches, etc.
 */
import { useCallback, useMemo, useState } from "react";

export function useBoolean(initial = false) {
  const [value, setValue] = useState<boolean>(initial);

  const on = useCallback(() => setValue(true), []);
  const off = useCallback(() => setValue(false), []);
  const toggle = useCallback(() => setValue((v) => !v), []);

  return useMemo(
    () => ({ value, set: setValue, on, off, toggle }),
    [off, on, toggle, value],
  );
}

