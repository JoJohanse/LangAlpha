import type { NavigateFunction } from 'react-router-dom';
import { getFlashWorkspace } from '@/pages/ChatAgent/utils/api';

export interface AskAIResponsePayload {
  thread_initial_message?: string;
  fallback_message?: string;
  additional_context?: Record<string, unknown>[] | null;
}

interface LaunchAskAIChatOptions {
  navigate: NavigateFunction;
  payload: AskAIResponsePayload;
  fallbackMessage: string;
}

function normalizeAdditionalContext(
  value: Record<string, unknown>[] | null | undefined,
): Record<string, unknown>[] | null {
  if (!Array.isArray(value) || value.length === 0) return null;
  const allowed = new Set(['skills', 'image', 'pdf', 'file', 'directive']);
  const normalized = value
    .map((ctx) => {
      const type = String(ctx?.type || '').trim();
      if (!allowed.has(type)) {
        return null;
      }
      return ctx;
    })
    .filter((ctx): ctx is Record<string, unknown> => !!ctx);
  return normalized.length ? normalized : null;
}

export async function launchAskAIChat({
  navigate,
  payload,
  fallbackMessage,
}: LaunchAskAIChatOptions): Promise<void> {
  const flashWs = await getFlashWorkspace() as { workspace_id: string };
  navigate('/chat/t/__default__', {
    state: {
      workspaceId: flashWs.workspace_id,
      initialMessage: payload.thread_initial_message || payload.fallback_message || fallbackMessage,
      additionalContext: normalizeAdditionalContext(payload.additional_context),
      agentMode: 'flash',
      workspaceStatus: 'flash',
      planMode: false,
    },
  });
}
