import type { Metadata } from "next";
import { ReadOnlyNote } from "@/components/form";
import { ErrorNotice, Notice, PageHeader, SectionTitle } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { VozEstado } from "@/lib/types";
import { VOZ_MAX_CHARS } from "@/lib/voz";
import { ExampleList } from "./examples";
import { VozPanel } from "./voz-panel";

export const metadata: Metadata = { title: "Voz" };

export default async function VozPage() {
  const { user } = await requireSession();
  const writer = canWrite(user.role);
  const estado = writer ? await apiGet<VozEstado>("/voz/estado") : null;

  return (
    <>
      <PageHeader
        eyebrow="Carga"
        title="Voz"
        description="Grabá audio en tu teléfono o escribí un pedido corto. Para interpretarlo, escribí el texto: el asistente te propone la carga y vos revisás y confirmás. Nunca calcula plata ni guarda nada por su cuenta."
      />
      <div className="space-y-10">
        <section aria-labelledby="voz-como">
          <SectionTitle>
            <span id="voz-como">Cómo funciona</span>
          </SectionTitle>
          <ol className="list-decimal space-y-1 pl-5 text-sm text-muted">
            <li>
              Grabá audio si querés conservarlo en esta pestaña. Para
              interpretar el pedido, escribilo en el cuadro (hasta{" "}
              {VOZ_MAX_CHARS} caracteres).
            </li>
            <li>
              El modelo extrae qué querés hacer y las palabras que usaste; la
              aplicación busca el material, producto, lote o taller en la base.
            </li>
            <li>
              Si algo es ambiguo o falta, te lo pregunta; nunca elige por vos.
            </li>
            <li>
              Recién cuando tocás «Confirmar y cargar» se guarda, con tus
              permisos y las mismas validaciones que las otras pantallas.
            </li>
          </ol>
        </section>

        {writer ? (
          estado?.ok ? (
            <VozPanel configured={estado.data.configurado} />
          ) : (
            <ErrorNotice
              message={estado?.ok === false ? estado.message : "Sin datos."}
            />
          )
        ) : (
          <section>
            <ReadOnlyNote />
            <div className="mt-6">
              <SectionTitle>Ejemplos de pedidos</SectionTitle>
              <ExampleList />
            </div>
          </section>
        )}

        <Notice tone="info" title="Privacidad">
          <p>
            El <strong>audio no sale de tu teléfono</strong>: queda solo en esta
            pestaña, no se sube ni se usa para interpretar el pedido. Al cerrar
            la pestaña se pierde.
          </p>
          <p className="mt-2">
            El <strong>texto</strong> que escribas sí se envía a Anthropic para
            interpretarlo; no se envían datos de la base. Revisá la propuesta
            antes de confirmar cualquier carga.
          </p>
        </Notice>
      </div>
    </>
  );
}
