"use client";

import { useState } from "react";
import { authClient, submitLogout } from "@/lib/auth-client";

export function LogoutButton() {
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [error, setError] = useState(false);

  async function handleSignOut() {
    setIsSigningOut(true);
    setError(false);
    const succeeded = await submitLogout(() => authClient.signOut());
    setIsSigningOut(false);
    if (succeeded) window.location.assign("/login");
    else setError(true);
  }

  return (
    <>
      <button disabled={isSigningOut} onClick={handleSignOut} type="button">
        {isSigningOut ? "Saliendo…" : "Cerrar sesión"}
      </button>
      {error ? (
        <p role="alert">No se pudo cerrar la sesión. Intentá de nuevo.</p>
      ) : null}
    </>
  );
}
