import { create } from "zustand";

import { api } from "@/lib/api";
import { tokens } from "@/lib/tokens";
import type { User } from "@/types";

interface AuthState {
  user: User | null;
  ready: boolean;
  setSession: (access: string, refresh: string, user: User) => void;
  hydrate: () => Promise<void>;
  logout: () => Promise<void>;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  ready: false,

  setSession(access, refresh, user) {
    tokens.set(access, refresh);
    set({ user, ready: true });
  },

  async hydrate() {
    if (!tokens.access) {
      set({ user: null, ready: true });
      return;
    }
    try {
      const user = await api<User>("/auth/me");
      set({ user, ready: true });
    } catch {
      tokens.clear();
      set({ user: null, ready: true });
    }
  },

  async logout() {
    const refresh = tokens.refresh;
    tokens.clear();
    set({ user: null });
    if (refresh) {
      try {
        await api("/auth/logout", { method: "POST", body: JSON.stringify({ refresh }) });
      } catch {
        // Local session is already gone; the server-side family expires on its own.
      }
    }
  },
}));

export function isAdmin(user: User | null): boolean {
  return user?.role === "admin" || user?.role === "superadmin";
}
