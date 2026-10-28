import Link from "next/link";

export function Wordmark({
  href = "/",
  tone = "dark",
}: {
  href?: string;
  tone?: "dark" | "light";
}) {
  const color = tone === "dark" ? "text-ink" : "text-white";
  const detail = tone === "dark" ? "text-gold-deep" : "text-gold";
  return (
    <Link
      href={href}
      className={`inline-flex flex-col leading-none ${color}`}
      aria-label="Casa López, inicio"
    >
      <span className="font-display text-xl uppercase tracking-caps-md">
        Casa López
      </span>
      <span
        className={`mt-1.5 text-[0.625rem] uppercase tracking-caps-lg ${detail}`}
      >
        Desde 1939
      </span>
    </Link>
  );
}
