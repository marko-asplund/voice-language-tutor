function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(item => typeof item === 'string');
}
function validSession(value: Record<string, unknown>): boolean {
  if (typeof value.id !== 'string' || typeof value.state !== 'string' ||
      !Array.isArray(value.transcript) || typeof value.partial !== 'boolean') return false;
  if (!value.transcript.every(turn => record(turn) && typeof turn.turn_id === 'string' &&
      ['learner', 'tutor'].includes(String(turn.speaker)) && typeof turn.text === 'string')) return false;
  if (value.error !== null && (!record(value.error) || typeof value.error.code !== 'string' ||
      typeof value.error.message !== 'string' || typeof value.error.retryable !== 'boolean')) return false;
  if (value.review !== null) {
    const review = value.review;
    if (!record(review) || typeof review.summary !== 'string' || !Array.isArray(review.mistakes) ||
        !Array.isArray(review.new_vocabulary) || !strings(review.suggested_next_topics)) return false;
    if (!review.mistakes.every(item => record(item) &&
        ['turn_id', 'original', 'corrected', 'explanation', 'category'].every(key => typeof item[key] === 'string'))) return false;
    if (!review.new_vocabulary.every(item => record(item) &&
        ['turn_id', 'term', 'translation', 'example'].every(key => typeof item[key] === 'string') &&
        ['conversation', 'generated'].includes(String(item.example_kind)))) return false;
  }
  return true;
}

export async function api<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const timeout = AbortSignal.timeout(15000);
  const response = await fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    cache: 'no-store',
  });
  let data: unknown;
  try { data = await response.json(); }
  catch { throw new Error('The local server returned an unreadable response.'); }
  if (!response.ok) {
    throw new Error(record(data) && typeof data.message === 'string' ? data.message :
      response.status === 422 ? 'Check the setup fields.' : 'The local request failed.');
  }
  if (!record(data)) throw new Error('Malformed local server response.');
  if (path === '/health' && !['fake', 'live'].includes(String(data.mode))) {
    throw new Error('Malformed local server status.');
  }
  if (path.startsWith('/api/sessions') && !validSession(data)) {
    throw new Error('Malformed local session response.');
  }
  if (path === '/api/sessions' && (!['fake', 'live'].includes(String(data.mode)) ||
      !record(data.dynamic_variables) || (data.mode === 'live' && typeof data.signed_url !== 'string'))) {
    throw new Error('Malformed local connection descriptor.');
  }
  return data as T;
}
