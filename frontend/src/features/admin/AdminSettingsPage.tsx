import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage, type ApiError } from "@/lib/api";
import { useApi } from "@/lib/query";

export default function AdminSettingsPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useApi<{ search_trends: string[] }>(
    ["admin", "settings"],
    "/admin/settings",
  );
  const [terms, setTerms] = useState("");

  useEffect(() => {
    if (data) setTerms(data.search_trends.join("\n"));
  }, [data]);

  const save = useMutation({
    mutationFn: (value: string[]) =>
      api("/admin/settings/search_trends", {
        method: "PUT",
        body: JSON.stringify({ value }),
      }),
    onSuccess: () => {
      toast("جستجوهای پرطرفدار ذخیره شد.");
      void queryClient.invalidateQueries({ queryKey: ["admin", "settings"] });
      void queryClient.invalidateQueries({ queryKey: ["search", "trending"] });
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  return (
    <div className="max-w-3xl space-y-4">
      <div>
        <h1 className="text-lg font-black text-slate-900">تنظیمات</h1>
        <p className="mt-1 text-xs text-slate-500">تنظیمات محتوایی صفحه اصلی و جستجو</p>
      </div>

      {error && <p className="text-sm text-rose-600">{errorMessage(error)}</p>}

      <div className="rounded-2xl border border-slate-200 bg-white p-5">
        <p className="text-sm font-bold text-slate-900">جستجوهای پرطرفدار</p>
        <p className="mt-1 text-xs leading-6 text-slate-500">
          هر عبارت در یک خط. این موارد در صفحه جستجو و زیر فرم جستجوی صفحه اصلی نمایش داده
          می‌شوند.
        </p>
        <textarea
          value={terms}
          onChange={(event) => setTerms(event.target.value)}
          disabled={isLoading}
          rows={8}
          className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          placeholder={"تعمیر کولر\nلوله‌کشی\nبرق‌کاری"}
        />
        <div className="mt-3 flex items-center gap-2">
          <Button
            loading={save.isPending}
            onClick={() =>
              save.mutate(
                terms
                  .split("\n")
                  .map((term) => term.trim())
                  .filter(Boolean),
              )
            }
          >
            ذخیره تنظیمات
          </Button>
          <span className="text-xs text-slate-400">
            {terms.split("\n").filter((term) => term.trim()).length} عبارت
          </span>
        </div>
      </div>
    </div>
  );
}
