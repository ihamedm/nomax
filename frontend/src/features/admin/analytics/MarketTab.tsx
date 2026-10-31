import { DataTable, type DataColumn } from "@/features/admin/data-table";
import { toFa } from "@/lib/digits";
import type {
  CategoryDemandRow,
  KeywordRow,
  MarketAnalytics,
  NoResultKeywordRow,
  SubcategoryDemandRow,
} from "./types";
import { ChartCard, HorizontalBars } from "./charts";
import { formatNumber, marketStatusMeta } from "./analytics-utils";

function StatusPill({ row }: { row: CategoryDemandRow }) {
  const meta = marketStatusMeta(row.status);
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] ${meta.className}`}>
      {meta.label}
    </span>
  );
}

export function MarketTab({ data }: { data: MarketAnalytics }) {
  const topCategories = data.categories
    .filter((row) => row.demand > 0 || row.businesses > 0)
    .slice(0, 10);
  const chartItems = topCategories.map((row) => ({
    label: row.name,
    icon: row.icon,
    values: { demand: row.demand, businesses: row.businesses },
    total: row.demand,
  }));

  const totalDemand = data.categories.reduce((sum, row) => sum + row.demand, 0);
  const totalSearches = data.categories.reduce((sum, row) => sum + row.searches, 0);
  const totalQuotes = data.categories.reduce((sum, row) => sum + row.quotes, 0);

  const categoryColumns: DataColumn<CategoryDemandRow>[] = [
    {
      key: "category",
      header: "دسته‌بندی",
      cell: (row) => (
        <div className="flex items-center gap-2">
          <span className="text-base">{row.icon}</span>
          <span className="text-xs font-bold text-slate-800">{row.name}</span>
        </div>
      ),
    },
    {
      key: "businesses",
      header: "کسب‌وکار",
      cell: (row) => <span className="text-xs text-slate-700">{toFa(row.businesses)}</span>,
    },
    {
      key: "searches",
      header: "جستجو",
      cell: (row) => <span className="text-xs text-slate-700">{toFa(row.searches)}</span>,
    },
    {
      key: "no_results",
      header: "بدون نتیجه",
      cell: (row) => (
        <span className={row.no_results > 0 ? "text-xs text-rose-600" : "text-xs text-slate-400"}>
          {toFa(row.no_results)}
        </span>
      ),
    },
    {
      key: "quotes",
      header: "استعلام",
      cell: (row) => <span className="text-xs text-slate-700">{toFa(row.quotes)}</span>,
    },
    {
      key: "unanswered",
      header: "استعلام فعال بی‌پاسخ",
      cell: (row) => (
        <span
          className={row.unanswered_quotes > 0 ? "text-xs text-amber-700" : "text-xs text-slate-400"}
        >
          {toFa(row.unanswered_quotes)}
        </span>
      ),
    },
    {
      key: "demand",
      header: "تقاضا",
      cell: (row) => <span className="text-xs font-black text-slate-900">{toFa(row.demand)}</span>,
    },
    {
      key: "status",
      header: "وضعیت",
      cell: (row) => <StatusPill row={row} />,
    },
  ];

  const subcategoryColumns: DataColumn<SubcategoryDemandRow>[] = [
    {
      key: "subcategory",
      header: "زیردسته",
      cell: (row) => (
        <div>
          <p className="text-xs font-bold text-slate-800">{row.name}</p>
          <p className="mt-0.5 text-[10px] text-slate-400">{row.category_name}</p>
        </div>
      ),
    },
    {
      key: "searches",
      header: "جستجو",
      cell: (row) => <span className="text-xs text-slate-700">{toFa(row.searches)}</span>,
    },
    {
      key: "quotes",
      header: "استعلام",
      cell: (row) => <span className="text-xs text-slate-700">{toFa(row.quotes)}</span>,
    },
    {
      key: "businesses",
      header: "کسب‌وکار",
      cell: (row) => <span className="text-xs text-slate-700">{toFa(row.businesses)}</span>,
    },
    {
      key: "demand",
      header: "تقاضا",
      cell: (row) => (
        <span className="text-xs font-black text-brand-700">{toFa(row.demand)}</span>
      ),
    },
  ];

  const keywordColumns: DataColumn<KeywordRow>[] = [
    {
      key: "keyword",
      header: "کلیدواژه",
      cell: (row) => <span className="text-xs font-medium text-slate-800">{row.keyword}</span>,
    },
    {
      key: "searches",
      header: "جستجو",
      cell: (row) => <span className="text-xs text-slate-700">{toFa(row.searches)}</span>,
    },
    {
      key: "avg_results",
      header: "میانگین نتایج",
      cell: (row) => <span className="text-xs text-slate-700">{toFa(row.avg_results)}</span>,
    },
    {
      key: "no_results",
      header: "بدون نتیجه",
      cell: (row) => (
        <span className={row.no_results > 0 ? "text-xs text-rose-600" : "text-xs text-slate-400"}>
          {toFa(row.no_results)}
        </span>
      ),
    },
  ];

  const noResultColumns: DataColumn<NoResultKeywordRow>[] = [
    {
      key: "keyword",
      header: "کلیدواژه",
      cell: (row) => <span className="text-xs font-medium text-slate-800">{row.keyword}</span>,
    },
    {
      key: "searches",
      header: "تعداد جستجو",
      cell: (row) => <span className="text-xs font-bold text-rose-600">{toFa(row.searches)}</span>,
    },
    {
      key: "category",
      header: "دسته مرتبط",
      cell: (row) => <span className="text-xs text-slate-600">{row.category_name}</span>,
    },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {[
          { label: "کل تقاضا", value: totalDemand, hint: "جستجو + استعلام" },
          { label: "کل جستجوها", value: totalSearches, hint: "در همه دسته‌ها" },
          { label: "کل استعلام‌ها", value: totalQuotes, hint: "در همه دسته‌ها" },
          { label: "دسته‌های فعال", value: data.categories.length, hint: "دسته اصلی" },
        ].map((item) => (
          <div key={item.label} className="rounded-2xl border border-slate-200 bg-white p-3.5">
            <p className="text-[11px] text-slate-400">{item.label}</p>
            <p className="mt-1 text-xl font-black text-slate-900">{formatNumber(item.value)}</p>
            <p className="mt-1 text-[10px] text-slate-400">{item.hint}</p>
          </div>
        ))}
      </div>

      <ChartCard
        title="تقاضا در برابر عرضه"
        description="ده دسته اصلی با بیشترین تقاضا؛ تقاضا = جستجو + استعلام"
      >
        <HorizontalBars
          items={chartItems}
          series={[
            { key: "demand", label: "تقاضا", color: "#10a56f" },
            { key: "businesses", label: "کسب‌وکار", color: "#94a3b8" },
          ]}
          labelWidth={110}
        />
      </ChartCard>

      <section className="space-y-2">
        <div>
          <h2 className="text-sm font-black text-slate-900">تحلیل دسته‌بندی‌ها</h2>
          <p className="mt-1 text-[11px] text-slate-400">
            مقایسه عرضه، جستجو، استعلام و استعلام‌های بی‌پاسخ در هر دسته.
          </p>
        </div>
        <DataTable
          columns={categoryColumns}
          rows={data.categories}
          rowKey={(row) => row.id}
          empty="داده‌ای برای دسته‌بندی‌ها وجود ندارد."
          minWidthClassName="min-w-[900px]"
        />
      </section>

      <div className="grid gap-3 xl:grid-cols-2">
        <section className="space-y-2">
          <div>
            <h2 className="text-sm font-black text-slate-900">پرتقاضاترین زیردسته‌ها</h2>
            <p className="mt-1 text-[11px] text-slate-400">
              زیردسته‌هایی که بیشترین جستجو و استعلام را دارند.
            </p>
          </div>
          <DataTable
            columns={subcategoryColumns}
            rows={data.subcategories}
            rowKey={(row) => row.id}
            empty="هنوز تقاضایی برای زیردسته‌ها ثبت نشده است."
            minWidthClassName="min-w-[520px]"
          />
        </section>

        <section className="space-y-2">
          <div>
            <h2 className="text-sm font-black text-slate-900">کلیدواژه‌های پرجستجو</h2>
            <p className="mt-1 text-[11px] text-slate-400">
              عبارت‌های پرتکرار و میانگین نتایج نمایش‌داده‌شده.
            </p>
          </div>
          <DataTable
            columns={keywordColumns}
            rows={data.keywords}
            rowKey={(row) => row.keyword}
            empty="هنوز جستجویی با کلیدواژه ثبت نشده است."
            minWidthClassName="min-w-[440px]"
          />
        </section>
      </div>

      <section className="space-y-2">
        <div>
          <h2 className="text-sm font-black text-slate-900">جستجوهای بدون نتیجه</h2>
          <p className="mt-1 text-[11px] text-slate-400">
            فرصت‌های از دست‌رفته: عبارت‌هایی که کاربر جستجو کرده اما نتیجه‌ای ندیده است.
          </p>
        </div>
        <DataTable
          columns={noResultColumns}
          rows={data.no_result_keywords}
          rowKey={(row) => `${row.keyword}-${row.category_id ?? "none"}`}
          empty="هیچ جستجوی بدون نتیجه‌ای ثبت نشده است."
          minWidthClassName="min-w-[500px]"
        />
      </section>
    </div>
  );
}
