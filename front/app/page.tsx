"use client";

import { useEffect, useState } from "react";

type DemoResource = {
  name: string;
  description: string;
};

type DemoResponse = {
  mode: string;
  disclaimer: string;
  resources: DemoResource[];
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const [data, setData] = useState<DemoResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadDemoResources() {
      try {
        const response = await fetch(`${apiUrl}/api/demo/resources`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`La API respondió con estado ${response.status}.`);
        }
        setData((await response.json()) as DemoResponse);
      } catch (requestError) {
        if (controller.signal.aborted) return;
        setError(
          requestError instanceof Error
            ? requestError.message
            : "No se pudo conectar con la API de demostración.",
        );
      }
    }

    void loadDemoResources();
    return () => controller.abort();
  }, []);

  return (
    <main className="page-shell">
      <header className="topbar">
        <a className="brand" href="#inicio" aria-label="Casa López, inicio">
          <span className="brand-mark">CL</span>
          <span>Casa López</span>
        </a>
        <span className="stage-pill">PROTOTIPO · ETAPA 1</span>
      </header>

      <section className="hero" id="inicio">
        <p className="eyebrow">ESPACIO DE DESCUBRIMIENTO</p>
        <h1>Del taller a una cotización más clara.</h1>
        <p className="hero-copy">
          Un primer espacio para explorar productos, materiales y proveedores
          junto a Gerardo. Todavía estamos validando el proceso y sus reglas.
        </p>
        <div className="hero-note">
          <span className="note-icon" aria-hidden="true">
            ✳
          </span>
          <p>
            <strong>Una base para conversar, no para cotizar.</strong>
            <br />
            Los datos de esta pantalla son ficticios y no representan costos
            reales ni cálculos aprobados.
          </p>
        </div>
      </section>

      <section className="workspace" aria-labelledby="workspace-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">FLUJO EN EXPLORACIÓN</p>
            <h2 id="workspace-title">Un punto de partida</h2>
          </div>
          <span className="connection-status">
            <span
              className={`status-dot ${data ? "is-connected" : error ? "has-error" : ""}`}
            />
            {data
              ? "API conectada"
              : error
                ? "API sin conexión"
                : "Conectando…"}
          </span>
        </div>

        {error ? (
          <div className="message-card error-card" role="alert">
            <strong>No pudimos cargar la demostración.</strong>
            <p>
              {error} Revisá que la API esté corriendo en {apiUrl}.
            </p>
          </div>
        ) : !data ? (
          <div className="message-card" aria-live="polite">
            Cargando datos demostrativos desde la API…
          </div>
        ) : (
          <>
            <div className="resource-grid">
              {data.resources.map((resource, index) => (
                <article className="resource-card" key={resource.name}>
                  <span className="resource-number">0{index + 1}</span>
                  <h3>{resource.name}</h3>
                  <p>{resource.description}</p>
                  <span className="demo-tag">DATO FICTICIO</span>
                </article>
              ))}
            </div>
            <p className="disclaimer">{data.disclaimer}</p>
          </>
        )}
      </section>

      <footer className="footer">
        <span>
          Casa López <span aria-hidden="true">·</span> Descubrimiento y
          prototipo inicial
        </span>
        <span>Una herramienta en construcción</span>
      </footer>
    </main>
  );
}
