import type { ReactNode } from "react";

import { cn } from "@/lib/cn";
import { toFa } from "@/lib/digits";
import { formatDuration, formatNumber } from "./analytics-utils";

export interface ChartSeries {
  key: string;
  label: string;
  color: string;
}

export function ChartCard({
  title,
  description,
  children,
  className,
  action,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
  action?: ReactNode;
}) {
  return (
    <section className={cn("rounded-2xl border border-slate-200 bg-white p-4", className)}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-black text-slate-900">{title}</h2>
          {description && <p className="mt-1 text-[11px] text-slate-400">{description}</p>}
        </div>
        {action}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function ChartLegend({ series }: { series: ChartSeries[] }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {series.map((item) => (
        <span key={item.key} className="inline-flex items-center gap-1.5 text-[10px] text-slate-500">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color }} />
          {item.label}
        </span>
      ))}
    </div>
  );
}

export function LineChart({
  data,
  series,
  height = 240,
}: {
  data: Array<Record<string, string | number>>;
  series: ChartSeries[];
  height?: number;
}) {
  const width = 720;
  const padding = { top: 16, right: 12, bottom: 30, left: 40 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const maxValue = Math.max(
    1,
    ...data.flatMap((point) => series.map((item) => Number(point[item.key] ?? 0))),
  );
  const niceMax = Math.max(4, Math.ceil(maxValue / 4) * 4);
  const xAt = (index: number) =>
    padding.left + (data.length <= 1 ? 0 : (index / (data.length - 1)) * plotWidth);
  const yAt = (value: number) =>
    padding.top + plotHeight - (value / niceMax) * plotHeight;
  const labelEvery = Math.max(1, Math.ceil(data.length / 7));

  return (
    <div>
      <ChartLegend series={series} />
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="mt-3 h-auto w-full overflow-visible"
        role="img"
        aria-label="نمودار روند"
      >
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const value = Math.round(niceMax * ratio);
          const y = padding.top + plotHeight - plotHeight * ratio;
          return (
            <g key={ratio}>
              <line
                x1={padding.left}
                x2={width - padding.right}
                y1={y}
                y2={y}
                stroke="#e2e8f0"
                strokeDasharray={ratio === 0 ? "0" : "4 4"}
              />
              <text x={padding.left - 7} y={y + 3} textAnchor="end" fontSize="9" fill="#94a3b8">
                {toFa(value)}
              </text>
            </g>
          );
        })}

        {series.map((item) => {
          const path = data
            .map((point, index) => {
              const value = Number(point[item.key] ?? 0);
              return `${index === 0 ? "M" : "L"} ${xAt(index)} ${yAt(value)}`;
            })
            .join(" ");
          return (
            <g key={item.key}>
              <path d={path} fill="none" stroke={item.color} strokeWidth="2.4" strokeLinejoin="round" />
              {data.map((point, index) => {
                const value = Number(point[item.key] ?? 0);
                return (
                  <circle
                    key={`${item.key}-${index}`}
                    cx={xAt(index)}
                    cy={yAt(value)}
                    r="2.6"
                    fill="#fff"
                    stroke={item.color}
                    strokeWidth="1.8"
                  >
                    <title>{`${item.label}: ${formatNumber(value)}`}</title>
                  </circle>
                );
              })}
            </g>
          );
        })}

        {data.map((point, index) =>
          index % labelEvery === 0 || index === data.length - 1 ? (
            <text
              key={String(point.label ?? index)}
              x={xAt(index)}
              y={height - 8}
              textAnchor="middle"
              fontSize="9"
              fill="#94a3b8"
            >
              {String(point.label ?? "")}
            </text>
          ) : null,
        )}
      </svg>
    </div>
  );
}

