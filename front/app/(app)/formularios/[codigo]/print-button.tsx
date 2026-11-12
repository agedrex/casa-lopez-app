"use client";

/** "Imprimir" is the PDF: the browser print dialog with the print styles of the sheet (Save as PDF). */
export function PrintButton() {
  return (
    <button
      type="button"
      onClick={() => window.print()}
      className="min-h-12 w-full rounded-card border border-line px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-parchment sm:min-h-0 sm:w-auto print:hidden"
    >
      Imprimir
    </button>
  );
}
