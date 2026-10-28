/** Accepts only same-origin relative paths so `?next=` cannot become an open redirect. */
export function safeNext(value: string | null | undefined): string {
  if (!value) return "/";
  if (
    !value.startsWith("/") ||
    value.startsWith("//") ||
    value.startsWith("/\\")
  ) {
    return "/";
  }
  return value;
}
