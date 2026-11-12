import { redirect } from "next/navigation";

// Models moved to Productos; this keeps old links (alerts, bookmarks) working.
export default async function ModelosMovedPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(await searchParams)) {
    for (const item of Array.isArray(value) ? value : value ? [value] : []) {
      query.append(key, item);
    }
  }
  redirect(`/productos/modelos${query.size ? `?${query}` : ""}`);
}
