'use client';

import { RiskDashboardSpec, Severity } from './types';

type SeverityTheme = {
  bg: string;
  border: string;
  text: string;
  chip: string;
  accent: string;
};

const severityThemes: Record<Severity, SeverityTheme> = {
  info: {
    bg: 'bg-slate-900/60',
    border: 'border-slate-800/80',
    text: 'text-slate-100',
    chip: 'bg-slate-800 text-slate-200',
    accent: 'text-sky-400',
  },
  low: {
    bg: 'bg-emerald-900/40',
    border: 'border-emerald-800/60',
    text: 'text-emerald-50',
    chip: 'bg-emerald-800/60 text-emerald-100',
    accent: 'text-emerald-300',
  },
  medium: {
    bg: 'bg-amber-900/40',
    border: 'border-amber-800/60',
    text: 'text-amber-50',
    chip: 'bg-amber-800/70 text-amber-100',
    accent: 'text-amber-200',
  },
  warning: {
    bg: 'bg-amber-900/40',
    border: 'border-amber-800/60',
    text: 'text-amber-50',
    chip: 'bg-amber-800/70 text-amber-100',
    accent: 'text-amber-200',
  },
  high: {
    bg: 'bg-rose-900/50',
    border: 'border-rose-800/60',
    text: 'text-rose-50',
    chip: 'bg-rose-800/70 text-rose-100',
    accent: 'text-rose-200',
  },
  critical: {
    bg: 'bg-rose-950/80',
    border: 'border-rose-900/70',
    text: 'text-rose-50',
    chip: 'bg-rose-800/80 text-rose-100',
    accent: 'text-rose-200',
  },
};

export function getSeverityTheme(severity?: Severity): SeverityTheme {
  return severityThemes[severity ?? 'info'] ?? severityThemes.info;
}

export function resolveDataRef<T = unknown>(
  spec: RiskDashboardSpec,
  ref?: string,
): T | undefined {
  if (!ref) return undefined;
  const root: Record<string, unknown> = {
    ...spec,
    data: spec.data ?? {},
    time_series: spec.time_series ?? {},
    tables: spec.tables ?? {},
  };
  return ref.split('.').reduce<unknown>((acc, key) => {
    if (acc === undefined || acc === null) return undefined;
    if (typeof acc !== 'object') return undefined;
    return (acc as Record<string, unknown>)[key];
  }, root) as T | undefined;
}

export function formatMetricValue(value: number | string, unit?: string): string {
  if (typeof value === 'number') {
    const abs = Math.abs(value);
    const fractionDigits = abs >= 100 ? 0 : abs >= 10 ? 1 : 2;
    const formatted = new Intl.NumberFormat('ru-RU', {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    }).format(value);
    return unit ? `${formatted} ${unit}` : formatted;
  }

  return unit ? `${value} ${unit}` : String(value);
}

export function formatChange(change?: number | string): string | null {
  if (change === undefined || change === null) return null;
  const numeric =
    typeof change === 'number'
      ? change
      : Number(String(change).replace('%', '').replace('+', ''));
  if (Number.isNaN(numeric)) return String(change);

  const abs = Math.abs(numeric);
  const fractionDigits = abs >= 10 ? 1 : 2;
  const formatted = abs.toFixed(fractionDigits);
  return `${numeric >= 0 ? '+' : '-'}${formatted}%`;
}

export function formatAsOf(asOf: string): string {
  const date = new Date(asOf);
  if (Number.isNaN(date.getTime())) return asOf;
  return new Intl.DateTimeFormat('ru-RU', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
    timeZoneName: 'short',
  }).format(date);
}

export const chartPalette = [
  '#22c55e',
  '#38bdf8',
  '#a855f7',
  '#f97316',
  '#e11d48',
  '#facc15',
  '#0ea5e9',
  '#8b5cf6',
];

export function toArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? value : [];
}
