import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { Button, Spinner } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { fa } from "@/lib/format";

export interface DataColumn<T> {
  key: string;
  header: string;
  className?: string;
  cell: (row: T) => ReactNode;
}

export interface PageMeta {
  page: number;
  pages: number;
  total: number;
}

interface DataTableProps<T> {
  columns: DataColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  loading?: boolean;
  error?: string | null;
  empty?: string;
  meta?: PageMeta;
  onPageChange?: (page: number) => void;
  toolbar?: ReactNode;
  minWidthClassName?: string;
}

/**
 * Shared admin list table. Every dashboard list uses this component so layout,
 * density, pagination and empty/loading states stay consistent.
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading = false,
  error = null,
  empty = "موردی پیدا نشد.",
  meta,
  onPageChange,
  toolbar,
  minWidthClassName = "min-w-[900px]",
}: DataTableProps<T>) {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      {toolbar && <div className="border-b border-slate-200 p-2.5">{toolbar}</div>}

      {loading && (
        <div className="flex justify-center py-12 text-brand-600">
          <Spinner />
        </div>
      )}
      {!loading && error && <p className="p-4 text-sm text-rose-600">{error}</p>}
      {!loading && !error && rows.length === 0 && (
        <p className="p-8 text-center text-sm text-slate-500">{empty}</p>
      )}

      {!loading && !error && rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className={cn("w-full text-right text-sm", minWidthClassName)}>
            <thead className="bg-slate-50 text-[11px] uppercase text-slate-400">
              <tr>
                {columns.map((column) => (
                  <th key={column.key} className={cn("px-3 py-2.5 font-medium", column.className)}>
                    {column.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row) => (
                <tr key={rowKey(row)} className="align-top hover:bg-slate-50/70">
                  {columns.map((column) => (
                    <td key={column.key} className={cn("px-3 py-2.5", column.className)}>
                      {column.cell(row)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {meta && meta.total > 0 && onPageChange && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 px-3 py-2.5 text-xs text-slate-500">
          <span>
            صفحه {fa(meta.page)} از {fa(meta.pages)} — {fa(meta.total)} رکورد
          </span>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={meta.page <= 1}
              onClick={() => onPageChange(meta.page - 1)}
            >
              قبلی
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={meta.page >= meta.pages}
              onClick={() => onPageChange(meta.page + 1)}
            >
              بعدی
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export interface FilterLinkItem {
  label: string;
  value: string;
}

export function FilterLinks({
  items,
  active,
  hrefFor,
}: {
  items: FilterLinkItem[];
  active: string;
  hrefFor: (value: string) => string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {items.map((item) => (
        <Link
          key={item.value || "all"}
          to={hrefFor(item.value)}
          className={cn(
            "rounded-full border px-3 py-1.5 text-xs transition-colors",
            active === item.value
              ? "border-brand-600 bg-brand-600 text-white"
              : "border-slate-200 bg-white text-slate-600 hover:border-brand-300",
          )}
        >
          {item.label}
        </Link>
      ))}
    </div>
  );
}
