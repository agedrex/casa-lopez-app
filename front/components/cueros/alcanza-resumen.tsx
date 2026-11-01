import Link from "next/link";
import { Notice } from "@/components/ui";
import { grupoTitulo } from "@/lib/cueros";
import { formatQuantity } from "@/lib/format";
import type { AlcanzaCuero } from "@/lib/types";
import { EstadoBadge } from "./estado-badge";
import { Metric } from "./grupo-card";

/** Answer of "¿Me alcanza?": everything comes calculated by the API. */
export function AlcanzaResumen({
  resultado,
  nombres,
}: {
  resultado: AlcanzaCuero;
  nombres: Record<string, string>;
}) {
  return (
    <div className="space-y-4">
      {resultado.alcanza ? (
        <Notice tone="info" title="Sí, alcanza.">
          Hay cuero suficiente para {formatQuantity(resultado.cantidad)} de{" "}
          {resultado.producto}.
        </Notice>
      ) : (
        <Notice title="No alcanza.">
          {resultado.faltante
            ? `Faltan ${formatQuantity(resultado.faltante)} m².`
            : (resultado.mensaje ?? "No se pudo calcular cuánto falta.")}
        </Notice>
      )}
      <dl className="grid grid-cols-2 gap-3">
        <Metric label="Necesario">
          {resultado.necesario
            ? `${formatQuantity(resultado.necesario)} m²`
            : "—"}
        </Metric>
        <Metric label="Disponible">
          {formatQuantity(resultado.disponible)} m²
        </Metric>
      </dl>
      {resultado.mensaje && resultado.alcanza ? (
        <p className="text-sm text-muted">{resultado.mensaje}</p>
      ) : null}
      {resultado.piezas.length > 0 ? (
        <div className="space-y-2">
          <h3 className="text-base font-bold">Pieles sugeridas</h3>
          {resultado.piezas.map((pieza) => (
            <Link
              key={pieza.codigo}
              href={`/cueros/${encodeURIComponent(pieza.codigo)}`}
              className="flex min-h-12 flex-wrap items-center justify-between gap-2 rounded-card border border-line px-4 py-2 hover:border-gold"
            >
              <span className="flex items-center gap-2">
                <span className="font-bold">{pieza.codigo}</span>
                <EstadoBadge estado={pieza.estado} />
              </span>
              <span className="text-base tabular-nums">
                {formatQuantity(pieza.disponible)} m²
              </span>
            </Link>
          ))}
        </div>
      ) : null}
      {resultado.alternativas.length > 0 ? (
        <div className="space-y-2">
          <h3 className="text-base font-bold">Otros cueros con material</h3>
          <ul className="space-y-1 text-base">
            {resultado.alternativas.map((alternativa) => (
              <li key={`${alternativa.material}|${alternativa.color ?? ""}`}>
                {grupoTitulo(
                  nombres[alternativa.material] ?? alternativa.material,
                  alternativa.color,
                )}
                : {formatQuantity(alternativa.disponible)} m²
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
