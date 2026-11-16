export function Metric({
  label,
  children,
  highlight = false,
}: {
  label: string;
  children: React.ReactNode;
  highlight?: boolean;
}) {
  return (
    <div
      className={
        highlight
          ? "col-span-2 rounded-card border border-gold bg-parchment px-4 py-3"
          : ""
      }
    >
      <dt className="text-sm text-muted">{label}</dt>
      <dd
        className={
          highlight ? "text-2xl font-bold" : "text-base font-bold tabular-nums"
        }
      >
        {children}
      </dd>
    </div>
  );
}
