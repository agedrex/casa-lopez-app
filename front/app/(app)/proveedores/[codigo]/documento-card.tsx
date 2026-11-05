import { Badge } from "@/components/ui";
import { formatDate, formatDateTime, formatMoney } from "@/lib/format";
import {
  canRetryOcr,
  documentFileUrl,
  documentTypeLabel,
  formatFileSize,
  isImageMime,
  ocrLabel,
  ocrTone,
} from "@/lib/proveedores";
import type { DocumentoProveedor } from "@/lib/types";
import { ConfirmarDatosForm } from "./confirmar-datos-form";
import { ReintentarOcrForm } from "./reintentar-ocr-form";

const PDF_ICON = "M7 3h7l5 5v13H7zM14 3v5h5M9.5 14h5M9.5 17.5h5";

function Thumbnail({ documento }: { documento: DocumentoProveedor }) {
  const url = documentFileUrl(documento.id);
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener"
      aria-label={`Abrir ${documento.nombre_archivo}`}
      className="flex size-28 shrink-0 items-center justify-center overflow-hidden rounded-card border border-line bg-paper-mid"
    >
      {isImageMime(documento.mime) ? (
        // biome-ignore lint/performance/noImgElement: the file comes from an authenticated same-origin route, not from a static asset that next/image could optimize.
        <img
          src={url}
          alt={documento.nombre_archivo}
          loading="lazy"
          className="size-full object-cover"
        />
      ) : (
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          className="size-12 text-muted"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d={PDF_ICON} />
        </svg>
      )}
    </a>
  );
}

function Datum({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-caps-sm text-muted">{label}</dt>
      <dd className="mt-0.5 break-words">{value}</dd>
    </div>
  );
}

export function DocumentoCard({
  documento,
  writer,
}: {
  documento: DocumentoProveedor;
  writer: boolean;
}) {
  const sugerencia = documento.ocr_sugerencia;
  const hasSuggestion =
    sugerencia !== null &&
    Boolean(
      sugerencia.numero ||
        sugerencia.fecha ||
        sugerencia.total ||
        sugerencia.moneda,
    );
  const total =
    documento.total && documento.moneda
      ? formatMoney(documento.total, documento.moneda)
      : "—";

  return (
    <li className="space-y-4 rounded-card border border-line bg-surface p-4 shadow-card sm:p-6">
      <div className="flex gap-4">
        <Thumbnail documento={documento} />
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{documentTypeLabel(documento.tipo)}</Badge>
            <Badge
              tone={ocrTone(documento.ocr_estado)}
              title={documento.ocr_error ?? undefined}
            >
              OCR: {ocrLabel(documento.ocr_estado)}
            </Badge>
          </div>
          <p className="break-words font-bold">{documento.nombre_archivo}</p>
          <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-3">
            <Datum label="Número" value={documento.numero ?? "—"} />
            <Datum
              label="Fecha"
              value={formatDate(documento.fecha_documento)}
            />
            <Datum label="Total" value={total} />
          </dl>
          <p className="text-xs text-muted">
            {formatFileSize(documento.tamano_bytes)} · subido el{" "}
            {formatDateTime(documento.created_at)}
          </p>
          <p className="text-sm">
            <a
              href={documentFileUrl(documento.id)}
              target="_blank"
              rel="noopener"
              className="underline decoration-gold underline-offset-4"
            >
              Abrir archivo
            </a>
          </p>
        </div>
      </div>

      {documento.ocr_estado === "ERROR" ? (
        <p className="rounded-card border border-blush-deep bg-blush/30 px-4 py-3 text-sm">
          No se pudo leer el texto de este archivo
          {documento.ocr_error ? `: ${documento.ocr_error}` : "."} El archivo
          está guardado y puede volver a intentarlo.
        </p>
      ) : null}
      {documento.ocr_estado === "NO_CONFIGURADO" ? (
        <p className="rounded-card border border-line bg-paper-mid px-4 py-3 text-sm text-muted">
          La lectura automática todavía no está activada. El archivo está
          guardado; cuando se active podrá pedir la lectura.
        </p>
      ) : null}
      {documento.ocr_estado === "PENDIENTE" ? (
        <p className="rounded-card border border-line bg-paper-mid px-4 py-3 text-sm text-muted">
          El texto de este archivo todavía no se leyó.
        </p>
      ) : null}

      {documento.ocr_texto ? (
        <details className="rounded-card border border-line">
          <summary className="min-h-12 cursor-pointer px-4 py-3 text-sm">
            Ver el texto leído del archivo
          </summary>
          {/* Plain text on purpose: the OCR output is untrusted and React escapes it. */}
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words border-t border-line px-4 py-3 text-sm">
            {documento.ocr_texto}
          </pre>
        </details>
      ) : null}

      {hasSuggestion ? (
        <p className="rounded-card border border-line bg-paper-mid px-4 py-3 text-sm">
          <span className="font-bold">Lo que parece decir el documento:</span>{" "}
          número {sugerencia?.numero ?? "—"}, fecha{" "}
          {formatDate(sugerencia?.fecha)}, total{" "}
          {sugerencia?.total
            ? sugerencia.moneda
              ? formatMoney(sugerencia.total, sugerencia.moneda)
              : sugerencia.total
            : "—"}
          .{" "}
          <span className="text-muted">
            Es solo una sugerencia: revísela contra el documento antes de
            confirmar.
          </span>
        </p>
      ) : null}

      {writer ? (
        <div className="space-y-4 border-t border-line pt-4">
          {/* Remount when the saved data changes so the fields show the new values. */}
          <ConfirmarDatosForm
            key={[
              documento.id,
              documento.tipo,
              documento.numero,
              documento.fecha_documento,
              documento.total,
              documento.moneda,
            ].join("|")}
            documento={documento}
          />
          {canRetryOcr(documento.ocr_estado) ? (
            <ReintentarOcrForm id={documento.id} />
          ) : null}
        </div>
      ) : null}
    </li>
  );
}
