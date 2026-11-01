import { formatDate, formatQuantity, todayIso } from "@/lib/format";
import { leerCargas } from "./cargas";

/** Cuts loaded today from this device. No prices here. */
export async function MisCargas() {
  const hoy = todayIso();
  const cargas = (await leerCargas()).filter((carga) => carga.fecha === hoy);
  return (
    <section aria-labelledby="mis-cargas">
      <h2 id="mis-cargas" className="mb-4 text-xl">
        Mis cargas de hoy
      </h2>
      {cargas.length === 0 ? (
        <p className="text-base text-muted">
          Todavía no cargaste cortes hoy desde este celular.
        </p>
      ) : (
        <ul className="space-y-3">
          {cargas.map((carga, index) => (
            <li
              key={`${carga.pieza}-${carga.lote}-${index}`}
              className="rounded-card border border-line bg-surface p-4"
            >
              <p className="text-base font-bold">
                {formatQuantity(carga.m2)} m² · piel {carga.pieza}
              </p>
              <p className="text-sm text-muted">
                {carga.producto || "Producto"} · lote {carga.lote} ·{" "}
                {formatDate(carga.fecha)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
