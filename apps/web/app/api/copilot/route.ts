import { randomUUID } from "crypto";
import {
  CopilotRuntime,
  copilotRuntimeNextJSAppRouterEndpoint,
  type CopilotRuntimeChatCompletionRequest,
  type CopilotRuntimeChatCompletionResponse,
  type CopilotServiceAdapter,
} from "@copilotkit/runtime";

type AgentServicePayload = {
  messages: { role: string; content: string }[];
  locale: string;
  user_role?: string;
  session_id?: string;
  metadata?: Record<string, unknown>;
};

type A2AOutput = {
  status?: "success" | "error" | "partial";
  text?: string;
  dashboard?: unknown;
  tables?: unknown;
  error_message?: string;
};

type AgentServiceResponse = {
  status?: "success" | "error" | "partial";
  output?: A2AOutput;
  text?: string;
  error_message?: string;
};

type RequestMessage = { role?: string; content?: unknown };

type NormalizedOutput = {
  status?: "success" | "error" | "partial";
  text?: string;
  dashboard?: unknown;
  error_message?: string;
};

const runtime = new CopilotRuntime({
  // Весь вызов уходит в кастомный serviceAdapter, без встроенных LLM провайдеров.
  delegateAgentProcessingToServiceAdapter: true,
});

class AgentServiceAdapter implements CopilotServiceAdapter {
  name = "AgentServiceAdapter";
  // Фактическая работа делегирована кастомному сервису; встроенный провайдер не нужен.
  provider = "empty";
  model = "noop";

  async process(
    request: CopilotRuntimeChatCompletionRequest,
  ): Promise<CopilotRuntimeChatCompletionResponse> {
    const threadId = request.threadId ?? randomUUID();
    const agentOutput = await this.forwardToAgent(request).catch((error) => {
      console.error("[agent-service] forwarding failed", error);
      const lastUserMessage = request.messages
        .slice()
        .reverse()
        .find((m) => (m as RequestMessage).role === "user") as RequestMessage | undefined;
      const lastUserContent =
        typeof lastUserMessage?.content === "string"
          ? lastUserMessage.content
          : JSON.stringify(lastUserMessage?.content ?? "");
      const fallbackText =
        "Пока возвращаю заглушку: не удалось связаться с orchestrator-agent. " +
        `Ваш запрос: "${lastUserContent || "нет текста"}".`;
      return {
        status: "error" as const,
        text: fallbackText,
        output: { status: "error" as const, text: fallbackText },
        error_message: error instanceof Error ? error.message : String(error),
      };
    });

    const asOutput =
      agentOutput.output && typeof agentOutput.output === "object"
        ? (agentOutput.output as A2AOutput)
        : undefined;

    const normalized: NormalizedOutput = {
      status: agentOutput.status ?? asOutput?.status,
      text: agentOutput.text ?? asOutput?.text,
      dashboard: asOutput?.dashboard,
      error_message: agentOutput.error_message ?? asOutput?.error_message,
    };

    const textContent =
      normalized.text || normalized.error_message || "Агент не вернул текстовый ответ.";
    const dashboardPayload = normalized.dashboard;
    const errorMessage = normalized.error_message;
    const status = normalized.status || (errorMessage ? "error" : "success");

    await request.eventSource.stream(async (stream$) => {
      const messageId = randomUUID();
      stream$.sendTextMessageStart({ messageId });
      stream$.sendTextMessageContent({ messageId, content: textContent });
      stream$.sendTextMessageEnd({ messageId });

      if (dashboardPayload) {
        const dashboardMessageId = randomUUID();
        const envelope = JSON.stringify({
          type: "dashboard",
          payload: dashboardPayload,
          status,
          error: errorMessage,
          text: textContent,
        });
        stream$.sendTextMessageStart({ messageId: dashboardMessageId, parentMessageId: messageId });
        stream$.sendTextMessageContent({ messageId: dashboardMessageId, content: envelope });
        stream$.sendTextMessageEnd({ messageId: dashboardMessageId });
      }

      stream$.complete();
    });

    return { threadId };
  }

  private async forwardToAgent(request: CopilotRuntimeChatCompletionRequest): Promise<AgentServiceResponse> {
    const agentUrl = process.env.AGENT_SERVICE_URL || "http://localhost:8100/a2a";
    const locale =
      (request.forwardedParameters as Record<string, string> | undefined)?.locale ?? "ru";
    const userRole =
      (request.forwardedParameters as Record<string, string> | undefined)?.user_role ?? "analyst";
    const sessionId = request.threadId ?? randomUUID();

    const payload: AgentServicePayload = {
      messages: request.messages.map((message) => {
        const msg = message as RequestMessage;
        return {
          role: msg.role ?? "user",
          content: typeof msg.content === "string" ? msg.content : JSON.stringify(msg),
        };
      }),
      locale,
      user_role: userRole,
      session_id: sessionId,
      metadata: (request.forwardedParameters as Record<string, unknown> | undefined) ?? {},
    };

    const response = await fetch(agentUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Agent service responded with ${response.status}`);
    }

    const data = (await response.json()) as AgentServiceResponse;
    return data;
  }
}

const agentServiceAdapter = new AgentServiceAdapter();

const handler = copilotRuntimeNextJSAppRouterEndpoint({
  runtime,
  endpoint: "/api/copilot",
  serviceAdapter: agentServiceAdapter,
  logLevel: "error",
});

export const POST = handler.handleRequest;
export const GET = handler.handleRequest;
