import { apiBaseUrl } from './env';

export type ProcessingStatusEnvelope = {
  ok?: boolean;
  data?: {
    overall_status?: string;
    is_terminal?: boolean;
    score?: {
      total_score?: number | null;
      max_score?: number | null;
    };
  };
  error?: {
    code?: string;
    message?: string;
  };
};

export async function getProcessingStatusByApi(
  submissionId: number,
  cookieHeader?: string,
): Promise<{ status: number; payload: ProcessingStatusEnvelope | null }> {
  const response = await fetch(`${apiBaseUrl()}/api/v1/submissions/${submissionId}/processing-status`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
      ...(cookieHeader ? { Cookie: cookieHeader } : {}),
    },
  });

  let payload: ProcessingStatusEnvelope | null = null;
  try {
    payload = (await response.json()) as ProcessingStatusEnvelope;
  } catch {
    payload = null;
  }

  return {
    status: response.status,
    payload,
  };
}
