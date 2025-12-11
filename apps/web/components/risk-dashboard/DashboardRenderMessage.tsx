'use client';

import {
  AssistantMessage as DefaultAssistantMessage,
  ImageRenderer as DefaultImageRenderer,
  UserMessage as DefaultUserMessage,
} from '@copilotkit/react-ui';
import type { RenderMessageProps } from '@copilotkit/react-ui';
import type { AIMessage, Message, UserMessage as UserMessageType } from '@copilotkit/shared';
import { useEffect, useMemo } from 'react';
import { RiskCockpit } from './RiskCockpit';
import type { RiskDashboardSpec } from './types';
import { useRiskDashboard } from './DashboardContext';

type DashboardEnvelope = {
  type?: string;
  payload?: RiskDashboardSpec;
  dashboard?: RiskDashboardSpec;
  status?: 'success' | 'error' | 'partial';
  error?: string | null;
  text?: string;
};

type DashboardCapableMessage = Message & {
  id?: string;
  content?: unknown;
  generativeUI?: () => React.ReactNode;
};

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
  const {
    message,
    messages,
    inProgress,
    index,
    isCurrentMessage,
    onRegenerate,
    onCopy,
    onThumbsUp,
    onThumbsDown,
    messageFeedback,
    markdownTagRenderers,
    AssistantMessage = DefaultAssistantMessage,
    UserMessage = DefaultUserMessage,
    ImageRenderer = DefaultImageRenderer,
  } = props;

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
      <AssistantMessage
        key={index}
        data-message-role="assistant"
        subComponent={messageWithUI.generativeUI?.()}
        rawData={messageWithUI}
        message={messageWithUI as AIMessage}
        messages={messages}
        isLoading={inProgress && isCurrentMessage && !typedMessage.content}
        isGenerating={inProgress && isCurrentMessage && !!typedMessage.content}
        isCurrentMessage={isCurrentMessage}
        onRegenerate={() => onRegenerate?.(messageId)}
        onCopy={onCopy}
        onThumbsUp={onThumbsUp}
        onThumbsDown={onThumbsDown}
        feedback={messageFeedback?.[messageId] || null}
        markdownTagRenderers={markdownTagRenderers}
        ImageRenderer={ImageRenderer}
      />
    );
  }

  switch (typedMessage.role) {
    case 'user':
      return (
        <UserMessage
          key={index}
          rawData={typedMessage}
          data-message-role="user"
          message={typedMessage as UserMessageType}
          ImageRenderer={ImageRenderer}
        />
      );
    case 'assistant':
      return (
        <AssistantMessage
          key={index}
          data-message-role="assistant"
          subComponent={typedMessage.generativeUI?.()}
          rawData={typedMessage}
          message={typedMessage as AIMessage}
          messages={messages}
          isLoading={inProgress && isCurrentMessage && !typedMessage.content}
          isGenerating={inProgress && isCurrentMessage && !!typedMessage.content}
          isCurrentMessage={isCurrentMessage}
          onRegenerate={() => onRegenerate?.(messageId)}
          onCopy={onCopy}
          onThumbsUp={onThumbsUp}
          onThumbsDown={onThumbsDown}
          feedback={messageFeedback?.[messageId] || null}
          markdownTagRenderers={markdownTagRenderers}
          ImageRenderer={ImageRenderer}
        />
      );
    default:
      return null;
  }
}
