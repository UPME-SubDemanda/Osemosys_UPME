/**
 * Interacción de leyenda estilo Plotly (declarativo):
 * - 1 click  → toggle inmediato de esa serie.
 * - 2 clicks rápidos (misma serie, <300ms):
 *     - si esa serie NO está aislada → aislarla (ocultar las demás).
 *     - si esa serie YA está aislada → restaurar todas las series.
 *
 * El estado de visibilidad (`hiddenNames` + `isolatedName`) vive en React.
 * Los handlers sólo despachan callbacks; cada componente re-renderiza con
 * `options.series[i].visible` calculado desde ese state. Así se evita el
 * race con `HighchartsReact.chart.update()` cuando la prop `options` cambia.
 */

const DOUBLE_CLICK_MS = 300;

export type LegendDblclickState = {
  lastTime: number;
  lastName: string | null;
  isolatedName: string | null;
};

export function createLegendDblclickState(): LegendDblclickState {
  return { lastTime: 0, lastName: null, isolatedName: null };
}

function isDoubleClick(state: LegendDblclickState, name: string, now: number): boolean {
  return state.lastName === name && now - state.lastTime < DOUBLE_CLICK_MS;
}

function clearDblclickTracking(state: LegendDblclickState) {
  state.lastTime = 0;
  state.lastName = null;
}

/**
 * Dispatcher único. Decide entre toggle / isolate / restoreAll y llama al callback
 * correspondiente. También actualiza el `isolatedName` interno del state para que
 * el próximo dblclick sepa si tiene que restaurar o aislar.
 */
export function dispatchLegendClick(
  state: LegendDblclickState,
  name: string,
  callbacks: {
    onToggle: (name: string) => void;
    onIsolate: (name: string) => void;
    onRestoreAll: () => void;
  },
) {
  const now = Date.now();

  if (isDoubleClick(state, name, now)) {
    clearDblclickTracking(state);
    if (state.isolatedName === name) {
      state.isolatedName = null;
      callbacks.onRestoreAll();
    } else {
      state.isolatedName = name;
      callbacks.onIsolate(name);
    }
    return;
  }

  state.lastTime = now;
  state.lastName = name;
  state.isolatedName = null;
  callbacks.onToggle(name);
}
