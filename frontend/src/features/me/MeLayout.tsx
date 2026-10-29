import { Navigate, Outlet, useLocation } from "react-router-dom";

import { Spinner } from "@/components/ui/button";
import { loginPath, returnPath } from "@/lib/auth-redirect";
import { useAuth } from "@/stores/auth";

/** Auth gate for `/me`; the app shell owns the header and bottom navigation. */
export function MeLayout() {
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

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-4">
      <Outlet />
    </div>
  );
}
