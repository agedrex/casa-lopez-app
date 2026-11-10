// Product notes imported from the Excel are one text of items separated by " | ":
//   IMPORTADO-EXCEL fila 22 | REVISAR: sin nombre | B=Fabián | E=2026-08-25 | Comentario AE53: ...
// This only splits it for display; the stored note is never modified.

const SEPARATOR = " | ";
const REVISAR = "REVISAR:";

export type NotaItem = {
  /** For a `REVISAR:` mark, only the reason (the prefix is shown by the screen). */
  text: string;
  revisar: boolean;
};

/** Items of a note, in order. Empty or missing notes and empty items give nothing. */
export function parseNota(nota: string | null | undefined): NotaItem[] {
  const items: NotaItem[] = [];
  for (const raw of (nota ?? "").split(SEPARATOR)) {
    const item = raw.trim();
    if (item === "") continue;
    if (item.startsWith(REVISAR)) {
      const reason = item.slice(REVISAR.length).trim();
      // A mark without a reason is kept as plain text so nothing of the note disappears.
      items.push(
        reason === ""
          ? { text: item, revisar: false }
          : { text: reason, revisar: true },
      );
    } else {
      items.push({ text: item, revisar: false });
    }
  }
  return items;
}
