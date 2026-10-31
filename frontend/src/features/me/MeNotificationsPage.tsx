import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/button";
import {
  NOTIFICATIONS_KEY,
  type AppNotification,
  type NotificationList,
} from "@/features/notifications/useUnreadNotifications";
import { api, errorMessage } from "@/lib/api";
import { formatJalali } from "@/lib/jalali";
import { useApi } from "@/lib/query";

function actionLabel(notification: AppNotification): string {
  if (notification.type === "business_rejected") return "اصلاح و ارسال دوباره";
  if (notification.type === "business_approved") return "مشاهده کسب‌وکار";
  if (notification.type === "quote_offer") return "مشاهده پیشنهادها";
  if (notification.type === "quote_accepted") return "مشاهده مشتری";
  if (notification.type === "quote_request") return "مشاهده درخواست";
  return "مشاهده";
}

function typeTone(type: string): "rose" | "brand" | "sky" | "slate" {
  if (type === "business_rejected" || type === "quote_cancelled") return "rose";
  if (type === "business_approved" || type === "quote_accepted") return "brand";
  if (type === "announcement" || type === "quote_offer") return "sky";
  return "slate";
}

function typeLabel(type: string): string {
  if (type === "business_rejected") return "رد کسب‌وکار";
  if (type === "business_approved") return "تأیید کسب‌وکار";
  if (type === "quote_request") return "درخواست قیمت";
  if (type === "quote_offer") return "پیشنهاد قیمت";
  if (type === "quote_accepted") return "پذیرش پیشنهاد";
  if (type === "quote_cancelled") return "لغو درخواست";
  if (type === "announcement") return "اطلاعیه";
  return "پیام";
}

export default function MeNotificationsPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { data, error, isLoading } = useApi<NotificationList>(
    NOTIFICATIONS_KEY,
    "/me/notifications",
  );

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
  }

  const markRead = useMutation({
    mutationFn: (id: string) => api(`/notifications/${id}/read`, { method: "PATCH" }),
    onSuccess: invalidate,
  });

  const markAllRead = useMutation({
    mutationFn: () => api("/me/notifications/read-all", { method: "PATCH" }),
    onSuccess: invalidate,
  });

  async function openNotification(notification: AppNotification) {
    const actionUrl = notification.payload?.action_url;
    if (!actionUrl) return;
    if (!notification.is_read) {
      try {
        await markRead.mutateAsync(notification.id);
      } catch {
        // Navigation should still work if marking as read fails.
      }
    }
    navigate(actionUrl);
  }

  const unreadCount = data?.unread_count ?? 0;

  return (
    <section className="space-y-3">
      <header className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-black text-slate-900">پیام‌ها و اعلان‌ها</h1>
          <p className="mt-1 text-xs text-slate-500">
            {unreadCount > 0
              ? `${unreadCount.toLocaleString("fa-IR")} پیام خوانده‌نشده`
              : "همه پیام‌ها خوانده شده‌اند."}
          </p>
        </div>
        {unreadCount > 0 && (
          <button
            type="button"
            className="shrink-0 text-xs text-brand-600 disabled:opacity-50"
            disabled={markAllRead.isPending}
            onClick={() => markAllRead.mutate()}
          >
            خواندن همه
          </button>
        )}
      </header>

      {isLoading && (
        <div className="flex justify-center py-16 text-brand-600">
          <Spinner />
        </div>
      )}
      {error && <p className="text-sm text-rose-600">{errorMessage(error)}</p>}
      {!isLoading && !error && data?.items.length === 0 && (
        <p className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
          هنوز پیامی ندارید.
        </p>
      )}
      {data?.items.map((item) => {
        const actionUrl = item.payload?.action_url;
        return (
          <article
            key={item.id}
            className={
              item.is_read
                ? "rounded-2xl border border-slate-200 bg-white p-4"
                : "rounded-2xl border border-brand-200 bg-brand-50/40 p-4"
            }
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-bold text-slate-900">{item.title}</p>
                <div className="mt-1 flex flex-wrap items-center gap-1.5">
                  <Badge tone={typeTone(item.type)}>{typeLabel(item.type)}</Badge>
                  {!item.is_read && <Badge tone="rose">جدید</Badge>}
                </div>
              </div>
              <span className="shrink-0 text-[11px] text-slate-400">
                {item.created_at ? formatJalali(item.created_at) : ""}
              </span>
            </div>
            <p className="mt-2 whitespace-pre-line text-sm leading-6 text-slate-600">
              {item.body}
            </p>
            <div className="mt-3 flex items-center justify-between gap-3">
              {actionUrl ? (
                <button
                  type="button"
                  className="text-xs font-medium text-brand-600"
                  onClick={() => void openNotification(item)}
                >
                  {actionLabel(item)} ←
                </button>
              ) : (
                <span />
              )}
              {!item.is_read && (
                <button
                  type="button"
                  className="text-[11px] text-slate-500 disabled:opacity-50"
                  disabled={markRead.isPending}
                  onClick={() => markRead.mutate(item.id)}
                >
                  علامت‌گذاری به‌عنوان خوانده‌شده
                </button>
              )}
            </div>
          </article>
        );
      })}
    </section>
  );
}
