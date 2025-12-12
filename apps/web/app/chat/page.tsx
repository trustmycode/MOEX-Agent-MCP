"use client";

import type React from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Ajv from "ajv";
import addFormats from "ajv-formats";
import { DashboardRenderer } from "@/components/risk-dashboard/DashboardRenderer";
import { RiskDashboardProvider, useRiskDashboard } from "@/components/risk-dashboard/DashboardContext";
import { DashboardRenderMessage } from "@/components/risk-dashboard/DashboardRenderMessage";
import type { RiskDashboardSpec } from "@/components/risk-dashboard/types";
import dashboardSchema from "@/schemas/risk-dashboard.schema.json";

type ChatMessage = {
  id?: string;
  role: "user" | "assistant" | "system";
  content?: unknown;
  done?: boolean;
  error?: boolean;
  generativeUI?: () => React.ReactNode;
};

type AguiEnvelope = {
  type: string;
  [key: string]: unknown;
};

function parseSseChunk(chunk: string): { event: string; data: AguiEnvelope } | null {
  const lines = chunk.split("\n");
  let eventName = "message";
  const dataLines: string[] = [];

  lines.forEach((line) => {
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5));
    }
  });

  const data = dataLines.join("\n");
  if (!data.trim()) return null;
  try {
    return { event: eventName, data: JSON.parse(data) as AguiEnvelope };
  } catch {
    return null;
  }
}

