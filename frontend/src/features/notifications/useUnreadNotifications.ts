import { useApi } from "@/lib/query";
import { useAuth } from "@/stores/auth";

export interface AppNotification {
  id: string;
  type: string;
  title: string;
  body: string;
  payload: {
    business_id?: string;
    business_slug?: string;
    business_name?: string;
    rejection_reason?: string;
    action?: "edit_business" | "view_business" | "announcement" | string;
    action_url?: string;
  };
  is_read: boolean;
  created_at?: string | null;
}

export interface NotificationList {
  items: AppNotification[];
  unread_count: number;
}

export const NOTIFICATIONS_KEY = ["notifications"] as const;

/** Unread messages power the header and profile badges. */
export function useUnreadNotificationCount(): number {
  const user = useAuth((state) => state.user);
  const { data } = useApi<{ count: number }>(
    ["notifications", "unread-count", user?.id ?? "guest"],
    "/me/notifications/unread-count",
    { enabled: Boolean(user), refetchInterval: 60_000 },
  );
  // Never show a previous account's cached badge after logout/user switch.
  return user ? (data?.count ?? 0) : 0;
}
