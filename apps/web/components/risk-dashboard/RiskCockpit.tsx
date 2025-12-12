'use client';

import { AlertBlock } from './AlertBlock';
import { DashboardRenderer } from './DashboardRenderer';
import { MetricCard } from './MetricCard';
import { AllocationChart } from './charts/AllocationChart';
import { EquityChart } from './charts/EquityChart';
import { RiskTable } from './tables/RiskTable';
import type { Alert, ChartSpec, LayoutItem, Metric, RiskDashboardSpec, TableSpec } from './types';
import { formatAsOf, resolveDataRef, toArray } from './utils';

type Props = {
  data: RiskDashboardSpec;
};

export function RiskCockpit({ data }: Props) {
  const layout = toArray<LayoutItem>(data.layout);
  const metrics = toArray<Metric>(data.metrics);
  const charts = toArray<ChartSpec>(data.charts);
  const tables = toArray<TableSpec>(data.tables);
  const alerts = toArray<Alert>(data.alerts);
  const metadata = data.metadata ?? { as_of: '' };

  if (layout.length > 0) {
    return <DashboardRenderer spec={{ ...data, layout, metrics, charts, tables, alerts, metadata }} />;
  }

  return (
    <div className="space-y-6">
      <header className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4 shadow-lg">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">Портфель</p>
            <p className="text-xl font-semibold text-white">
              {metadata.portfolio_id ?? 'Портфель (demo)'}
            </p>
            <p className="text-sm text-slate-400">
              Сценарий: {metadata.scenario_type ?? '—'}
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded-full bg-slate-800 px-3 py-1 text-slate-200">
              Дата: {formatAsOf(metadata.as_of ?? '')}
            </span>
            {metadata.base_currency && (
              <span className="rounded-full bg-slate-800 px-3 py-1 text-slate-200">
                Валюта: {metadata.base_currency}
              </span>
            )}
          </div>
        </div>
      </header>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <p className="text-sm font-semibold text-white">Ключевые метрики</p>
          <span className="text-xs text-slate-400">{metrics.length} шт.</span>
        </div>
        {metrics.length === 0 ? (
          <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-slate-400">
            Нет метрик для отображения
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {metrics.map((metric) => (
              <MetricCard key={metric.id} metric={metric} />
            ))}
          </div>
        )}
      </section>

      <AlertBlock alerts={alerts} />

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-4">
          {charts.length === 0 && (
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-slate-400">
              Графики отсутствуют
            </div>
          )}
          {charts.map((chart) =>
            chart.type === 'line' ? (
              <EquityChart key={chart.id} chart={chart} dashboard={data} />
            ) : (
              <AllocationChart key={chart.id} chart={chart} dashboard={data} />
            ),
          )}
        </div>

        <div className="space-y-4">
          {tables.length === 0 && (
            <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-slate-400">
              Таблицы отсутствуют
            </div>
          )}
          {tables.map((table) => {
            const rows = resolveDataRef<Array<Record<string, unknown>>>(data, table.data_ref) ?? [];
            return <RiskTable key={table.id} table={table} rows={rows} />;
          })}
        </div>
      </section>
    </div>
  );
}
