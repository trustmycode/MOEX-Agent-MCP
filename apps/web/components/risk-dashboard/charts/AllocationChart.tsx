'use client';

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { ChartSpec, RiskDashboardSpec } from '../types';
import { chartPalette, resolveDataRef, toArray } from '../utils';

type Props = {
  chart: ChartSpec;
  dashboard: RiskDashboardSpec;
};

function renderBar(chart: ChartSpec, dashboard: RiskDashboardSpec) {
  const seriesList = toArray(chart.series);
  const series = seriesList[0];
  const data = toArray<Record<string, unknown>>(
    resolveDataRef<Array<Record<string, unknown>>>(dashboard, series?.data_ref),
  );
  const nameKey = chart.x_axis?.field ?? 'name';
  const valueKey = chart.y_axis?.field ?? 'value';

  if (!series || data.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-slate-400">
        Нет данных для графика {chart.title}
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-semibold text-white">{chart.title}</p>
        <span className="text-xs text-slate-400">Bar</span>
      </div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis
              dataKey={nameKey}
              tick={{ fill: '#94a3b8', fontSize: 12 }}
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
            />
            <Legend />
            <Bar
              dataKey={valueKey}
              name={series.label}
              fill={series.color ?? chartPalette[0]}
              radius={[6, 6, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function renderPie(chart: ChartSpec, dashboard: RiskDashboardSpec) {
  const seriesList = toArray(chart.series);
  const series = seriesList[0];
  const data = toArray<Record<string, unknown>>(
    resolveDataRef<Array<Record<string, unknown>>>(dashboard, series?.data_ref),
  );
  const nameKey = chart.x_axis?.field ?? 'name';
  const valueKey = chart.y_axis?.field ?? 'value';

  if (!series || data.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-slate-400">
        Нет данных для графика {chart.title}
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-semibold text-white">{chart.title}</p>
        <span className="text-xs text-slate-400">Pie</span>
      </div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Tooltip
              contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b' }}
              labelStyle={{ color: '#e2e8f0' }}
              formatter={(val: unknown) =>
                new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(
                  Number(val),
                )
              }
            />
            <Legend />
            <Pie
              data={data}
              dataKey={valueKey}
              nameKey={nameKey}
              cx="50%"
              cy="50%"
              outerRadius={120}
              label={({ name, percent }) =>
                `${name} ${(((percent ?? 0) * 100).toFixed(1)).replace('.', ',')}%`
              }
            >
              {data.map((_, idx) => (
                <Cell
                  // eslint-disable-next-line react/no-array-index-key
                  key={idx}
                  fill={chartPalette[idx % chartPalette.length]}
                />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function AllocationChart({ chart, dashboard }: Props) {
  if (chart.type === 'pie') return renderPie(chart, dashboard);
  return renderBar(chart, dashboard);
}
