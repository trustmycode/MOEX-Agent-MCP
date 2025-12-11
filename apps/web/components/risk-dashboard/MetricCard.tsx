'use client';

import { ArrowDownRight, ArrowUpRight } from 'lucide-react';
import { formatChange, formatMetricValue, getSeverityTheme } from './utils';
import type { Metric } from './types';

type Props = {
  metric: Metric;
};

export function MetricCard({ metric }: Props) {
  const theme = getSeverityTheme(metric.severity);
  const changeText = formatChange(metric.change);
  const isPositive = (metric.change ?? 0) >= 0;
  const ChangeIcon = isPositive ? ArrowUpRight : ArrowDownRight;

  return (
    <div
      className={`rounded-xl border p-4 shadow-sm transition-colors ${theme.bg} ${theme.border}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-2">
          <p className="text-sm text-slate-400">{metric.label}</p>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-semibold text-white">
              {formatMetricValue(metric.value, metric.unit)}
            </span>
            {changeText && (
              <span
                className={`flex items-center gap-1 text-sm font-medium ${
                  isPositive ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                <ChangeIcon className="h-4 w-4" />
                {changeText}
              </span>
            )}
          </div>
        </div>
        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${theme.chip}`}>
          {metric.severity ?? 'info'}
        </span>
      </div>
    </div>
  );
}
