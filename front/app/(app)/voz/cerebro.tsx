import type { RecorderState } from "@/lib/use-recorder";
import styles from "./cerebro.module.css";

const particles = Array.from({ length: 88 }, (_, index) => {
  const y = 1 - (index / 87) * 2;
  const radius = Math.sqrt(1 - y * y);
  const angle = index * 2.399963229728653;
  const depth = Math.sin(angle) * radius;
  return {
    id: index,
    x: 160 + Math.cos(angle) * radius * 75,
    y: 160 + y * 75,
    size: 0.8 + (depth + 1) * 0.9,
    opacity: 0.3 + (depth + 1) * 0.3,
  };
});

export function Cerebro({
  state,
  visible,
}: {
  state: RecorderState;
  visible: boolean;
}) {
  const label =
    state === "recording"
      ? "Escuchando"
      : state === "paused"
        ? "Pausado"
        : "Quieto";
  return (
    <svg
      className={`${styles.brain} mx-auto block h-auto w-full max-w-72 text-gold-deep`}
      data-state={state}
      data-visible={visible}
      viewBox="0 0 320 320"
      role="img"
      aria-label={`Cerebro: ${label}`}
    >
      <defs>
        <radialGradient id="brain-glow">
          <stop offset="0" stopColor="currentColor" stopOpacity="0.22" />
          <stop offset="0.55" stopColor="currentColor" stopOpacity="0.07" />
          <stop offset="1" stopColor="currentColor" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle
        className={styles.pulse}
        cx="160"
        cy="160"
        r="112"
        fill="url(#brain-glow)"
      />
      <circle
        cx="160"
        cy="160"
        r="108"
        fill="none"
        stroke="currentColor"
        strokeOpacity="0.2"
        strokeDasharray="2 9"
      />
      <g
        className={styles.ringA}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      >
        <ellipse
          cx="160"
          cy="160"
          rx="125"
          ry="49"
          strokeOpacity="0.75"
          strokeDasharray="85 18 6 20"
        />
        <circle
          cx="160"
          cy="160"
          r="128"
          strokeOpacity="0.35"
          strokeDasharray="3 23"
        />
      </g>
      <g
        className={styles.ringB}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
      >
        <ellipse
          cx="160"
          cy="160"
          rx="54"
          ry="120"
          strokeOpacity="0.7"
          strokeDasharray="70 24 5 30"
        />
      </g>
      <g
        className={styles.ringC}
        fill="none"
        stroke="currentColor"
        strokeWidth="1"
      >
        <ellipse
          cx="160"
          cy="160"
          rx="112"
          ry="68"
          strokeOpacity="0.45"
          strokeDasharray="50 12 4 18"
        />
      </g>
      <circle
        cx="160"
        cy="160"
        r="76"
        fill="none"
        stroke="currentColor"
        strokeOpacity="0.25"
      />
      <g fill="currentColor">
        {particles.map((particle) => (
          <circle
            key={particle.id}
            cx={particle.x}
            cy={particle.y}
            r={particle.size}
            opacity={particle.opacity}
          />
        ))}
      </g>
      <circle cx="160" cy="160" r="4" fill="currentColor" />
    </svg>
  );
}
