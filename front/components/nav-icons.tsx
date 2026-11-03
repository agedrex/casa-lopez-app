export const ICONS: Record<string, string> = {
  "/": "M4 13h6V4H4v9zm0 7h6v-5H4v5zm8 0h8V11h-8v9zm0-16v5h8V4h-8z",
  "/productos": "M4 7l8-4 8 4-8 4-8-4zm0 4l8 4 8-4M4 15l8 4 8-4",
  "/materiales":
    "M12 3v18M16.5 7.5C16.5 6 14.5 5 12 5S7.5 6 7.5 8s2 2.5 4.5 3 4.5 1 4.5 3-2 3-4.5 3-4.5-1-4.5-2.5",
  "/fabricacion": "M3 20h18M5 20V9l5 3V9l5 3V5h4v15",
  "/corte": "M4 4l16 16M20 4L4 20M8 8l2-2M14 18l2-2",
  "/cueros": "M4 7l8-4 8 4v10l-8 4-8-4V7zm0 0l8 4 8-4M12 11v10",
  "/grilla": "M3 4h18v16H3zM3 10h18M3 15h18M9 4v16M15 4v16",
  "/calidad": "M12 3 2 21h20L12 3zm0 6v5m0 3h.01",
  more: "M5 12h.01M12 12h.01M19 12h.01",
  mic: "M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM6 11a6 6 0 0 0 12 0M12 17v4",
  "/voz":
    "M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM6 11a6 6 0 0 0 12 0M12 17v4",
  "/dolar":
    "M12 3v18M16 7.5C16 6 14.5 5 12 5S8 6 8 8s2 2.5 4 3 4 1 4 3-1.5 3-4 3-4-1-4-2.5",
  "/talleres": "M3 21h18M5 21V10l7-5 7 5v11M10 21v-6h4v6",
  "/costos-fijos": "M5 3h14v18H5zM9 8h6M9 12h6M9 16h3",
  "/admin": "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z",
  "/admin/modelos": "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
  box: "M4 7l8-4 8 4-8 4-8-4zm0 0v10l8 4 8-4V7M12 11v10",
};

export function Icon({
  path,
  className = "size-6",
}: {
  path: string;
  className?: string;
}) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={path} />
    </svg>
  );
}