export function BarChart({
  items,
  series,
  showValues = false,
  height = 200,
  labelEvery = 1,
}: {
  items: Array<{ label: string; values: Record<string, number> }>;
  series: ChartSeries[];
  showValues?: boolean;
  height?: number;
  labelEvery?: number;
}) {
  const max = Math.max(1, ...items.flatMap((item) => series.map((s) => item.values[s.key] ?? 0)));
  return (
    <div>
      <ChartLegend series={series} />
      <div className="mt-3 overflow-x-auto pb-1">
        <div className="flex min-w-full items-end gap-2" style={{ height: height + 34 }}>
          {items.map((item, index) => (
            <div key={`${item.label}-${index}`} className="flex min-w-0 flex-1 flex-col items-center gap-1">
              <div className="flex w-full flex-1 items-end justify-center gap-0.5">
                {series.map((s) => {
                  const value = item.values[s.key] ?? 0;
                  return (
                    <div
                      key={s.key}
                      className="group relative w-full max-w-4 rounded-t-md transition-opacity hover:opacity-80"
                      style={{
                        height: `${Math.max(2, (value / max) * height)}px`,
                        backgroundColor: s.color,
                      }}
                      title={`${item.label} — ${s.label}: ${formatNumber(value)}`}
                    >
                      {showValues && value > 0 && (
                        <span className="absolute -top-4 left-1/2 -translate-x-1/2 text-[8px] text-slate-500">
                          {toFa(value)}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
              <span className="h-3 max-w-full truncate text-[9px] text-slate-400" title={item.label}>
                {index % labelEvery === 0 ? item.label : ""}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function HorizontalBars({
  items,
  series,
  labelWidth = 100,
}: {
  items: Array<{ label: string; icon?: string; values: Record<string, number>; total?: number }>;
  series: ChartSeries[];
  labelWidth?: number;
}) {
  const max = Math.max(1, ...items.flatMap((item) => series.map((s) => item.values[s.key] ?? 0)));
  return (
    <div>
      <ChartLegend series={series} />
      <div className="mt-3 space-y-2">
        {items.map((item) => (
          <div
            key={item.label}
            className="grid items-center gap-2"
            style={{ gridTemplateColumns: `${labelWidth}px 1fr 42px` }}
          >
            <span className="truncate text-[10px] text-slate-600" title={item.label}>
              {item.icon ? `${item.icon} ` : ""}
              {item.label}
            </span>
            <div className="flex flex-col gap-1">
              {series.map((s) => {
                const value = item.values[s.key] ?? 0;
                return (
                  <div key={s.key} className="flex items-center gap-1.5">
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${Math.max(value > 0 ? 2 : 0, (value / max) * 100)}%`,
                          backgroundColor: s.color,
                        }}
                        title={`${s.label}: ${formatNumber(value)}`}
                      />
                    </div>
                    <span className="w-8 shrink-0 text-left text-[9px] text-slate-400" dir="ltr">
                      {toFa(value)}
                    </span>
                  </div>
                );
              })}
            </div>
            <span className="text-left text-[10px] font-bold text-slate-700">
              {item.total !== undefined ? toFa(item.total) : ""}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function DonutChart({
  items,
  centerLabel,
  centerValue,
}: {
  items: Array<{ label: string; value: number; color: string; hint?: string }>;
  centerLabel?: string;
  centerValue?: string | number;
}) {
  const total = items.reduce((sum, item) => sum + item.value, 0);
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center">
      <div className="relative h-40 w-40 shrink-0">
        <svg viewBox="0 0 140 140" className="h-full w-full -rotate-90">
          <circle cx="70" cy="70" r={radius} fill="none" stroke="#f1f5f9" strokeWidth="16" />
          {items.map((item) => {
            if (item.value <= 0 || total <= 0) return null;
            const portion = item.value / total;
            const dash = portion * circumference;
            const currentOffset = offset;
            offset += dash;
            return (
              <circle
                key={item.label}
                cx="70"
                cy="70"
                r={radius}
                fill="none"
                stroke={item.color}
                strokeWidth="16"
                strokeDasharray={`${Math.max(0, dash - 2)} ${circumference}`}
                strokeDashoffset={-currentOffset}
                strokeLinecap="round"
              >
                <title>{`${item.label}: ${formatNumber(item.value)}`}</title>
              </circle>
            );
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-black text-slate-900">
            {centerValue !== undefined ? centerValue : formatNumber(total)}
          </span>
          {centerLabel && <span className="mt-0.5 text-[9px] text-slate-400">{centerLabel}</span>}
        </div>
      </div>
      <div className="w-full space-y-2">
        {items.map((item) => (
          <div key={item.label} className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5 text-[11px] text-slate-600">
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color }} />
              {item.label}
            </span>
            <span className="text-[11px] font-bold text-slate-800">
              {formatNumber(item.value)}
              {item.hint && <span className="mr-1 text-[9px] font-normal text-slate-400">{item.hint}</span>}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function TimingBars({
  items,
}: {
  items: Array<{ label: string; seconds: number | null; count: number; color: string }>;
}) {
  const max = Math.max(1, ...items.map((item) => item.seconds ?? 0));
  return (
    <div className="space-y-4">
      {items.map((item) => (
        <div key={item.label}>
          <div className="flex items-center justify-between gap-3">
            <span className="text-[11px] text-slate-600">{item.label}</span>
            <span className="text-[10px] font-bold text-slate-800">
              {formatDuration(item.seconds)}
            </span>
          </div>
          <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full"
              style={{
                width: `${item.seconds === null ? 0 : Math.max(2, (item.seconds / max) * 100)}%`,
                backgroundColor: item.color,
              }}
            />
          </div>
          <p className="mt-1 text-[9px] text-slate-400">{toFa(item.count)} نمونه</p>
        </div>
      ))}
    </div>
  );
}
