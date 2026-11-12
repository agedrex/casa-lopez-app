import {
  Badge,
  Card,
  ErrorNotice,
  Notice,
  SectionTitle,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import type { ApiResult } from "@/lib/api";
import { personRoleLabel } from "@/lib/people";
import type { Persona } from "@/lib/types";
import { PersonaActivaForm, PersonaForm } from "./persona-forms";

/**
 * Who charges a salary or does a task in the factory, under Mano de obra. A person may or may
 * not have a user of the app: the two are not linked. Nothing is deleted: a person who is gone
 * is deactivated and their expenses and lots stay.
 */
export function PersonasPanel({
  personas,
}: {
  personas: ApiResult<Persona[]>;
}) {
  return (
    <section aria-label="Personas" className="space-y-6">
      <div>
        <SectionTitle>Personas</SectionTitle>
        <p className="-mt-2 text-sm text-muted">
          Quién cobra un sueldo o hace una tarea en la fábrica. Nada se borra:
          una persona que ya no está se desactiva y sus gastos y lotes quedan.
        </p>
      </div>
      {personas.ok ? (
        personas.data.length === 0 ? (
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
                {personas.data.map((persona) => (
                  <tr key={persona.codigo} className="hover:bg-paper-mid/50">
                    <td className={tdClass}>
                      {persona.nombre}
                      <span className="block text-xs text-muted">
                        {persona.codigo}
                      </span>
                    </td>
                    <td className={tdClass}>{personRoleLabel(persona.rol)}</td>
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
        <ErrorNotice message={personas.message} />
      )}
      <div>
        <SectionTitle>Nueva persona</SectionTitle>
        <Card>
          <PersonaForm />
        </Card>
      </div>
    </section>
  );
}
