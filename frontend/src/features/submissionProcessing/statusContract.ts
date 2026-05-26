import { ProcessingOverallStatus } from './types';

export const PROCESSING_OVERALL_STATUSES: ProcessingOverallStatus[] = [
  'NOT_FOUND',
  'DRAFT_OR_UNSEALED',
  'SEALED',
  'WAITING_CAPTURE',
  'CAPTURING',
  'CAPTURE_FAILED',
  'WAITING_GRADING',
  'GRADING',
  'GRADING_FAILED',
  'COMPLETED',
  'NEEDS_REVIEW',
];

export const ACTIVE_PROCESSING_STATUSES: ProcessingOverallStatus[] = [
  'DRAFT_OR_UNSEALED',
  'SEALED',
  'WAITING_CAPTURE',
  'CAPTURING',
  'WAITING_GRADING',
  'GRADING',
];

export const TERMINAL_PROCESSING_STATUSES: ProcessingOverallStatus[] = [
  'NOT_FOUND',
  'CAPTURE_FAILED',
  'GRADING_FAILED',
  'COMPLETED',
  'NEEDS_REVIEW',
];

const STATUS_SET = new Set<string>(PROCESSING_OVERALL_STATUSES);

export function isProcessingOverallStatus(value: unknown): value is ProcessingOverallStatus {
  return typeof value === 'string' && STATUS_SET.has(value);
}
