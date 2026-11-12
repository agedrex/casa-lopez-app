"use client";

import { useEffect, useState } from "react";
import { traerDolarDelDia } from "./actions";

/**
 * Asks the server for today's BNA quote once per browser session and day, only when the
 * stored one is older. Shows nothing unless the call is running; a failure keeps the last
 * stored rate on screen.
 */
export function DolarAlDia({
  today,
  stale,
}: {
  today: string;
  stale: boolean;
}) {
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    if (!stale) return;
    const key = `dolar-bna-${today}`;
    if (sessionStorage.getItem(key)) return;
    sessionStorage.setItem(key, "1");
    setUpdating(true);
    traerDolarDelDia()
      .catch(() => undefined)
      .finally(() => setUpdating(false));
  }, [stale, today]);

  return updating ? (
    <output className="mt-2 block text-xs text-muted">
      Buscando la cotización de hoy…
    </output>
  ) : null;
}
