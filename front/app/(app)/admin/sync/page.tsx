import type { Metadata } from "next";
import { Field, inputClass, SecondaryButton } from "@/components/form";
import {
  Badge,
  Card,
  ErrorNotice,
  Notice,
  PageHeader,
  SectionTitle,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { requireRole } from "@/lib/session";
import type { SyncEstado, SyncUltima, SyncVista } from "@/lib/types";
import { BackToAdmin } from "../back-link";
import { SimularForm, SincronizarForm } from "./sync-forms";

export const metadata: Metadata = { title: "Sincronización con Google Sheets" };

const count = new Intl.NumberFormat("es-AR");

function resultado(ultima: SyncUltima): string {
  if (!ultima.ok) return "Con error";
  return ultima.simulacion ? "Simulación" : "Sincronización";
}

export default async function SyncPage({
  searchParams,
}: {
  searchParams: Promise<{ pestana?: string | string[] }>;
}) {
  await requireRole("admin");
  const params = await searchParams;
  const estado = await apiGet<SyncEstado>("/sync/sheets/estado");

  if (!estado.ok) {
    return (
      <>
        <BackToAdmin />
        <PageHeader eyebrow="Administración" title="Google Sheets" />
        <ErrorNotice message={estado.message} />
      </>
    );
  }

  const { configurado, variables, faltantes, pestanas, en_curso, ultima } =
    estado.data;
  const pedida = Array.isArray(params.pestana)
    ? params.pestana[0]
    : params.pestana;
  const elegida = pedida && pestanas.includes(pedida) ? pedida : pestanas[0];
  const vista = elegida
    ? await apiGet<SyncVista>(
        `/sync/sheets/vista/${encodeURIComponent(elegida)}`,
      )
    : null;

  return (
    <>
      <BackToAdmin />
      <PageHeader
        eyebrow="Administración"
        title="Google Sheets"
        description="Una copia para ver y consultar. La app calcula todo y empuja los datos al Sheet; nada vuelve del Sheet a la app, y lo que se escriba allá se pisa en la próxima sincronización."
      />
      <div className="space-y-12">
        <section>
          <SectionTitle>Conexión</SectionTitle>
          <Card className="space-y-3">
            <p>
              <Badge tone={configurado ? "good" : "warn"}>
                {configurado ? "Configurado" : "Sin configurar"}
              </Badge>
            </p>
            {configurado ? (
              <p className="text-sm text-muted">
                Las dos variables están cargadas en el servicio del backend. Por
                seguridad, acá nunca se muestran sus valores.
              </p>
            ) : (
              <p className="text-sm text-muted">
                Para escribir en Google hay que cargar en el servicio del
                backend (Railway) estas variables de entorno:{" "}
                {variables.map((nombre, indice) => (
                  <span key={nombre}>
                    {indice > 0 ? " y " : ""}
                    <code className="rounded bg-parchment px-1.5 py-0.5 text-xs">
                      {nombre}
                    </code>
                    {faltantes.includes(nombre) ? " (falta)" : " (cargada)"}
                  </span>
                ))}
                . Mientras tanto se puede simular.
              </p>
            )}
          </Card>
        </section>

        <section>
          <SectionTitle>Acciones</SectionTitle>
          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <h3 className="mb-3 text-lg">Simular</h3>
              <SimularForm enCurso={en_curso} />
            </Card>
            <Card>
              <h3 className="mb-3 text-lg">Sincronizar</h3>
              <SincronizarForm
                configurado={configurado}
                faltantes={faltantes}
                enCurso={en_curso}
              />
            </Card>
          </div>
        </section>

        <section>
          <SectionTitle>Última ejecución</SectionTitle>
          {ultima ? (
            <div className="space-y-4">
              {!ultima.ok ? (
                <ErrorNotice
                  title="La última sincronización falló."
                  message={ultima.error ?? "Error desconocido."}
                />
              ) : null}
              <Card className="space-y-2 text-sm">
                <p>
                  <Badge tone={ultima.ok ? "good" : "alert"}>
                    {resultado(ultima)}
                  </Badge>
                </p>
                <p className="text-muted">
                  Empezó el {formatDateTime(ultima.iniciado)} y terminó el{" "}
                  {formatDateTime(ultima.finalizado)} (
                  {count.format(ultima.duracion_ms)} ms).{" "}
                  {ultima.simulacion
                    ? "No se escribió nada en Google."
                    : "Se escribió en el Sheet."}{" "}
                  {count.format(ultima.total_filas)} filas en total.
                </p>
              </Card>
              <TableWrap>
                <table className={tableClass}>
                  <caption className="sr-only">
                    Filas por pestaña en la última ejecución
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col" className={thClass}>
                        Pestaña
                      </th>
                      <th scope="col" className={`${thClass} text-right`}>
                        Filas
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {ultima.pestanas.map((pestana) => (
                      <tr
                        key={pestana.nombre}
                        className="hover:bg-paper-mid/50"
                      >
                        <td className={tdClass}>{pestana.nombre}</td>
                        <td className={`${tdClass} text-right tabular-nums`}>
                          {count.format(pestana.filas)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
              <p className="text-xs text-muted">
                Este resumen vive en la memoria del servicio: se borra si el
                backend se reinicia.
              </p>
            </div>
          ) : (
            <Notice tone="info" title="Todavía no hubo ejecuciones.">
              El resumen se guarda en memoria; aparece después de simular o
              sincronizar y se pierde si el backend se reinicia.
            </Notice>
          )}
        </section>

        <section>
          <SectionTitle>Vista previa</SectionTitle>
          <form method="get" className="mb-5 flex flex-wrap items-end gap-4">
            <Field id="pestana" label="Pestaña">
              <select
                id="pestana"
                name="pestana"
                defaultValue={elegida}
                className={inputClass}
              >
                {pestanas.map((nombre) => (
                  <option key={nombre} value={nombre}>
                    {nombre}
                  </option>
                ))}
              </select>
            </Field>
            <SecondaryButton pending={false}>Ver</SecondaryButton>
          </form>
          {vista === null ? null : vista.ok ? (
            <div className="space-y-3">
              <p className="text-sm text-muted">
                {vista.data.total_filas === 0
                  ? "Esta pestaña no tiene filas todavía."
                  : `Primeras ${count.format(vista.data.mostradas)} de ${count.format(vista.data.total_filas)} filas, tal como las recibiría el Sheet.`}
              </p>
              <TableWrap>
                <table className={tableClass}>
                  <caption className="sr-only">
                    Vista previa de la pestaña {vista.data.pestana}
                  </caption>
                  <thead>
                    <tr>
                      {vista.data.encabezados.map((encabezado) => (
                        <th key={encabezado} scope="col" className={thClass}>
                          {encabezado}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {vista.data.filas.map((fila, indice) => (
                      <tr
                        // Rows have no key of their own and the list is static, so the position is the identity.
                        // biome-ignore lint/suspicious/noArrayIndexKey: static preview
                        key={indice}
                        className="hover:bg-paper-mid/50"
                      >
                        {fila.map((celda, columna) => (
                          <td
                            // biome-ignore lint/suspicious/noArrayIndexKey: static preview
                            key={columna}
                            className={tdClass}
                          >
                            {celda}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            </div>
          ) : (
            <ErrorNotice message={vista.message} />
          )}
        </section>
      </div>
    </>
  );
}
