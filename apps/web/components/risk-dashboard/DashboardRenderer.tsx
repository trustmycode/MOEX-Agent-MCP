'use client';

import { AlertBlock } from './AlertBlock';
import { MetricCard } from './MetricCard';
import { AllocationChart } from './charts/AllocationChart';
import { EquityChart } from './charts/EquityChart';
import { RiskTable } from './tables/RiskTable';
import type { Alert, ChartSpec, LayoutItem, Metric, RiskDashboardSpec, TableSpec } from './types';
import { formatAsOf, resolveDataRef, toArray } from './utils';

type Props = {
  spec: RiskDashboardSpec;
  validationErrors?: string[];
};

function Section({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 shadow">
      {title && <p className="mb-3 text-sm font-semibold text-white">{title}</p>}
      {children}
    </section>
  );
}

export function DashboardRenderer({ spec, validationErrors }: Props) {
  const layout = toArray<LayoutItem>(spec.layout);
  const metrics = toArray<Metric>(spec.metrics);
  const charts = toArray<ChartSpec>(spec.charts);
  const tables = toArray<TableSpec>(spec.tables);
  const alerts = toArray<Alert>(spec.alerts);
  const metadata = spec.metadata ?? { as_of: '' };
  const validationList = toArray<string>(validationErrors);

  const metricMap = new Map(metrics.map((m) => [m.id, m]));
  const chartMap = new Map(charts.map((c) => [c.id, c]));
  const tableMap = new Map(tables.map((t) => [t.id, t]));

  const renderWidget = (item: LayoutItem) => {
    switch (item.type) {
      case 'kpi_grid': {
        const ids = Array.isArray(item.metric_ids) && item.metric_ids.length ? item.metric_ids : metrics.map((m) => m.id);
        const selected = ids.map((id) => metricMap.get(id)).filter(Boolean);
        return (
          <Section key={item.id} title={item.title ?? 'Ключевые метрики'}>
            {selected.length === 0 ? (
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3 text-slate-400">
                Нет метрик для отображения
              </div>
            ) : (
              <div
                className={`grid gap-4 ${
                  (item.columns ?? 0) >= 3 ? 'sm:grid-cols-2 xl:grid-cols-3' : 'sm:grid-cols-2'
                }`}
              >
                {selected.map((metric) => (
                  <MetricCard key={metric!.id} metric={metric!} />
                ))}
              </div>
            )}
          </Section>
        );
      }
      case 'alert_list': {
        const selectedAlerts =
          Array.isArray(item.alert_ids) && item.alert_ids.length > 0
            ? alerts.filter((a) => item.alert_ids?.includes(a.id))
            : alerts;
        return (
          <Section key={item.id} title={item.title ?? 'Предупреждения'}>
            <AlertBlock alerts={selectedAlerts} />
          </Section>
        );
      }
      case 'chart': {
        if (!item.chart_id) {
          return null;
        }
        const chart = chartMap.get(item.chart_id);
        if (!chart) {
          return (
            <Section key={item.id} title={item.title}>
              <div className="text-sm text-slate-400">Чарт {item.chart_id} не найден.</div>
            </Section>
          );
        }
        return chart.type === 'line' ? (
          <EquityChart key={item.id} chart={chart} dashboard={spec} />
        ) : (
          <AllocationChart key={item.id} chart={chart} dashboard={spec} />
        );
      }
      case 'table': {
        if (!item.table_id) return null;
        const table = tableMap.get(item.table_id);
        if (!table) {
          return (
            <Section key={item.id} title={item.title}>
              <div className="text-sm text-slate-400">Таблица {item.table_id} не найдена.</div>
            </Section>
          );
        }
        const rows =
          resolveDataRef<Array<Record<string, unknown>>>(spec, table.data_ref) ??
          (table as unknown as { rows?: Array<Record<string, unknown>> }).rows ??
          [];
        return <RiskTable key={item.id} table={table} rows={rows} />;
      }
      case 'text':
        return (
          <Section key={item.id} title={item.title}>
            <div className="space-y-2 text-sm text-slate-200">
              {item.description ?? 'Текстовый блок'}
            </div>
          </Section>
        );
      default:
        return null;
    }
  };

  return (
    <div className="space-y-4">
      <header className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4 shadow-lg">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">Портфель</p>
            <p className="text-xl font-semibold text-white">{metadata.portfolio_id ?? 'Портфель (demo)'}</p>
            <p className="text-sm text-slate-400">Сценарий: {metadata.scenario_type ?? '—'}</p>
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
            {spec.version && (
              <span className="rounded-full bg-slate-800 px-3 py-1 text-slate-200">
                Версия: {spec.version}
              </span>
            )}
          </div>
        </div>
        {validationList.length > 0 && (
          <div className="mt-3 rounded-lg border border-amber-700/70 bg-amber-900/20 p-2 text-xs text-amber-100">
            <p className="font-semibold">Ошибки схемы:</p>
            <ul className="list-disc pl-4">
              {validationList.map((err) => (
                <li key={err}>{err}</li>
              ))}
            </ul>
          </div>
        )}
      </header>

      {layout.length === 0 ? (
        <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-slate-300">
          Layout не задан. Будут показаны базовые блоки, если они появятся в данных.
        </div>
      ) : (
        <div className="space-y-4">{layout.map(renderWidget)}</div>
      )}
    </div>
  );
}


