import { AdminNav } from "./admin-nav";

// Every admin page is checked on its own (requireRole) and by proxy.ts; this layout only gives them one frame.
export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <AdminNav />
      {children}
    </>
  );
}
