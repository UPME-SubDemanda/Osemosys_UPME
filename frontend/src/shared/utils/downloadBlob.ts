/**
 * Inicia la descarga de un Blob con nombre de archivo.
 * Retrasa revokeObjectURL: Safari y Firefox a menudo cancelan la descarga si se libera la URL al instante.
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.setTimeout(() => {
    URL.revokeObjectURL(url);
  }, 1500);
}
