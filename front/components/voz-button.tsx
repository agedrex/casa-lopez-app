"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useDictation } from "@/lib/use-dictation";
import { ICONS, Icon } from "./nav-icons";

const buttonClass =
  "grid size-9 place-items-center rounded-full border border-line text-ink-soft transition-colors hover:border-gold hover:text-ink focus-visible:outline-2 focus-visible:outline-gold";

/**
 * Desktop header microphone. One press starts the browser's dictation (es-AR); when it ends, the person lands on /voz with
 * the text in the box. Nothing is interpreted or saved from here: the proposal and its confirmation stay on /voz.
 * Browsers without dictation get a plain link to /voz, where the request can be typed. Mobile has its own entry (the "+" button).
 */
export function VozButton() {
  const router = useRouter();
  const heard = useRef("");
  const [problem, setProblem] = useState("");
  const dictation = useDictation((text) => {
    heard.current = text;
  });
  const { listening, status } = dictation;
  const wasListening = useRef(false);

  // The recognizer ends by itself (silence) or when the person presses again: both land here.
  useEffect(() => {
    if (wasListening.current && !listening) {
      const text = heard.current.trim();
      heard.current = "";
      if (text) router.push(`/voz?texto=${encodeURIComponent(text)}`);
      else setProblem(status);
    }
    wasListening.current = listening;
  }, [listening, status, router]);

  useEffect(() => {
    if (!problem) return;
    const timer = window.setTimeout(() => setProblem(""), 6000);
    return () => window.clearTimeout(timer);
  }, [problem]);

  if (!dictation.supported) {
    return (
      <Link
        href="/voz"
        title="Voz: escribir un pedido"
        className={`${buttonClass} hidden lg:grid`}
      >
        <Icon path={ICONS.mic} className="size-5" />
        <span className="sr-only">Ir a Voz</span>
      </Link>
    );
  }

  return (
    <div className="relative hidden lg:block">
      <button
        type="button"
        aria-pressed={listening}
        title={listening ? "Detener y usar lo dictado" : "Dictar un pedido"}
        onClick={() => {
          setProblem("");
          if (listening) dictation.stop();
          else dictation.start("");
        }}
        className={`${buttonClass} ${
          listening
            ? "animate-pulse border-bordeaux bg-bordeaux text-white"
            : ""
        }`}
      >
        <Icon path={ICONS.mic} className="size-5" />
        <span className="sr-only">
          {listening ? "Detener el dictado" : "Dictar un pedido por voz"}
        </span>
      </button>
      <output className="sr-only">{listening ? "Escuchando…" : ""}</output>
      {problem ? (
        <p
          role="alert"
          className="absolute right-0 z-10 mt-2 w-64 rounded-card border border-line bg-surface p-3 text-xs text-bordeaux shadow-card"
        >
          {problem}
        </p>
      ) : null}
    </div>
  );
}
