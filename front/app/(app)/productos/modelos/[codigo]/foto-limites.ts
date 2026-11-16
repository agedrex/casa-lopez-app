// Client-side hint only: the API checks the real size and the file's magic bytes (JPEG, PNG or WebP, 5 MB at most).
export const MAX_FOTO_BYTES = 5 * 1024 * 1024;
export const FOTO_MIME = ["image/jpeg", "image/png", "image/webp"] as const;
export const FOTO_ACCEPT = FOTO_MIME.join(",");

/** Why a photo is refused before sending it, or null. The API still has the last word. */
export function fotoHint(file: { size: number; type: string }): string | null {
  if (file.size === 0) return "el archivo está vacío";
  if (file.size > MAX_FOTO_BYTES) return "supera los 5 MB";
  if (file.type && !(FOTO_MIME as readonly string[]).includes(file.type)) {
    return "solo se aceptan fotos JPG, PNG o WebP";
  }
  return null;
}
