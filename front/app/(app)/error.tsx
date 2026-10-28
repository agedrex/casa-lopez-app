"use client";

import { ErrorNotice, PageHeader } from "@/components/ui";

export default function ErrorPage({
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <>
      <PageHeader title="Algo salió mal" />
      <ErrorNotice
        title="No pudimos mostrar esta sección."
        message="Intente nuevamente. Si el problema continúa, avise al administrador."
      />
      <button
        type="button"
        onClick={reset}
        className="inline-flex min-h-11 items-center mt-6 rounded-card border border-ink px-4 py-2 text-sm hover:bg-ink hover:text-white"
      >
        Reintentar
      </button>
    </>
  );
}
