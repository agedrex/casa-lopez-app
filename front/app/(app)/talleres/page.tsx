import type { Metadata } from "next";
import Link from "next/link";
import { TallerBadges } from "@/components/taller-badges";
import {
  ErrorNotice,
  Notice,
  numClass,
  PageHeader,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatArs, formatDate, formatQuantity } from "@/lib/format";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { Taller } from "@/lib/types";

export const metadata: Metadata = { title: "Talleres" };

export default async function TalleresPage() {
  const { user } = await requireSession();
  const result = await apiGet<Taller[]>("/talleres");

  return (
    <>
      <PageHeader
        eyebrow="Producción"
        title="Talleres"
        description="Agenda de los talleres que confeccionan. Un taller desactivado se oculta de los lotes nuevos pero conserva su historia."
        actions={
          canWrite(user.role) ? (
            <Link
              href="/talleres/nuevo"
              className="rounded-card bg-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm text-white hover:bg-ink-soft"
            >
              Nuevo taller
            </Link>
          ) : undefined
        }
      />
      {result.ok ? (
        result.data.length === 0 ? (
          <Notice tone="info" title="Todavía no hay talleres cargados." />
        ) : (
          <TableWrap>
            <table className={tableClass}>
              <thead>
                <tr>
                  <th className={thClass}>Taller</th>
                  <th className={thClass}>Contacto</th>
                  <th className={thClass}>Teléfono</th>
                  <th className={`${thClass} ${numClass}`}>Lotes</th>
                  <th className={`${thClass} ${numClass}`}>Unidades</th>
                  <th className={thClass}>Último lote</th>
                  <th className={`${thClass} ${numClass}`}>Cobró en total</th>
                </tr>
              </thead>
              <tbody>
                {result.data.map((taller) => (
                  <tr key={taller.codigo} className="hover:bg-paper-mid/50">
                    <td className={tdClass}>
                      <Link
                        href={`/talleres/${encodeURIComponent(taller.codigo)}`}
                        className="underline decoration-gold underline-offset-4"
                      >
                        {taller.nombre}
                      </Link>
                      <span className="block text-xs text-muted">
                        {taller.codigo}
                      </span>{" "}
                      <TallerBadges taller={taller} />
                    </td>
                    <td className={tdClass}>{taller.contacto ?? "—"}</td>
                    <td className={tdClass}>{taller.telefono ?? "—"}</td>
                    <td className={`${tdClass} ${numClass}`}>{taller.lotes}</td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatQuantity(taller.unidades)}
                    </td>
                    <td className={tdClass}>
                      {formatDate(taller.ultimo_lote)}
                    </td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatArs(taller.cobro_total_ars)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        )
      ) : (
        <ErrorNotice message={result.message} />
      )}
    </>
  );
}
