import { useApi } from "@/lib/query";
import { useAuth } from "@/stores/auth";

export const OWNER_REVIEWS_KEY = ["reviews", "owner-list"] as const;
export const OWNER_REVIEW_BADGE_KEY = ["reviews", "owner-unread"] as const;

export interface OwnerReview {
  id: string;
  business_id: string;
  business_name: string;
  business_slug: string;
  rating: number;
  text?: string | null;
  author_name?: string | null;
  status: string;
  is_private: boolean;
  reply?: string | null;
  replied_at?: string | null;
  created_at?: string | null;
}

export interface OwnerReviewList {
  items: OwnerReview[];
  unread_count: number;
}

/** Number of pending/private reviews the owner has not opened yet. */
export function useOwnerReviewBadge(): number {
  const user = useAuth((state) => state.user);
  const enabled = Boolean(user) && user?.role === "owner";
  const { data } = useApi<{ count: number }>(
    ["reviews", "owner-unread", user?.id ?? "guest"],
    "/me/reviews/unread-count",
    { enabled, refetchInterval: 60_000 },
  );
  return enabled ? (data?.count ?? 0) : 0;
}
