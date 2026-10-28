// Shared shape of what a server action answers to its form. Plain data, no "use server".

export type FormState = {
  status: "idle" | "ok" | "error" | "warning";
  message?: string;
  /** Warnings listed by the API (a quote that cannot be saved yet). */
  avisos?: string[];
  /** The action stopped on a warning and wants an explicit "load it anyway". */
  needsConfirm?: boolean;
};

export const IDLE: FormState = { status: "idle" };

export const ok = (message: string): FormState => ({ status: "ok", message });

export const error = (message: string, avisos: string[] = []): FormState => ({
  status: "error",
  message,
  avisos,
});
