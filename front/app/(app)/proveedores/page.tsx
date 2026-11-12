import type { Metadata } from "next";
import Link from "next/link";
import { buttonClass, labelClass } from "@/components/cueros/estilos";
import { inputClass } from "@/components/form";
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
import { requireRole } from "@/lib/session";
import type { Proveedor } from "@/lib/types";
import { createProveedor } from "./actions";
import { ProveedorForm } from "./proveedor-form";

export const metadata: Metadata = { title: "Proveedores" };

type Params = Record<string, string | string[] | undefined>;

const first = (value: string | string[] | undefined) =>
  (Array.isArray(value) ? value[0] : value) ?? "";

const ESTADOS = [
  { value: "", label: "Todos" },
  { value: "true", label: "Activos" },
  { value: "false", label: "Inactivos" },
];

export default async function ProveedoresPage({
  searchParams,
}: {
  searchParams: Promise<Params>;
}) {
  await requireRole("admin");
  const params = await searchParams;
  const q = first(params.q).trim();
  const activo = ["true", "false"].includes(first(params.activo))
    ? first(params.activo)
    : "";

  const query = new URLSearchParams();
  if (q) query.set("q", q);
  if (activo) query.set("activo", activo);
  const result = await apiGet<Proveedor[]>(
    `/proveedores${query.size > 0 ? `?${query}` : ""}`,
  );
  const filtered = Boolean(q || activo);

  return (
    <>
      <PageHeader
        eyebrow="Datos de base"
        title="Proveedores"
        description="Agenda de proveedores con sus facturas e imágenes. Un proveedor desactivado se oculta de las listas pero conserva sus archivos."
      />
      <div className="space-y-10">
        <section aria-label="Buscar proveedores">
          <form method="get" className="grid gap-4 sm:grid-cols-[2fr_1fr_auto]">
            <div>
              <label htmlFor="filtro-q" className={labelClass}>
                Buscar por nombre, código o CUIT
              </label>
              <input
                id="filtro-q"
                name="q"
                type="search"
                defaultValue={q}
                autoComplete="off"
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="filtro-activo" className={labelClass}>
                Estado
              </label>
              <select
                id="filtro-activo"
                name="activo"
                defaultValue={activo}
                className={inputClass}
              >
                {ESTADOS.map((estado) => (
                  <option key={estado.value} value={estado.value}>
                    {estado.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-end">
              <button type="submit" className={buttonClass}>
                Buscar
              </button>
            </div>
          </form>
        </section>

        <section>
          {result.ok ? (
            result.data.length === 0 ? (
              <Notice
                tone="info"
                title={
                  filtered
                    ? "No hay proveedores con ese filtro."
                    : "Todavía no hay proveedores cargados."
                }
              />
            ) : (
              <TableWrap>
                <table className={tableClass}>
                  <thead>
                    <tr>
                      <th className={thClass}>Proveedor</th>
                      <th className={thClass}>CUIT</th>
                      <th className={thClass}>Contacto</th>
                      <th className={thClass}>Teléfono</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.data.map((proveedor) => (
                      <tr
                        key={proveedor.codigo}
                        className="hover:bg-paper-mid/50"
                      >
                        <td className={tdClass}>
                          <Link
                            href={`/proveedores/${encodeURIComponent(proveedor.codigo)}`}
                            className="underline decoration-gold underline-offset-4"
                          >
                            {proveedor.nombre}
                          </Link>
                          <span className="block text-xs text-muted">
                            {proveedor.codigo}
                          </span>{" "}
                          {proveedor.activo ? null : (
                            <Badge tone="neutral">Inactivo</Badge>
                          )}
                        </td>
                        <td className={tdClass}>{proveedor.cuit ?? "—"}</td>
                        <td className={tdClass}>{proveedor.contacto ?? "—"}</td>
                        <td className={tdClass}>{proveedor.telefono ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            )
          ) : (
            <ErrorNotice message={result.message} />
          )}
        </section>

        <section>
          <SectionTitle>Nuevo proveedor</SectionTitle>
          <Card>
            <ProveedorForm
              action={createProveedor}
              submitLabel="Crear proveedor"
              pendingLabel="Creando…"
            />
          </Card>
        </section>
      </div>
    </>
  );
}
