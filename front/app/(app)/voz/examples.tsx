import { VOZ_EXAMPLES } from "@/lib/voz";

/** Examples of how to phrase a request. With `onPick` each one can be copied into the text box; without it it is plain text. */
export function ExampleList({
  onPick,
}: {
  onPick?: (example: string) => void;
}) {
  return (
    <ul className="space-y-2 text-sm">
      {VOZ_EXAMPLES.map((example) => (
        <li
          key={example}
          className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-line bg-paper-mid px-4 py-2.5"
        >
          <span>«{example}»</span>
          {onPick ? (
            <button
              type="button"
              onClick={() => onPick(example)}
              aria-label={`Usar el ejemplo: ${example}`}
              className="text-xs uppercase tracking-caps-sm text-gold-deep underline underline-offset-4 hover:text-ink"
            >
              Usar
            </button>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
