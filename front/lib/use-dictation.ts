"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import {
  getSpeechRecognition,
  joinSpoken,
  type SpeechRecognitionLike,
  speechErrorMessage,
} from "./voz";

const noSubscription = () => () => {};

/**
 * Push-to-talk dictation with the browser's own recognizer (es-AR). The audio is handled by the browser: this app never
 * receives or stores it, only the text the person confirms. `start(base)` keeps what was typed before and appends what is
 * said; every partial result is handed to `onText`, so the text box stays editable all the time.
 */
export function useDictation(onText: (text: string) => void) {
  // Server and first client render say "unsupported"; the real answer arrives after hydration without a mismatch.
  const supported = useSyncExternalStore(
    noSubscription,
    () => getSpeechRecognition() !== null,
    () => false,
  );
  const [listening, setListening] = useState(false);
  const [status, setStatus] = useState("");
  const recognition = useRef<SpeechRecognitionLike | null>(null);
  const callback = useRef(onText);
  useEffect(() => {
    callback.current = onText;
  });

  const stop = useCallback(() => recognition.current?.stop(), []);

  const start = useCallback((base: string) => {
    const Recognizer = getSpeechRecognition();
    if (!Recognizer || recognition.current) return;
    const next = new Recognizer();
    next.lang = "es-AR";
    next.continuous = false;
    next.interimResults = true;
    next.maxAlternatives = 1;
    next.onresult = (event) => {
      let spoken = "";
      for (let index = 0; index < event.results.length; index += 1) {
        spoken += event.results[index][0].transcript;
      }
      callback.current(joinSpoken(base, spoken));
    };
    next.onerror = (event) => {
      const message = speechErrorMessage(event.error);
      if (message) setStatus(message);
    };
    next.onend = () => {
      recognition.current = null;
      setListening(false);
      setStatus((current) =>
        current === "Escuchando…"
          ? "Listo. Revise el texto y toque «Interpretar»."
          : current,
      );
    };
    recognition.current = next;
    setStatus("Escuchando…");
    setListening(true);
    try {
      next.start();
    } catch {
      recognition.current = null;
      setListening(false);
      setStatus("No se pudo iniciar el micrófono. Escriba el pedido.");
    }
  }, []);

  // Leaving the screen must release the microphone.
  useEffect(() => () => recognition.current?.abort(), []);

  return { supported, listening, status, start, stop };
}
