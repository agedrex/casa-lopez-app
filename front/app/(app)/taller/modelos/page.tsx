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

export const metadata: Metadata = { title: "Modelos del taller" };

const buttonClass =
  "inline-flex min-h-11 items-center justify-center rounded-card bg-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm text-white hover:bg-ink-soft sm:min-h-0";

type Search = Promise<{ estado?: string | string[] }>;

export default async function ModelosDelTallerPage({
  searchParams,
}: {
  searchParams: Search;
}) {
  const { user } = await requireSession();
  if (!canFillFormularios(user.role)) redirect("/");
  const esAdmin = hasRole(user.role, "admin");

  // The admin reviews: it opens on what is waiting for it (COMPLETADO); `?estado=todas` shows every state. The taller
  // sees every sheet the API gives it (the ones to fill, the completed ones and its own) with no filter.
  const { estado: pedido } = await searchParams;
  const pedida = (Array.isArray(pedido) ? pedido[0] : pedido)?.trim() ?? "";
  const filtro = esAdmin
    ? pedida === "todas"
      ? null
      : isEstado(pedida)
        ? pedida
        : "COMPLETADO"
    : null;
  const result = await apiGet<FormularioResumen[]>(
    `/formularios${filtro ? `?estado=${filtro}` : ""}`,
  );

  return (
    <>
      <PageHeader
        eyebrow="Producción"
        title={esAdmin ? "Hojas de consumos" : "Mis modelos"}
        description={
          esAdmin
            ? "Las hojas que carga el taller con las medidas reales. Abrí una completada para validarla (las medidas pasan al modelo) o devolverla con un comentario."
            : "Los modelos nuevos y su hoja de consumos y herrajes. Tocá uno para completarla."
        }
        actions={
          <Link href="/taller/modelos/nuevo" className={buttonClass}>
            Nuevo modelo
          </Link>
        }
      />
      {esAdmin ? <Filtros actual={filtro} /> : null}
      {result.ok ? (
        result.data.length === 0 ? (
          <Notice
            tone="info"
            title={
              esAdmin && filtro === "COMPLETADO"
                ? "No hay hojas esperando revisión."
                : "Todavía no hay hojas."
            }
          >
            {esAdmin
              ? "Cuando el taller complete una hoja aparece acá."
              : "Creá un modelo nuevo para empezar."}
          </Notice>
        ) : (
          <Lista hojas={result.data} userId={user.id} />
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

function Lista({
  hojas,
  userId,
}: {
  hojas: FormularioResumen[];
  userId: string;
}) {
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
                  {hoja.creado_por === userId ? (
                    <Badge>Creado por vos</Badge>
                  ) : null}
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
                    {hoja.creado_por === userId ? (
                      <span className="ml-2">
                        <Badge>Creado por vos</Badge>
                      </span>
                    ) : null}
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
