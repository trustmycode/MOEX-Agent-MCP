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

type AgentServiceResponse = {
  output?: { text?: string; error_message?: string };
  text?: string;
  error_message?: string;
};

const runtime = new CopilotRuntime();

class AgentServiceAdapter implements CopilotServiceAdapter {
  name = "AgentServiceAdapter";
  provider = "agent-service";
  model = "a2a-orchestrator";

  async process(
    request: CopilotRuntimeChatCompletionRequest,
  ): Promise<CopilotRuntimeChatCompletionResponse> {
    const threadId = request.threadId ?? randomUUID();
    const agentText = await this.forwardToAgent(request).catch((error) => {
      console.error("[agent-service] forwarding failed", error);
      const lastUser =
        request.messages.findLast((m) => m.role === "user")?.content?.toString() ?? "";
      return (
        "Пока возвращаю заглушку: не удалось связаться с orchestrator-agent. " +
        `Ваш запрос: "${lastUser || "нет текста"}".`
      );
    });

    await request.eventSource.stream(async (stream$) => {
      const messageId = randomUUID();
      stream$.sendTextMessageStart({ messageId });
      stream$.sendTextMessageContent({ messageId, content: agentText });
      stream$.sendTextMessageEnd({ messageId });
      stream$.complete();
    });

    return { threadId };
  }

  private async forwardToAgent(request: CopilotRuntimeChatCompletionRequest): Promise<string> {
    const agentUrl = process.env.AGENT_SERVICE_URL || "http://localhost:8100/a2a";
    const locale =
      (request.forwardedParameters as Record<string, string> | undefined)?.locale ?? "ru";
    const userRole =
      (request.forwardedParameters as Record<string, string> | undefined)?.user_role ?? "analyst";
    const sessionId = request.threadId ?? randomUUID();

    const payload: AgentServicePayload = {
      messages: request.messages.map((message) => ({
        role: message.role,
        content: typeof message.content === "string" ? message.content : JSON.stringify(message),
      })),
      locale,
      user_role: userRole,
      session_id: sessionId,
      metadata: request.forwardedParameters ?? {},
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
    const text = data?.output?.text || data?.text;

    if (!text) {
      throw new Error("Agent service returned empty response");
    }

    return text;
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