function ChatPageInner() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [schemaErrors, setSchemaErrors] = useState<string[]>([]);
  const [runStatus, setRunStatus] = useState<"idle" | "running" | "finished" | "error">(
    "idle",
  );
  const [error, setError] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string>("");
  const threadIdRef = useRef<string>("");

  useEffect(() => {
    if (!threadIdRef.current) {
      const nextId = crypto.randomUUID();
      threadIdRef.current = nextId;
      setThreadId(nextId);
    }
  }, []);

  const ensureThreadId = useCallback(() => {
    if (!threadIdRef.current) {
      const nextId = crypto.randomUUID();
      threadIdRef.current = nextId;
      setThreadId(nextId);
    }
    return threadIdRef.current;
  }, []);

  const ajv = useMemo(() => {
    const instance = new Ajv({ allErrors: true, strict: false });
    addFormats(instance);
    return instance;
  }, []);
  const validateDashboard = useMemo(() => ajv.compile(dashboardSchema as object), [ajv]);
  const { dashboard, applyDashboard, reset } = useRiskDashboard();

  const upsertAssistantMessage = useCallback((messageId: string, updater: (text: string) => string) => {
    setMessages((prev) => {
      const existingIdx = prev.findIndex((m) => m.id === messageId && m.role === "assistant");
      if (existingIdx === -1) {
        return [
          ...prev,
          { id: messageId, role: "assistant", content: updater(""), done: false },
        ];
      }
      const next = [...prev];
      const current = next[existingIdx];
      const currentText = typeof current.content === "string" ? current.content : "";
      next[existingIdx] = { ...current, content: updater(currentText) };
      return next;
    });
  }, []);

  const markDone = useCallback((messageId: string) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === messageId ? { ...m, done: true } : m)),
    );
  }, []);

  const handleAguiEvent = useCallback(
    (eventName: string, payload: AguiEnvelope) => {
      switch (eventName) {
        case "RUN_STARTED":
          setRunStatus("running");
          setError(null);
          setSchemaErrors([]);
          reset();
          break;
        case "TEXT_MESSAGE_START": {
          const messageId = String(payload.messageId ?? crypto.randomUUID());
          upsertAssistantMessage(messageId, () => "");
          break;
        }
        case "TEXT_MESSAGE_CONTENT": {
          const messageId = String(payload.messageId ?? "assistant");
          const content = String((payload as { delta?: unknown }).delta ?? "");
          const normalizedContent = content.replace(/\u202f|\u00a0/g, " ");
          upsertAssistantMessage(messageId, (prev) => prev + normalizedContent);
          break;
        }
        case "TEXT_MESSAGE_END": {
          const messageId = String(payload.messageId ?? "assistant");
          markDone(messageId);
          break;
        }
        case "STATE_SNAPSHOT": {
          const snapshot = (payload as { snapshot?: Record<string, unknown> }).snapshot ?? {};
          const snapshotDashboard = snapshot.dashboard as RiskDashboardSpec | undefined;
          const schemaValid = snapshot.schema_valid as boolean | undefined;
          const schemaErrs = (snapshot.schema_errors as string[]) ?? [];

          if (snapshotDashboard) {
            const dashMessageId =
              (payload.runId as string) ||
              (payload.run_id as string) ||
              (snapshotDashboard.metadata?.portfolio_id as string) ||
              crypto.randomUUID();

            // Лёгкая диагностика
            console.debug("STATE_SNAPSHOT dashboard received", {
              runId: payload.runId || payload.run_id,
              portfolio: snapshotDashboard.metadata?.portfolio_id,
            });

            let validationOk = true;
            let errors: string[] = [];

            if (schemaValid === false) {
              validationOk = false;
              errors = schemaErrs;
            } else if (schemaValid === true) {
              validationOk = true;
            } else if (!validateDashboard(snapshotDashboard)) {
              validationOk = false;
              errors =
                validateDashboard.errors?.map((e) => e.message || "")?.filter(Boolean) ?? [];
            }

            setSchemaErrors(validationOk ? [] : errors);

            const status = ["success", "error", "partial"].includes(
              (snapshot.status as string) ?? "",
            )
              ? (snapshot.status as "success" | "error" | "partial")
              : "success";

            // Идемпотентно применяем дашборд в контекст
            applyDashboard(dashMessageId, snapshotDashboard, {
              status,
              text: (snapshot.text as string | undefined) ?? undefined,
              error: (snapshot.error as string | undefined) ?? null,
            });
          }
          break;
        }
        case "RUN_FINISHED":
          setRunStatus("finished");
          break;
        case "RUN_ERROR":
          setRunStatus("error");
          setError(String(payload.message ?? "Неизвестная ошибка"));
          break;
        default:
          break;
      }
    },
    [applyDashboard, markDone, reset, upsertAssistantMessage, validateDashboard],
  );

  const streamRun = useCallback(
    async (body: object) => {
      setRunStatus("running");
      setError(null);
      setSchemaErrors([]);

      const response = await fetch("/api/agui", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        setRunStatus("error");
        setError(`HTTP ${response.status}`);
        return;
      }
      if (!response.body) {
        setRunStatus("error");
        setError("Пустой ответ от сервера");
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (value) {
          buffer += decoder.decode(value, { stream: true });
          const chunks = buffer.split("\n\n");
          buffer = chunks.pop() ?? "";
          for (const chunk of chunks) {
            const parsed = parseSseChunk(chunk.trim());
            if (parsed) {
              handleAguiEvent(parsed.event, parsed.data);
            }
          }
        }
        if (done) {
          if (buffer.trim()) {
            const parsed = parseSseChunk(buffer.trim());
            if (parsed) {
              handleAguiEvent(parsed.event, parsed.data);
            }
          }
          break;
        }
      }
    },
    [handleAguiEvent],
  );

  const handleSend = useCallback(
    async (e?: React.FormEvent) => {
      e?.preventDefault();
      if (!input.trim()) return;
      const currentThreadId = ensureThreadId();

      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: input.trim(),
        done: true,
      };
      setMessages((prev) => [...prev, userMessage]);

      const runId = crypto.randomUUID();
      const body = {
        threadId: currentThreadId,
        runId,
        messages: [{ role: "user", content: input.trim() }],
        state: {},
        tools: [],
        context: [],
      };

      setInput("");
      setSchemaErrors([]);
      reset();
      await streamRun(body);
    },
    [ensureThreadId, input, reset, streamRun],
  );

  const handleTextareaKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        void handleSend();
      }
    },
    [handleSend],
  );

  return (
    <main className="min-h-screen bg-background p-6 lg:p-10">
      <div className="mb-6 space-y-2">
        <p className="text-sm uppercase tracking-[0.2em] text-slate-400">AG-UI · MOEX Risk</p>
        <h1 className="text-3xl font-semibold text-white lg:text-4xl">Чат с агентом и риск-дашборд</h1>
        <p className="max-w-3xl text-slate-300">
          Формулируйте запросы по портфельному риску и аналитике MOEX. Агент отвечает по SSE: текстовые сообщения приходят в чат, а структурированные STATE_SNAPSHOT рендерят дашборд ниже.
        </p>
      </div>

      <div className="grid gap-6">
        <section className="flex min-h-[70vh] flex-col rounded-2xl border border-slate-800 bg-slate-950/70 p-4 shadow-xl">
          <div className="mb-4 flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-sm font-semibold text-white">Чат</p>
              <p className="text-xs text-slate-400">Статус: {runStatus}</p>
            </div>
            {error && (
              <span className="rounded-full bg-rose-900/40 px-3 py-1 text-xs text-rose-100">
                {error}
              </span>
            )}
          </div>

          <form
            onSubmit={handleSend}
            className="mb-4 flex flex-col gap-3 rounded-xl border border-slate-800/80 bg-slate-900/60 p-3"
          >
            <textarea
              className="min-h-[90px] w-full rounded-xl border border-slate-700 bg-slate-900/70 p-3 text-sm text-white outline-none focus:border-emerald-500"
              placeholder="Например: «оцени риск портфеля SBER 40%, GAZP 30%, LKOH 30%» или «собери дашборд по stress-test»"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={runStatus === "running"}
              onKeyDown={handleTextareaKeyDown}
            />
            <div className="flex items-center justify-between">
              <p className="text-xs text-slate-400">Thread ID: {threadId || "—"}</p>
              <button
                type="submit"
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-emerald-500 disabled:opacity-60"
                disabled={runStatus === "running"}
              >
                Отправить
              </button>
            </div>
          </form>

          <div className="flex flex-1 flex-col space-y-3 overflow-y-auto pr-1 justify-end">
            {messages.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-800 bg-slate-900/30 p-4 text-sm text-slate-400">
                История пуста. Спросите: «оцени риск портфеля SBER/GAZP/LKOH» или «построй stress-сценарии».
              </div>
            ) : (
              messages.map((msg, idx) => (
                <DashboardRenderMessage
                  // eslint-disable-next-line react/no-array-index-key
                  key={msg.id ?? idx}
                  message={msg}
                  index={idx}
                  isCurrentMessage={idx === messages.length - 1}
                />
              ))
            )}
          </div>
        </section>

        <section className="flex min-h-[70vh] flex-col rounded-2xl border border-slate-800 bg-slate-950/70 p-4 shadow-xl">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-sm font-semibold text-white">Risk Dashboard</p>
            {schemaErrors.length > 0 && (
              <span className="rounded-full bg-amber-900/50 px-3 py-1 text-xs text-amber-100">
                Schema errors: {schemaErrors.length}
              </span>
            )}
          </div>
          <div className="flex-1">
            {dashboard ? (
              <DashboardRenderer spec={dashboard} validationErrors={schemaErrors} />
            ) : (
              <div className="rounded-xl border border-dashed border-slate-800 bg-slate-900/30 p-4 text-sm text-slate-400">
                Дашборд пока не получен. Отправьте запрос — агент пришлёт STATE_SNAPSHOT и layout для рендера.
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}

export default function ChatPage() {
  return (
    <RiskDashboardProvider>
      <ChatPageInner />
    </RiskDashboardProvider>
  );
}

