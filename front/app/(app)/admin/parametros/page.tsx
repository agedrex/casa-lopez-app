import type { Metadata } from "next";
import { Badge, Card, ErrorNotice, Notice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import {
  displayValue,
  isEditable,
  splitStatus,
  unitLabel,
} from "@/lib/parametros";
import { requireRole } from "@/lib/session";
import type { Parametro } from "@/lib/types";
import { BackToAdmin } from "../back-link";
import { ParametroForm } from "./parametro-form";

export const metadata: Metadata = { title: "Parámetros" };

export default async function ParametrosPage() {
  await requireRole("admin");
  const result = await apiGet<Parametro[]>("/parametros");

  return (
    <>
      <BackToAdmin />
      <PageHeader
        eyebrow="Administración"
        title="Parámetros"
        description="Los valores que el sistema lee al calcular. Cambiar uno afecta a la próxima cotización; las ya guardadas quedan como estaban."
      />
      <div className="mb-8">
        <Notice title="No hay historial de cambios">
          La base no guarda el valor anterior de un parámetro. Antes de
          confirmar, anote el valor actual si quiere poder volver a él.
          SUPUESTO: validar si Casa López necesita ese historial (haría falta
          una tabla nueva).
        </Notice>
      </div>
      {result.ok ? (
        <ul className="space-y-6">
          {result.data.map((parametro) => {
            const editable = isEditable(parametro);
            const status = splitStatus(parametro.fuente_estado);
            return (
              <li key={parametro.codigo}>
                <Card>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-xl">{parametro.constante}</h2>
                      <p className="text-xs text-muted">{parametro.codigo}</p>
                    </div>
                    <Badge
                      tone={status.state === "Confirmado" ? "good" : "warn"}
                      title={parametro.fuente_estado ?? undefined}
                    >
                      {status.state || "Sin marca"}
                    </Badge>
                  </div>
                  <dl className="mt-4 grid gap-x-8 gap-y-3 text-sm sm:grid-cols-3">
                    <div>
                      <dt className="text-xs uppercase tracking-caps-sm text-muted">
                        Valor actual
                      </dt>
                      <dd className="mt-0.5 font-display text-2xl tabular-nums">
                        {displayValue(parametro)}
                      </dd>
                      <dd className="text-xs text-muted">
                        {unitLabel(parametro.unidad)}
                      </dd>
                    </div>
                    <div className="sm:col-span-2">
                      <dt className="text-xs uppercase tracking-caps-sm text-muted">
                        Qué es
                      </dt>
                      <dd className="mt-0.5">{parametro.que_es ?? "—"}</dd>
                      <dd className="mt-1 text-xs text-muted">
                        Fuente / estado: {parametro.fuente_estado ?? "—"}
                      </dd>
                    </div>
                  </dl>
                  {editable ? (
                    <details className="mt-5">
                      <summary className="cursor-pointer text-sm underline decoration-gold underline-offset-4">
                        Cambiar este parámetro
                        <span className="sr-only">
                          {" "}
                          ({parametro.constante})
                        </span>
                      </summary>
                      <div className="mt-4">
                        <ParametroForm
                          parametro={parametro}
                          currentLabel={
                            parametro.valor_texto ?? parametro.valor ?? ""
                          }
                        />
                      </div>
                    </details>
                  ) : (
                    <p className="mt-5 text-sm text-muted">
                      Calculado por el sistema: no se edita.
                    </p>
                  )}
                </Card>
              </li>
            );
          })}
        </ul>
      ) : (
        <ErrorNotice message={result.message} />
      )}
    </>
  );
}
