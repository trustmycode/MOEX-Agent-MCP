'use client';

import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import type { RiskDashboardSpec } from './types';

type DashboardStatus = 'idle' | 'success' | 'error' | 'partial';

type DashboardState = {
  data: RiskDashboardSpec | null;
  lastMessageId: string | null;
  status: DashboardStatus;
  summary?: string | null;
  error?: string | null;
};

type DashboardMeta = {
  status?: DashboardStatus | RiskDashboardStatus;
  text?: string;
  error?: string | null;
};

type RiskDashboardStatus = 'success' | 'error' | 'partial';

type DashboardContextValue = {
  dashboard: RiskDashboardSpec | null;
  status: DashboardStatus;
  summary: string | null;
  error: string | null;
  applyDashboard: (messageId: string, payload: RiskDashboardSpec, meta?: DashboardMeta) => void;
  reset: () => void;
};

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function RiskDashboardProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<DashboardState>({
    data: null,
    lastMessageId: null,
    status: 'idle',
    summary: null,
    error: null,
  });

  const applyDashboard = useCallback(
    (messageId: string, payload: RiskDashboardSpec, meta?: DashboardMeta) => {
      setState((prev) => {
        if (prev.lastMessageId === messageId) return prev;
        const nextStatus = (meta?.status as DashboardStatus | undefined) ?? 'success';
        return {
          data: payload,
          lastMessageId: messageId,
          status: nextStatus as DashboardStatus,
          summary: meta?.text ?? prev.summary ?? null,
          error: meta?.error ?? null,
        };
      });
    },
    [],
  );

  const reset = useCallback(() => {
    setState({
      data: null,
      lastMessageId: null,
      status: 'idle',
      summary: null,
      error: null,
    });
  }, []);

  const value = useMemo<DashboardContextValue>(
    () => ({
      dashboard: state.data,
      status: state.status,
      summary: state.summary ?? null,
      error: state.error ?? null,
      applyDashboard,
      reset,
    }),
    [state, applyDashboard, reset],
  );

  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}

export function useRiskDashboard(): DashboardContextValue {
  const ctx = useContext(DashboardContext);
  if (!ctx) {
    throw new Error('useRiskDashboard must be used within RiskDashboardProvider');
  }
  return ctx;
}


