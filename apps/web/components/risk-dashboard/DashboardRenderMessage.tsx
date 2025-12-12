'use client';

import { useEffect, useMemo } from 'react';
import { RiskCockpit } from './RiskCockpit';
import type { RiskDashboardSpec } from './types';
import { useRiskDashboard } from './DashboardContext';

type MessageRole = 'user' | 'assistant' | 'system';

type MinimalMessage = {
  id?: string;
  role: MessageRole;
  content?: unknown;
  generativeUI?: () => React.ReactNode;
};

export type RenderMessageProps = {
  message: MinimalMessage;
  messages?: MinimalMessage[];
  inProgress?: boolean;
  index?: number;
  isCurrentMessage?: boolean;
  onRegenerate?: (id?: string) => void;
  onCopy?: () => void;
};

type DashboardEnvelope = {
  type?: string;
  payload?: RiskDashboardSpec;
  dashboard?: RiskDashboardSpec;
  status?: 'success' | 'error' | 'partial';
  error?: string | null;
  text?: string;
};

type DashboardCapableMessage = MinimalMessage;

function parseDashboardEnvelope(content: unknown): DashboardEnvelope | null {
  if (typeof content !== 'string') return null;
  try {
    const parsed = JSON.parse(content) as DashboardEnvelope;
    if (parsed?.type === 'dashboard' || parsed?.payload || parsed?.dashboard) {
      return parsed;
    }
  } catch {
    // not a dashboard envelope — ignore
  }
  return null;
}

export function DashboardRenderMessage(props: RenderMessageProps) {
  const { message, index, onRegenerate, onCopy } = props;

  const { applyDashboard } = useRiskDashboard();
  const typedMessage = message as DashboardCapableMessage;
  const messageId = typedMessage.id ?? String(index);

  const envelope = useMemo(
    () => parseDashboardEnvelope(typedMessage.content),
    [typedMessage.content],
  );
  const dashboardPayload = envelope?.payload ?? envelope?.dashboard;

  useEffect(() => {
    if (!dashboardPayload) return;
    applyDashboard(messageId, dashboardPayload, {
      status: envelope?.status,
      text: envelope?.text,
      error: envelope?.error,
    });
  }, [applyDashboard, dashboardPayload, envelope?.error, envelope?.status, envelope?.text, messageId]);

  if (dashboardPayload) {
    const messageWithUI = {
      ...typedMessage,
      id: messageId,
      content: envelope?.text ?? 'Сформирован дашборд риска.',
      generativeUI: () => (
        <div className="mt-3 rounded-xl border border-slate-800 bg-slate-950/50 p-3">
          <RiskCockpit data={dashboardPayload} />
        </div>
      ),
    };

    return (
      <div
        key={index}
        className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 text-slate-100 shadow"
      >
        <p className="text-xs uppercase tracking-wide text-slate-400 mb-1">assistant</p>
        <p className="whitespace-pre-wrap text-sm">{messageWithUI.content}</p>
        {messageWithUI.generativeUI?.()}
      </div>
    );
  }

  switch (typedMessage.role) {
    case 'user':
      return (
        <div
          key={index}
          className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4 text-slate-100 shadow"
        >
          <p className="text-xs uppercase tracking-wide text-slate-400 mb-1">user</p>
          <p className="whitespace-pre-wrap text-sm">{String(typedMessage.content ?? '')}</p>
          {onCopy && (
            <button
              onClick={onCopy}
              className="mt-2 rounded border border-slate-700 px-2 py-1 text-xs text-slate-200 hover:border-slate-500"
            >
              Копировать
            </button>
          )}
        </div>
      );
    case 'assistant':
      return (
        <div
          key={index}
          className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 text-slate-100 shadow"
        >
          <p className="text-xs uppercase tracking-wide text-slate-400 mb-1">assistant</p>
          <p className="whitespace-pre-wrap text-sm">{String(typedMessage.content ?? '')}</p>
          {typedMessage.generativeUI?.()}
          {onRegenerate && (
            <button
              onClick={() => onRegenerate(messageId)}
              className="mt-2 rounded border border-slate-700 px-2 py-1 text-xs text-slate-200 hover:border-slate-500"
            >
              Перегенерировать
            </button>
          )}
        </div>
      );
    default:
      return null;
  }
}

