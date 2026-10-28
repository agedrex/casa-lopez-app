"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type RecorderState = "idle" | "requesting" | "recording" | "paused";

export function useRecorder() {
  const [state, setState] = useState<RecorderState>("idle");
  const [seconds, setSeconds] = useState(0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [visible, setVisible] = useState(true);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const chunks = useRef<BlobPart[]>([]);
  const elapsed = useRef(0);
  const started = useRef(0);
  const url = useRef<string | null>(null);
  const requesting = useRef(false);
  const mounted = useRef(true);

  const release = useCallback(() => {
    stream.current?.getTracks().forEach((track) => {
      track.stop();
    });
    stream.current = null;
    recorder.current = null;
  }, []);

  useEffect(() => {
    const update = () => setVisible(!document.hidden);
    update();
    document.addEventListener("visibilitychange", update);
    return () => document.removeEventListener("visibilitychange", update);
  }, []);

  useEffect(() => {
    if (state !== "recording") return;
    const timer = window.setInterval(() => {
      setSeconds(
        Math.floor((elapsed.current + Date.now() - started.current) / 1000),
      );
    }, 250);
    return () => window.clearInterval(timer);
  }, [state]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      if (recorder.current && recorder.current.state !== "inactive") {
        recorder.current.onstop = null;
        recorder.current.stop();
      }
      release();
      if (url.current) URL.revokeObjectURL(url.current);
    };
  }, [release]);

  const start = useCallback(async () => {
    if (requesting.current || recorder.current) return;
    setError("");
    if (
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      setError(
        "Este navegador no permite grabar audio. Podés escribir el pedido abajo.",
      );
      return;
    }
    requesting.current = true;
    setState("requesting");
    try {
      // Ask for microphone access only after the person touches Grabar.
      const nextStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      if (!mounted.current) {
        nextStream.getTracks().forEach((track) => {
          track.stop();
        });
        return;
      }
      stream.current = nextStream;
      const nextRecorder = new MediaRecorder(nextStream);
      recorder.current = nextRecorder;
      chunks.current = [];
      elapsed.current = 0;
      started.current = Date.now();
      setSeconds(0);
      if (url.current) URL.revokeObjectURL(url.current);
      url.current = null;
      setAudioUrl(null);
      nextRecorder.ondataavailable = (event) => {
        if (event.data.size) chunks.current.push(event.data);
      };
      nextRecorder.onstop = () => {
        if (chunks.current.length) {
          // TODO: Connect an explicitly approved transcription flow with ElevenLabs.
          // The recording stays in this tab and is never uploaded here.
          const nextUrl = URL.createObjectURL(
            new Blob(chunks.current, { type: nextRecorder.mimeType }),
          );
          url.current = nextUrl;
          setAudioUrl(nextUrl);
        }
        release();
        setState("idle");
      };
      nextRecorder.start();
      setState("recording");
    } catch (cause) {
      release();
      setState("idle");
      setError(
        cause instanceof DOMException && cause.name === "NotAllowedError"
          ? "El micrófono está bloqueado. Permitilo desde el candado del navegador y volvé a tocar Grabar; también podés escribir el pedido."
          : "No pudimos iniciar el micrófono. Revisá que esté conectado y volvé a intentar, o escribí el pedido.",
      );
    } finally {
      requesting.current = false;
    }
  }, [release]);

  const pause = useCallback(() => {
    if (recorder.current?.state !== "recording") return;
    elapsed.current += Date.now() - started.current;
    recorder.current.pause();
    setSeconds(Math.floor(elapsed.current / 1000));
    setState("paused");
  }, []);

  const resume = useCallback(() => {
    if (recorder.current?.state !== "paused") return;
    started.current = Date.now();
    recorder.current.resume();
    setState("recording");
  }, []);

  const stop = useCallback(() => {
    if (!recorder.current || recorder.current.state === "inactive") return;
    if (recorder.current.state === "recording")
      elapsed.current += Date.now() - started.current;
    setSeconds(Math.floor(elapsed.current / 1000));
    recorder.current.stop();
    setState("idle");
  }, []);

  return {
    state,
    seconds,
    audioUrl,
    error,
    visible,
    start,
    pause,
    resume,
    stop,
  };
}
