'use client';

import type { RiskDashboardDataRow, TableSpec } from '../types';

type Props = {
  table: TableSpec;
  rows: RiskDashboardDataRow[];
};

const alignClass: Record<NonNullable<TableSpec['columns'][number]['align']>, string> = {
  left: 'text-left',
  right: 'text-right',
  center: 'text-center',
};

function resolveAlign(align?: TableSpec['columns'][number]['align']) {
  return align ? alignClass[align] : 'text-left';
}

export function RiskTable({ table, rows }: Props) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-semibold text-white">{table.title ?? 'Таблица'}</p>
        <span className="text-xs text-slate-400">{rows.length} строк</span>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm text-slate-200">
          <thead className="bg-slate-900/60 text-xs uppercase tracking-wide text-slate-400">
            <tr>
              {table.columns.map((col) => (
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
            {rows.length === 0 ? (
              <tr>
                <td colSpan={table.columns.length} className="px-3 py-4 text-center text-slate-400">
                  Нет данных для отображения
                </td>
              </tr>
            ) : (
              rows.map((row, idx) => (
                <tr
                  key={idx}
                  className="border-b border-slate-800/60 last:border-b-0 hover:bg-slate-900/40"
                >
                  {table.columns.map((col) => (
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
