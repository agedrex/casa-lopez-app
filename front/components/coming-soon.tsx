import { PageHeader } from "./ui";

export function ComingSoon({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <>
      <PageHeader eyebrow="Próximamente" title={title} />
      <div className="rounded-card border border-dashed border-line bg-surface px-8 py-16 text-center">
        <p className="font-display text-2xl">
          Esta sección todavía no está disponible.
        </p>
        <p className="mx-auto mt-3 max-w-md text-sm text-muted">
          {description}
        </p>
      </div>
    </>
  );
}
