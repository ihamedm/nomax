import { useSearchParams } from "react-router-dom";

import { Spinner } from "@/components/ui/button";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useApi } from "@/lib/query";
import { GeneralTab } from "@/features/admin/analytics/GeneralTab";
import { QuotesTab } from "@/features/admin/analytics/QuotesTab";
import { MarketTab } from "@/features/admin/analytics/MarketTab";
import { BusinessesTab } from "@/features/admin/analytics/BusinessesTab";
import { MapTab } from "@/features/admin/analytics/MapTab";
import { LogsTab } from "@/features/admin/analytics/LogsTab";
import type {
  AnalyticsMapData,
  AnalyticsOverview,
  BusinessPerformance,
  MarketAnalytics,
  QuoteAnalytics,
} from "@/features/admin/analytics/types";

type Tab = "general" | "quotes" | "market" | "businesses" | "map" | "logs";

const TABS: Array<{ value: Tab; label: string; icon: string }> = [
  { value: "general", label: "عمومی", icon: "▦" },
  { value: "quotes", label: "استعلام‌ها", icon: "⌕" },
  { value: "market", label: "بازار و تقاضا", icon: "◔" },
  { value: "businesses", label: "کسب‌وکارها", icon: "⌂" },
  { value: "map", label: "نقشه", icon: "⌖" },
  { value: "logs", label: "لاگ رویدادها", icon: "☷" },
];

export default function AdminAnalyticsPage() {
  const [params, setParams] = useSearchParams();
  const rawTab = params.get("tab");
  const tab: Tab =
    rawTab === "quotes" ||
    rawTab === "market" ||
    rawTab === "businesses" ||
    rawTab === "map" ||
    rawTab === "logs"
      ? rawTab
      : "general";

  function setTab(next: Tab) {
    const nextParams = new URLSearchParams(params);
    if (next === "general") nextParams.delete("tab");
    else nextParams.set("tab", next);
    setParams(nextParams, { replace: true });
  }

  const overview = useApi<AnalyticsOverview>(
    ["admin", "analytics", "overview"],
    "/admin/analytics/overview",
    { enabled: tab === "general" },
  );
  const quotes = useApi<QuoteAnalytics>(
    ["admin", "analytics", "quotes"],
    "/admin/analytics/quotes",
    { enabled: tab === "quotes" },
  );
  const market = useApi<MarketAnalytics>(
    ["admin", "analytics", "market"],
    "/admin/analytics/market",
    { enabled: tab === "market" },
  );
  const businesses = useApi<BusinessPerformance>(
    ["admin", "analytics", "businesses"],
    "/admin/analytics/businesses",
    { enabled: tab === "businesses" },
  );
  const map = useApi<AnalyticsMapData>(
    ["admin", "analytics", "map"],
    "/admin/analytics/map",
    { enabled: tab === "map" },
  );

  const activeQuery =
    tab === "general"
      ? overview
      : tab === "quotes"
        ? quotes
        : tab === "market"
          ? market
          : tab === "businesses"
            ? businesses
            : tab === "map"
              ? map
              : null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-bold">تحلیل و آمار</h1>
          <p className="mt-1 text-xs text-slate-500">
            تصویر زنده‌ای از رشد، استعلام‌ها و تعادل عرضه و تقاضا در بازار محلی.
          </p>
        </div>
        <span className="rounded-full bg-slate-200/70 px-2.5 py-1 text-[10px] text-slate-500">
          همه زمان‌ها به وقت تهران
        </span>
      </div>

      <div className="inline-flex rounded-2xl border border-slate-200 bg-white p-1">
        {TABS.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => setTab(item.value)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs transition-colors",
              tab === item.value
                ? "bg-brand-50 font-bold text-brand-700"
                : "text-slate-500 hover:bg-slate-50",
            )}
          >
            <span aria-hidden>{item.icon}</span>
            {item.label}
          </button>
        ))}
      </div>

      {activeQuery?.isLoading && (
        <div className="flex justify-center py-20 text-brand-600">
          <Spinner />
        </div>
      )}

      {activeQuery?.error && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
          {errorMessage(activeQuery.error)}
        </div>
      )}

      {tab === "general" && overview.data && <GeneralTab data={overview.data} />}
      {tab === "quotes" && quotes.data && <QuotesTab data={quotes.data} />}
      {tab === "market" && market.data && <MarketTab data={market.data} />}
      {tab === "businesses" && businesses.data && (
        <BusinessesTab data={businesses.data} />
      )}
      {tab === "map" && map.data && <MapTab data={map.data} />}
      {tab === "logs" && <LogsTab />}
    </div>
  );
}
