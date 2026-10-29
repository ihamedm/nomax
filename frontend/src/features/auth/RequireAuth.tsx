import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { Spinner } from "@/components/ui/button";
import { loginPath, returnPath } from "@/lib/auth-redirect";
import { useAuth } from "@/stores/auth";

/**
 * Route-level guard for pages that require a session. Sends unauthenticated
 * visitors to `/login` and remembers the exact page (including query state) so
 * they return there after signing in.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const user = useAuth((state) => state.user);
  const ready = useAuth((state) => state.ready);
  const location = useLocation();

  if (!ready) {
    return (
      <div className="flex min-h-[50dvh] items-center justify-center text-brand-600">
        <Spinner />
      </div>
    );
  }
  if (!user) return <Navigate to={loginPath(returnPath(location))} replace />;

  return <>{children}</>;
}
