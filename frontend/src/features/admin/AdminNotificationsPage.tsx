import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";

const AUDIENCES = [
  { value: "all", label: "همه کاربران" },
  { value: "owners", label: "مالکان کسب‌وکار" },
  { value: "customers", label: "مشتریان" },
  { value: "user", label: "یک کاربر مشخص" },
];

export default function AdminNotificationsPage() {
  const toast = useToast();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [audience, setAudience] = useState("all");
  const [userId, setUserId] = useState("");
  const [actionUrl, setActionUrl] = useState("");
  const [sending, setSending] = useState(false);
  const [lastSent, setLastSent] = useState<number | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) {
      toast("عنوان پیام را وارد کنید.");
      return;
    }
    if (!body.trim()) {
      toast("متن پیام را وارد کنید.");
      return;
    }
    if (audience === "user" && !userId.trim()) {
      toast("شناسه کاربر گیرنده را وارد کنید.");
      return;
    }
    setSending(true);
    try {
      const result = await api<{ sent: number }>("/admin/notifications/broadcast", {
        method: "POST",
        body: JSON.stringify({
          title: title.trim(),
          body: body.trim(),
          audience,
          user_id: audience === "user" ? userId.trim() : undefined,
          action_url: actionUrl.trim() || undefined,
        }),
      });
      setLastSent(result.sent);
      toast(`پیام برای ${result.sent.toLocaleString("fa-IR")} کاربر در صندوق پیام ارسال شد.`);
    } catch (error) {
      toast(errorMessage(error));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="text-sm font-black text-slate-900">ارسال پیام درون‌برنامه‌ای</h2>
        <p className="mt-2 text-xs leading-6 text-slate-500">
          این پیام در صندوق پیام کاربران نومکس نمایش داده می‌شود و با اعلان پوش (Push) متفاوت
          است. پیام‌های خوانده‌نشده با نشان قرمز روی آیکون حساب کاربر و کارت پیام‌ها در پروفایل
          نمایش داده می‌شوند.
        </p>
      </div>

      <form onSubmit={submit} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
        <div>
          <label className="text-xs font-bold text-slate-700" htmlFor="notif-title">
            عنوان
          </label>
          <input
            id="notif-title"
            value={title}
            maxLength={160}
            onChange={(event) => setTitle(event.target.value)}
            className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm outline-none focus:border-brand-400"
            placeholder="مثلاً اطلاعیه به‌روزرسانی نومکس"
          />
        </div>

        <div>
          <label className="text-xs font-bold text-slate-700" htmlFor="notif-body">
            متن پیام
          </label>
          <textarea
            id="notif-body"
            value={body}
            rows={5}
            maxLength={4000}
            onChange={(event) => setBody(event.target.value)}
            className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-brand-400"
            placeholder="متن پیام برای گیرندگان..."
          />
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="text-xs font-bold text-slate-700" htmlFor="notif-audience">
              گیرندگان
            </label>
            <select
              id="notif-audience"
              value={audience}
              onChange={(event) => setAudience(event.target.value)}
              className="mt-1 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:border-brand-400"
            >
              {AUDIENCES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs font-bold text-slate-700" htmlFor="notif-link">
              لینک مقصد (اختیاری)
            </label>
            <input
              id="notif-link"
              value={actionUrl}
              onChange={(event) => setActionUrl(event.target.value)}
              className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 text-sm outline-none focus:border-brand-400"
              placeholder="/me/businesses"
              dir="ltr"
            />
          </div>
        </div>

        {audience === "user" && (
          <div>
            <label className="text-xs font-bold text-slate-700" htmlFor="notif-user">
              شناسه کاربر گیرنده
            </label>
            <input
              id="notif-user"
              value={userId}
              onChange={(event) => setUserId(event.target.value)}
              className="mt-1 h-10 w-full rounded-xl border border-slate-200 px-3 text-xs outline-none focus:border-brand-400"
              placeholder="user UUID"
              dir="ltr"
            />
          </div>
        )}

        <div className="flex items-center justify-between gap-3 border-t border-slate-100 pt-4">
          <p className="text-[11px] text-slate-400">
            گیرنده هر پیام با شناسه کاربر (user_id) ذخیره می‌شود.
          </p>
          <Button type="submit" disabled={sending}>
            {sending ? "در حال ارسال..." : "ارسال پیام"}
          </Button>
        </div>
        {lastSent !== null && (
          <p className="rounded-xl bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
            آخرین ارسال: {lastSent.toLocaleString("fa-IR")} پیام در صندوق گیرندگان ثبت شد.
          </p>
        )}
      </form>
    </div>
  );
}
