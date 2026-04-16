/**
 * canvg publica tipos en lib/index.d.ts pero package.json "exports" no los enlaza para el
 * resolvedor de TS al importar "canvg" (ESM). Declaración mínima para Highcharts offline PNG.
 */
declare module "canvg" {
  export default class Canvg {
    static fromString(
      ctx: CanvasRenderingContext2D,
      svg: string,
      options?: unknown,
    ): Canvg;
    start(options?: unknown): void;
    stop(): void;
    render(options?: unknown): Promise<void>;
  }
}
