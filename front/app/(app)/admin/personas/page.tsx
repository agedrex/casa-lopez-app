import type { Metadata } from "next";
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
import { personRoleLabel } from "@/lib/people";
import { requireRole } from "@/lib/session";
import type { Persona } from "@/lib/types";
import { BackToAdmin } from "../back-link";
import { PersonaActivaForm, PersonaForm } from "./persona-forms";

export const metadata: Metadata = { title: "Personas" };

export default async function PersonasPage() {
  await requireRole("admin");
  const result = await apiGet<Persona[]>("/personas");

  return (
    <>
      <BackToAdmin />
      <PageHeader
        eyebrow="Administración"
        title="Personas"
        description="Quién cobra un sueldo o hace una tarea en la fábrica. Nada se borra: una persona que ya no está se desactiva y sus gastos y lotes quedan."
      />
      <div className="space-y-12">
        <section>
          <SectionTitle>Personas cargadas</SectionTitle>
          {result.ok ? (
            result.data.length === 0 ? (
              <Notice tone="info" title="Todavía no hay personas cargadas." />
            ) : (
              <TableWrap>
                <table className={tableClass}>
                  <thead>
                    <tr>
                      <th className={thClass}>Persona</th>
                      <th className={thClass}>Rol</th>
                      <th className={thClass}>Estado</th>
                      <th className={thClass}>Acción</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.data.map((persona) => (
                      <tr
                        key={persona.codigo}
                        className="hover:bg-paper-mid/50"
                      >
                        <td className={tdClass}>
                          {persona.nombre}
                          <span className="block text-xs text-muted">
                            {persona.codigo}
                          </span>
                        </td>
                        <td className={tdClass}>
                          {personRoleLabel(persona.rol)}
                        </td>
                        <td className={tdClass}>
                          <Badge tone={persona.activo ? "good" : "warn"}>
                            {persona.activo ? "Activa" : "Desactivada"}
                          </Badge>
                        </td>
                        <td className={tdClass}>
                          <PersonaActivaForm
                            codigo={persona.codigo}
                            nombre={persona.nombre}
                            activo={persona.activo}
                          />
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
        </section>
        <section>
          <SectionTitle>Nueva persona</SectionTitle>
          <Card>
            <PersonaForm />
          </Card>
        </section>
      </div>
    </>
  );
}
