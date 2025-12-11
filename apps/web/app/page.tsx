"use client";

import { useMemo } from "react";
import { useCopilotReadable } from "@copilotkit/react-core";
import { CopilotSidebar } from "@copilotkit/react-ui";
import { DashboardRenderMessage } from "@/components/risk-dashboard/DashboardRenderMessage";
import { RiskCockpit } from "@/components/risk-dashboard/RiskCockpit";
import { RiskDashboardProvider, useRiskDashboard } from "@/components/risk-dashboard/DashboardContext";

function CanvasPanel() {
  const { dashboard, status, summary, error } = useRiskDashboard();

  const metaChips = useMemo(() => {
    if (!dashboard) return null;
    return (
      <div className="flex flex-wrap gap-2 text-xs">
        <span className="rounded-full bg-slate-800 px-3 py-1 text-slate-200">
          Сценарий: {dashboard.metadata.scenario_type ?? "—"}
        </span>
        {dashboard.metadata.portfolio_id && (
          <span className="rounded-full bg-slate-800 px-3 py-1 text-slate-200">
            Портфель: {dashboard.metadata.portfolio_id}
          </span>
        )}
        {status !== "idle" && (
          <span className="rounded-full bg-slate-800 px-3 py-1 text-slate-200">
            Статус: {status}
          </span>
        )}
      </div>
    );
  }, [dashboard, status]);

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 shadow-xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-white">Canvas · Risk Dashboard</h2>
          <p className="text-slate-300">
            Здесь автоматом рисуется RiskCockpit, когда агент вернул <code>output.dashboard</code>.
            Попробуйте: «Оцени риск портфеля SBER 100%».
          </p>
        </div>
        <span className="rounded-full bg-emerald-500/20 px-3 py-1 text-xs font-medium text-emerald-200">
          Generative UI
        </span>
      </div>

      <div className="mt-4 space-y-3">
        {metaChips}
        {error && (
          <div className="rounded-xl border border-rose-800/80 bg-rose-900/40 p-3 text-sm text-rose-100">
            Ошибка агента: {error}
          </div>
        )}
        {dashboard ? (
          <RiskCockpit data={dashboard} />
        ) : (
          <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4 text-slate-300">
            Данные ещё не загружены. Отправьте запрос в чат справа, агент вернёт RiskDashboardSpec,
            и Canvas перерисуется без ручных кликов.
          </div>
        )}
        {summary && (
          <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3 text-sm text-slate-200">
            Ответ агента: {summary}
          </div>
        )}
      </div>
    </section>
  );
}

function HomeContent() {
  const { dashboard, status } = useRiskDashboard();

  useCopilotReadable({
    description: "Состояние Canvas Risk Dashboard",
    value: {
      status,
      hasDashboard: Boolean(dashboard),
      scenario: dashboard?.metadata.scenario_type ?? null,
      portfolio: dashboard?.metadata.portfolio_id ?? null,
    },
  });

  return (
    <main className="min-h-screen p-6 lg:p-10">
      <div className="mb-6 flex flex-col gap-2">
        <p className="text-sm text-slate-300 uppercase tracking-[0.2em]">
          Agentic UI · CopilotKit
        </p>
        <h1 className="text-3xl font-semibold text-white lg:text-4xl">Risk Dashboard Canvas</h1>
        <p className="text-slate-300 max-w-3xl">
          Левый Canvas — динамический RiskCockpit. Чат справа — CopilotKit, который общается с
          Orchestrator Agent и отправляет дашборд в рендер-цикл Generative UI.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <CanvasPanel />

        <aside className="relative h-full">
          <div className="sticky top-6 rounded-2xl border border-slate-800 bg-slate-950/70 p-2 shadow-2xl">
            <CopilotSidebar
              defaultOpen
              RenderMessage={DashboardRenderMessage}
              labels={{
                title: "Чат с агентом",
                placeholder: "Например: оцени риск портфеля SBER/GAZP/LKOH",
                initial: "Спроси про risk dashboard или liquidity report.",
              }}
            >
              <div className="p-4 text-sm text-slate-300">
                Чатовая панель CopilotKit должна быть видна справа. Если она скрыта,
                нажмите на кнопку открытия внизу экрана.
              </div>
            </CopilotSidebar>
          </div>
        </aside>
      </div>
    </main>
  );
}

export default function Home() {
  return (
    <RiskDashboardProvider>
      <HomeContent />
    </RiskDashboardProvider>
  );
}
