'use client';

import type { RiskDashboardDataRow, TableSpec } from '../types';
import { toArray } from '../utils';

type Props = {
  table: TableSpec;
  rows: RiskDashboardDataRow[];
};

function normalizeRows(
  rows: unknown,
  columns: TableSpec['columns'],
): Array<Record<string, unknown>> {
  // Если пришёл массив — обрабатываем построчно
  if (Array.isArray(rows)) {
    return rows.map((row) => {
      // Массив значений: сопоставляем по порядку колонок
      if (Array.isArray(row)) {
        return columns.reduce<Record<string, unknown>>((acc, col, idx) => {
          acc[col.id] = row[idx] ?? '—';
          return acc;
        }, {});
      }
      // Объект — оставляем как есть
      if (row && typeof row === 'object') {
        return row as Record<string, unknown>;
      }
      // Примитив — оборачиваем в значение первой колонки
      return { [columns[0]?.id ?? 'value']: row };
    });
  }

  // Объект-словарь (например { TICKER: { ... } }) → превращаем в массив строк
  if (rows && typeof rows === 'object') {
    return Object.entries(rows as Record<string, unknown>).map(([key, value]) => {
      if (value && typeof value === 'object') {
        return { ticker: key, ...(value as Record<string, unknown>) };
      }
      return { ticker: key, value };
    });
  }

  return [];
}

const alignClass: Record<NonNullable<TableSpec['columns'][number]['align']>, string> = {
  left: 'text-left',
  right: 'text-right',
  center: 'text-center',
};

function resolveAlign(align?: TableSpec['columns'][number]['align']) {
  return align ? alignClass[align] : 'text-left';
}

export function RiskTable({ table, rows }: Props) {
  const columns = toArray<TableSpec['columns'][number]>(table.columns);
  const safeRows = normalizeRows(rows, columns);
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-semibold text-white">{table.title ?? 'Таблица'}</p>
        <span className="text-xs text-slate-400">{safeRows.length} строк</span>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm text-slate-200">
          <thead className="bg-slate-900/60 text-xs uppercase tracking-wide text-slate-400">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.id}
                  className={`px-3 py-2 font-semibold ${resolveAlign(col.align)}`}
                  scope="col"
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {safeRows.length === 0 ? (
              <tr>
                <td colSpan={columns.length || 1} className="px-3 py-4 text-center text-slate-400">
                  Нет данных для отображения
                </td>
              </tr>
            ) : (
              safeRows.map((row, idx) => (
                <tr
                  key={idx}
                  className="border-b border-slate-800/60 last:border-b-0 hover:bg-slate-900/40"
                >
                  {columns.map((col) => (
                    <td key={col.id} className={`px-3 py-2 ${resolveAlign(col.align)}`}>
                      {String(row[col.id] ?? '—')}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
