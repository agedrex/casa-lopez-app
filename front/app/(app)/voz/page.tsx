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
        description="Dicte o escriba un pedido corto. El asistente interpreta lo que dijo y le propone la carga; usted revisa y confirma. El asistente nunca calcula plata ni guarda nada por su cuenta."
      />
      <div className="space-y-10">
        <section aria-labelledby="voz-como">
          <SectionTitle>
            <span id="voz-como">Cómo funciona</span>
          </SectionTitle>
          <ol className="list-decimal space-y-1 pl-5 text-sm text-muted">
            <li>
              Dicte con el micrófono o escriba el pedido (hasta {VOZ_MAX_CHARS}{" "}
              caracteres).
            </li>
            <li>
              El modelo extrae qué quiere hacer y las palabras que usó; la
              aplicación busca el material, producto, lote o taller en la base.
            </li>
            <li>
              Si algo es ambiguo o falta, se lo pregunta; nunca elige por usted.
            </li>
            <li>
              Recién cuando usted toca «Confirmar y cargar» se guarda, con sus
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
            El <strong>texto</strong> del pedido se envía al proveedor del
            modelo (Anthropic) para interpretarlo; no se envían datos de la
            base. La aplicación <strong>no recibe ni guarda audio</strong>.
          </p>
          <p className="mt-2">
            Ojo: el dictado lo hace el navegador y, en Chrome, Edge y Safari,
            usa el servicio de reconocimiento de voz de Google o de Apple, que
            puede recibir el audio. Si eso no es aceptable, escriba el pedido.
          </p>
        </Notice>
      </div>
    </>
  );
}
