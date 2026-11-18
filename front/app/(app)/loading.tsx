export default function Loading() {
  return (
    <output aria-busy="true" className="block animate-pulse">
      <span className="sr-only">Cargando…</span>
      <div className="mb-8 h-9 w-56 rounded-card bg-parchment" />
      <div className="space-y-3">
        {[0, 1, 2, 3, 4].map((row) => (
          <div key={row} className="h-11 rounded-card bg-parchment/70" />
        ))}
      </div>
    </output>
  );
}
