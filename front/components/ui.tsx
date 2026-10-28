import type { ReactNode } from "react";

type Tone = "neutral" | "warn" | "good" | "alert";

const TONES: Record<Tone, string> = {
  neutral: "bg-parchment text-ink-soft",
  warn: "bg-blush/50 text-bordeaux",
  good: "bg-sage/20 text-ink-soft",
  alert: "bg-bordeaux text-white",
};

export function Badge({
  children,
  tone = "neutral",
  title,
}: {
  children: ReactNode;
  tone?: Tone;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-block max-w-full truncate rounded-full px-2.5 py-0.5 align-middle text-xs tracking-caps-sm ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-line pb-5 sm:mb-10 sm:pb-6">
      <div>
        {eyebrow ? (
          <p className="mb-2 text-xs uppercase tracking-caps-md text-gold-deep">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="text-2xl sm:text-4xl">{title}</h1>
        {description ? (
          <p className="mt-3 max-w-2xl text-sm text-muted">{description}</p>
        ) : null}
      </div>
      {actions}
    </div>
  );
}

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-card border border-line bg-surface p-4 shadow-card sm:p-6 ${className}`}
    >
      {children}
    </section>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="mb-4 text-xl">{children}</h2>;
}

export function Notice({
  title,
  children,
  tone = "warn",
}: {
  title: string;
  children?: ReactNode;
  tone?: "warn" | "info";
}) {
  const style =
    tone === "warn"
      ? "border-blush-deep bg-blush/30"
      : "border-line bg-paper-mid";
  return (
    <div className={`rounded-card border px-5 py-4 text-sm ${style}`}>
      <p className="font-bold text-ink-soft">{title}</p>
      {children ? <div className="mt-1 text-muted">{children}</div> : null}
    </div>
  );
}

export function ErrorNotice({
  title = "No pudimos cargar los datos.",
  message,
}: {
  title?: string;
  message: string;
}) {
  return (
    <div
      role="alert"
      className="rounded-card border border-bordeaux/30 bg-bordeaux/5 px-5 py-4 text-sm"
    >
      <p className="font-bold text-bordeaux">{title}</p>
      <p className="mt-1 text-muted">{message}</p>
    </div>
  );
}

export function TableWrap({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-x-auto overscroll-x-contain rounded-card border border-line bg-surface">
      {children}
    </div>
  );
}

export const tableClass = "w-full min-w-max border-collapse text-left text-sm";

/**
 * Phone layout for list pages: a stack of cards below `md`, the table from `md` up.
 * Render both and let CSS pick, so there is no hydration or width sniffing.
 */
export function ResponsiveTable({
  table,
  cards,
}: {
  table: ReactNode;
  cards: ReactNode;
}) {
  return (
    <>
      <div className="md:hidden">{cards}</div>
      <div className="hidden md:block">{table}</div>
    </>
  );
}

export function CardList({ children }: { children: ReactNode }) {
  return <ul className="space-y-3">{children}</ul>;
}

export function CardItem({ children }: { children: ReactNode }) {
  return (
    <li className="rounded-card border border-line bg-surface p-4 shadow-card">
      {children}
    </li>
  );
}
export const thClass =
  "border-b border-line bg-paper-mid px-3 py-3 text-xs font-normal uppercase tracking-caps-sm text-muted sm:px-4";
export const tdClass = "border-b border-line/70 px-3 py-3 align-top sm:px-4";
export const numClass = "text-right tabular-nums";
