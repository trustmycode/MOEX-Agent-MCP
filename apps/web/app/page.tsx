"use client";

import { CopilotSidebar } from "@copilotkit/react-ui";

export default function Home() {
  return (
    <main className="min-h-screen p-6 lg:p-10">
      <div className="mb-6 flex flex-col gap-2">
        <p className="text-sm text-slate-300 uppercase tracking-[0.2em]">
          Agentic UI · CopilotKit
        </p>
        <h1 className="text-3xl font-semibold text-white lg:text-4xl">
          Risk Dashboard Canvas
        </h1>
        <p className="text-slate-300 max-w-3xl">
          Левая зона — будущий Canvas для визуализаций (Risk Dashboard, портфельные метрики,
          стресс-сценарии). Справа — чат CopilotKit, который проксирует запросы в
          Orchestrator Agent.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <section className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 shadow-xl">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-xl font-semibold text-white">Canvas (заглушка)</h2>
              <p className="text-slate-300">
                Здесь появятся графики и таблицы сценариев 5 / 7 / 9. Пока оставляем placeholder
                под будущие виджеты.
              </p>
            </div>
            <span className="rounded-full bg-emerald-500/20 px-3 py-1 text-xs font-medium text-emerald-200">
              v0 foundation
            </span>
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
              <p className="text-sm text-slate-400">Следующий шаг</p>
              <p className="text-white font-medium">
                Подключить рендеринг RiskDashboardSpec из агента.
              </p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-4">
              <p className="text-sm text-slate-400">API</p>
              <p className="text-white font-medium">
                /api/copilot → агент `/a2a` (fallback: mock-ответ).
              </p>
            </div>
          </div>
        </section>

        <aside className="relative h-full">
          <div className="sticky top-6 rounded-2xl border border-slate-800 bg-slate-950/70 p-2 shadow-2xl">
            <CopilotSidebar
              defaultOpen
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
