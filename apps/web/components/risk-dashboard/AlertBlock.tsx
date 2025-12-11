'use client';

import {
  AlertCircle,
  AlertTriangle,
  CircleAlert,
  OctagonAlert,
  ShieldAlert,
} from 'lucide-react';
import { getSeverityTheme } from './utils';
import type { Alert } from './types';

type Props = {
  alerts?: Alert[];
};

const severityIcon: Record<
  NonNullable<Alert['severity']>,
  (props: { className?: string }) => JSX.Element
> = {
  info: CircleAlert,
  low: AlertCircle,
  medium: AlertTriangle,
  warning: AlertTriangle,
  high: ShieldAlert,
  critical: OctagonAlert,
};

export function AlertBlock({ alerts }: Props) {
  if (!alerts || alerts.length === 0) return null;

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-semibold text-white">Предупреждения</p>
        <span className="text-xs text-slate-400">{alerts.length} шт.</span>
      </div>
      <div className="space-y-3">
        {alerts.map((alert) => {
          const Icon = severityIcon[alert.severity] ?? CircleAlert;
          const theme = getSeverityTheme(alert.severity);
          return (
            <div
              key={alert.id}
              className={`rounded-xl border p-3 ${theme.bg} ${theme.border} flex items-start gap-3`}
            >
              <Icon className={`h-5 w-5 ${theme.accent} shrink-0`} />
              <div className="space-y-1">
                <p className={`${theme.text} text-sm leading-snug`}>{alert.message}</p>
                {alert.related_ids && alert.related_ids.length > 0 && (
                  <div className="flex flex-wrap gap-2 text-xs text-slate-400">
                    {alert.related_ids.map((rel) => (
                      <span
                        key={rel}
                        className="rounded-full bg-slate-800/70 px-2 py-0.5 text-[11px] uppercase tracking-wide"
                      >
                        {rel}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
