'use client';

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { ChartSpec, RiskDashboardSpec } from '../types';
import { chartPalette, resolveDataRef } from '../utils';

type Props = {
  chart: ChartSpec;
  dashboard: RiskDashboardSpec;
};

type SeriesRow = Record<string, unknown>;

function buildLineData(chart: ChartSpec, dashboard: RiskDashboardSpec) {
  const xField = chart.x_axis?.field ?? 'x';
  const yField = chart.y_axis?.field ?? 'value';
  const map = new Map<string | number, Record<string, unknown>>();

  chart.series.forEach((series) => {
    const rows = resolveDataRef<SeriesRow[]>(dashboard, series.data_ref) ?? [];
    rows.forEach((row, idx) => {
      const xValue = (row as Record<string, unknown>)[xField] ?? idx;
      const yValue =
        (row as Record<string, unknown>)[yField] ??
        (row as Record<string, unknown>)[series.id] ??
        null;
      const key = typeof xValue === 'number' ? xValue : String(xValue);
      const existing = map.get(key) ?? { [xField]: xValue };
      existing[series.id] = yValue;
      map.set(key, existing);
    });
  });

  const sorter = (a: Record<string, unknown>, b: Record<string, unknown>) => {
    const av = a[xField];
    const bv = b[xField];
    const aDate = typeof av === 'string' ? new Date(av).getTime() : Number(av);
    const bDate = typeof bv === 'string' ? new Date(bv).getTime() : Number(bv);
    if (!Number.isNaN(aDate) && !Number.isNaN(bDate)) return aDate - bDate;
    if (typeof av === 'number' && typeof bv === 'number') return av - bv;
    return String(av).localeCompare(String(bv));
  };

  return Array.from(map.values()).sort(sorter);
}

function formatTick(value: string | number) {
  const date = new Date(value);
  if (!Number.isNaN(date.getTime())) {
    return new Intl.DateTimeFormat('ru-RU', { month: 'short', day: '2-digit' }).format(date);
  }
  return String(value);
}

export function EquityChart({ chart, dashboard }: Props) {
  const data = buildLineData(chart, dashboard);
  const xField = chart.x_axis?.field ?? 'x';

  if (data.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 text-slate-400">
        Нет данных для графика {chart.title}
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-semibold text-white">{chart.title}</p>
        <span className="text-xs text-slate-400">Line</span>
      </div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis
              dataKey={xField}
              tick={{ fill: '#94a3b8', fontSize: 12 }}
              tickFormatter={formatTick}
              axisLine={{ stroke: '#1f2937' }}
            />
            <YAxis
              tick={{ fill: '#94a3b8', fontSize: 12 }}
              axisLine={{ stroke: '#1f2937' }}
              tickFormatter={(v) =>
                new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 }).format(
                  Number(v),
                )
              }
            />
            <Tooltip
              contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b' }}
              labelStyle={{ color: '#e2e8f0' }}
              formatter={(val: unknown) =>
                new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(
                  Number(val),
                )
              }
              labelFormatter={formatTick}
            />
            <Legend />
            {chart.series.map((series, idx) => (
              <Line
                key={series.id}
                type="monotone"
                dataKey={series.id}
                name={series.label}
                stroke={series.color ?? chartPalette[idx % chartPalette.length]}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
