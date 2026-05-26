export const FORBIDDEN_TOKENS = [
  'answer_state',
  'answer_text',
  'sealed_answer_text',
  'raw_answer',
  'row_payload_json',
  'capture_dataset_row',
  'student_capture_source_dsn',
  'password',
  'dsn',
  'traceback',
  'select *',
];

export function findForbiddenTokens(value: string): string[] {
  const haystack = value.toLowerCase();
  return FORBIDDEN_TOKENS.filter((token) => haystack.includes(token));
}

export function assertNoForbiddenTokens(value: string, contextLabel: string): void {
  const hits = findForbiddenTokens(value);
  if (hits.length > 0) {
    throw new Error(`${contextLabel} contains forbidden tokens: ${hits.join(', ')}`);
  }
}
