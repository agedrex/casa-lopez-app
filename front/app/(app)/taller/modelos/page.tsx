import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import {
  Badge,
  CardItem,
  CardList,
  ErrorNotice,
  Notice,
  PageHeader,
  ResponsiveTable,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDate } from "@/lib/format";
import {
  ESTADO_TONE,
  ESTADOS_FILTRO,
  estadoLabel,
  isEstado,
} from "@/lib/formularios";
import { canFillFormularios, hasRole } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { FormularioResumen } from "@/lib/types";
import { LotesYModelos } from "../../fabricacion/lotes-y-modelos";

export const metadata: Metadata = { title: "Modelos del taller" };

type Search = Promise<{ estado?: string | string[] }>;

export default async function ModelosDelTallerPage({
  searchParams,
}: {
  searchParams: Search;
}) {
  const { user } = await requireSession();
  if (!canFillFormularios(user.role)) redirect("/");
  const esAdmin = hasRole(user.role, "admin");
  // The taller has one screen with two tabs, Lotes and Modelos (this route is the Modelos tab).
  if (!esAdmin) return <LotesYModelos vista="modelos" />;

  // The admin reviews: it opens on what is waiting for it (COMPLETADO); `?estado=todas` shows every state.
  const { estado: pedido } = await searchParams;
  const pedida = (Array.isArray(pedido) ? pedido[0] : pedido)?.trim() ?? "";
  const filtro =
    pedida === "todas" ? null : isEstado(pedida) ? pedida : "COMPLETADO";
  const result = await apiGet<FormularioResumen[]>(
    `/formularios${filtro ? `?estado=${filtro}` : ""}`,
  );

  return (
    <>
      <PageHeader
        eyebrow="Producción"
        title="Hojas de consumos"
        description="Las hojas que carga el taller con las medidas reales. Abrí una completada para validarla (las medidas pasan al modelo) o devolverla con un comentario."
      />
      <Filtros actual={filtro} />
      {result.ok ? (
        result.data.length === 0 ? (
          <Notice
            tone="info"
            title={
              filtro === "COMPLETADO"
                ? "No hay hojas esperando revisión."
                : "Todavía no hay hojas."
            }
          >
            Cuando el taller complete una hoja aparece acá.
          </Notice>
        ) : (
          <Lista hojas={result.data} />
        )
      ) : (
        <ErrorNotice message={result.message} />
      )}
    </>
  );
}

function Filtros({ actual }: { actual: string | null }) {
  const opciones = [
    ...ESTADOS_FILTRO.map((code) => ({
      href: `?estado=${code}`,
      label: estadoLabel(code),
      activa: actual === code,
    })),
    { href: "?estado=todas", label: "Todas", activa: actual === null },
  ];
  return (
    <nav aria-label="Estado de la hoja" className="mb-6 flex flex-wrap gap-2">
      {opciones.map((opcion) => (
        <Link
          key={opcion.href}
          href={opcion.href}
          aria-current={opcion.activa ? "page" : undefined}
          className={`inline-flex min-h-11 items-center rounded-full border px-4 text-sm sm:min-h-0 sm:py-1.5 ${
            opcion.activa
              ? "border-ink bg-ink text-white"
              : "border-line text-ink-soft hover:bg-parchment"
          }`}
        >
          {opcion.label}
        </Link>
      ))}
    </nav>
  );
}

function EstadoBadge({ hoja }: { hoja: FormularioResumen }) {
  return (
    <Badge tone={ESTADO_TONE[hoja.estado]}>{estadoLabel(hoja.estado)}</Badge>
  );
}

function Lista({ hojas }: { hojas: FormularioResumen[] }) {
  const href = (hoja: FormularioResumen) =>
    `/taller/modelos/${encodeURIComponent(hoja.codigo)}`;
  return (
    <ResponsiveTable
      cards={
        <CardList>
          {hojas.map((hoja) => (
            <CardItem key={hoja.codigo}>
              <Link href={href(hoja)} className="block min-h-11">
                <p className="text-xs uppercase tracking-caps-sm text-muted">
                  {hoja.modelo ?? hoja.codigo}
                </p>
                <p className="mt-0.5 text-base">{hoja.articulo}</p>
                <p className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted">
                  <EstadoBadge hoja={hoja} />
                  <span>{formatDate(hoja.created_at)}</span>
                </p>
              </Link>
            </CardItem>
          ))}
        </CardList>
      }
      table={
        <TableWrap>
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>ID del modelo</th>
                <th className={thClass}>Nombre</th>
                <th className={thClass}>Hoja</th>
                <th className={thClass}>Estado</th>
                <th className={thClass}>Creada</th>
              </tr>
            </thead>
            <tbody>
              {hojas.map((hoja) => (
                <tr key={hoja.codigo}>
                  <td className={`${tdClass} tabular-nums`}>
                    {hoja.modelo ?? "—"}
                  </td>
                  <td className={tdClass}>
                    <Link
                      href={href(hoja)}
                      className="underline decoration-gold underline-offset-4"
                    >
                      {hoja.articulo}
                    </Link>
                  </td>
                  <td className={`${tdClass} tabular-nums`}>{hoja.codigo}</td>
                  <td className={tdClass}>
                    <EstadoBadge hoja={hoja} />
                  </td>
                  <td className={tdClass}>{formatDate(hoja.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      }
    />
  );
}
