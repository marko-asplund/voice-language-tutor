import { createSignal, onCleanup, Show } from 'solid-js';
import { api } from './api';
import { Voice } from './voice';
import type { Connection, Session, Setup, Turn } from './types';
import SetupForm from './components/SetupForm';
import Transcript from './components/Transcript';
import ReviewPanel from './components/ReviewPanel';
import ConversationControls from './components/ConversationControls';

export default function App() {
  const [setup, setSetup] = createSignal<Setup>({
    target_language: 'English', native_language: 'Spanish', level: 'B1', topic: 'Travel', student_name: '',
  });
  const [mode, setMode] = createSignal('Loading');
  const [session, setSession] = createSignal<Session | null>(null);
  const [turns, setTurns] = createSignal<Turn[]>([]);
  const [active, setActive] = createSignal(false);
  const [busy, setBusy] = createSignal(false);
  const [muted, setMuted] = createSignal(false);
  const [status, setStatus] = createSignal('Ready');
  const [error, setError] = createSignal('');
  const [elapsed, setElapsed] = createSignal(0);
  const [endPending, setEndPending] = createSignal(false);
  const [pollFailed, setPollFailed] = createSignal(false);
  const voice = new Voice();
  let generation = 0;
  let lostDuringStart = false;
  let timer: ReturnType<typeof setInterval> | undefined;
  let pollTimer: ReturnType<typeof setTimeout> | undefined;
  let abort = new AbortController();
  let disposed = false;
  const reviewing = () => ['transcript_pending', 'reviewing'].includes(session()?.state ?? '');
  const message = (exc: unknown, fallback: string) => exc instanceof Error ? exc.message : fallback;

  void api<{ mode: string }>('/health', undefined, abort.signal)
    .then(value => { if (!disposed) setMode(value.mode); })
    .catch(() => { if (!disposed) setError('Start the local server and reload.'); });

  function stopTimers() {
    if (timer) clearInterval(timer);
    if (pollTimer) clearTimeout(pollTimer);
    timer = undefined;
    pollTimer = undefined;
  }

  async function poll(id: string, epoch: number, deadline: number) {
    setPollFailed(false);
    try {
      const next = await api<Session>(`/api/sessions/${id}`, undefined, abort.signal);
      if (disposed || epoch !== generation) return;
      setSession(next);
      setStatus(next.state);
      if (next.transcript.length) setTurns(next.transcript);
      if (next.state === 'reviewed' || next.state === 'failed') return;
      if (Date.now() > deadline) throw new Error('Review status timed out. Check the local server.');
      pollTimer = setTimeout(() => void poll(id, epoch, deadline), 1000);
    } catch (exc) {
      if (!disposed && epoch === generation && !abort.signal.aborted) {
        setError(message(exc, 'Review status unavailable.'));
        setPollFailed(true);
      }
    }
  }

  async function end(partial = false) {
    if (busy() || (!active() && !endPending())) return;
    setBusy(true);
    setActive(false);
    setEndPending(true);
    stopTimers();
    try {
      await voice.end();
      const current = session();
      if (current) {
        const next = await api<Session>(`/api/sessions/${current.id}/end`, { partial }, abort.signal);
        if (disposed) return;
        setSession(next);
        setEndPending(false);
        void poll(current.id, generation, Date.now() + 310000);
      }
    } catch (exc) {
      if (!disposed) setError(message(exc, 'Unable to end the session.'));
    } finally {
      if (!disposed) { setBusy(false); setMuted(false); }
    }
  }

  async function start() {
    if (busy() || active() || endPending() || reviewing()) return;
    setBusy(true);
    lostDuringStart = false;
    setError('');
    setPollFailed(false);
    setTurns([]);
    setSession(null);
    setElapsed(0);
    stopTimers();
    abort.abort();
    abort = new AbortController();
    const epoch = ++generation;
    try {
      const health = await api<{ mode: string }>('/health', undefined, abort.signal);
      if (disposed || epoch !== generation) return;
      setMode(health.mode);
      if (health.mode === 'live') {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          stream.getTracks().forEach(track => track.stop());
        } catch {
          throw new Error('Microphone access denied or unavailable. Allow it in your browser and retry.');
        }
      }
      if (disposed || epoch !== generation) return;
      const created = await api<Connection>('/api/sessions', setup(), abort.signal);
      if (disposed || epoch !== generation) return;
      setSession(created);
      const interrupted = (text: string) => {
        if (epoch !== generation || disposed) return;
        setError(text);
        if (busy()) lostDuringStart = true;
        else void end(true);
      };
      const cid = await voice.start(created, {
        message: (speaker, text) => {
          if (epoch === generation && !disposed) setTurns(previous => [
            ...previous, { turn_id: `live-${previous.length + 1}`, speaker, text },
          ]);
        },
        status: value => { if (epoch === generation && !disposed) setStatus(value); },
        disconnected: () => interrupted('Voice disconnected. Preparing a partial review.'),
        error: () => interrupted('Voice connection failed. Check ElevenLabs access and agent settings.'),
      });
      if (disposed || epoch !== generation) { await voice.end(); return; }
      const next = await api<Session>(`/api/sessions/${created.id}/started`, { conversation_id: cid }, abort.signal);
      if (disposed || epoch !== generation) { await voice.end(); return; }
      setSession(next);
      setActive(true);
      setMuted(false);
      const began = Date.now();
      timer = setInterval(() => setElapsed(Math.floor((Date.now() - began) / 1000)), 1000);
    } catch (exc) {
      await voice.end().catch(() => {});
      if (!disposed) {
        setError(message(exc, 'Unable to connect.'));
        setStatus('Connection failed');
      }
    } finally {
      if (!disposed) {
        setBusy(false);
        if (lostDuringStart && active()) void end(true);
      }
    }
  }

  async function retry() {
    const current = session();
    if (!current || busy()) return;
    setBusy(true);
    setError('');
    try {
      const next = await api<Session>(`/api/sessions/${current.id}/review/retry`, {}, abort.signal);
      if (disposed) return;
      setSession(next);
      void poll(current.id, generation, Date.now() + 310000);
    } catch (exc) {
      if (!disposed) setError(message(exc, 'Retry failed.'));
    } finally { if (!disposed) setBusy(false); }
  }

  onCleanup(() => {
    disposed = true;
    generation++;
    stopTimers();
    abort.abort();
    void voice.end().catch(() => {});
  });

  return <main>
    <header><h1>Voice Language Tutor</h1><p>Practice a conversation, then review what you said.</p></header>
    <Show when={mode() === 'fake'}>
      <p class="notice">Simulation — no microphone, audio, or provider calls. Sample transcript and review only.</p>
    </Show>
    <Show when={mode() === 'live'}><p>Audio goes to ElevenLabs; review text goes to OpenAI.</p></Show>
    <p><small>Sessions are kept in memory. Server restarts or browser reloads lose this view.</small></p>
    <SetupForm value={setup()} disabled={active() || busy() || reviewing() || endPending()}
      change={(key, value) => setSetup(previous => ({ ...previous, [key]: value }))} />
    <ConversationControls active={active()} busy={busy() || reviewing() || endPending()}
      muted={muted()} status={`${status()} · ${Math.floor(elapsed() / 60)}:${String(elapsed() % 60).padStart(2, '0')}`}
      start={() => void start()} end={() => void end()}
      mute={() => { setMuted(value => !value); voice.mute(muted()); }} />
    <Show when={endPending()}>
      <p>Review preparation has not been confirmed.
        <button disabled={busy()} onClick={() => void end(true)}>Retry End</button>
      </p>
    </Show>
    <Show when={pollFailed()}>
      <button onClick={() => {
        const current = session();
        if (current) { setError(''); void poll(current.id, generation, Date.now() + 310000); }
      }}>Refresh review status</button>
    </Show>
    <Show when={error()}><p role="alert">{error()}</p></Show>
    <Transcript turns={turns()} />
    <ReviewPanel session={session()} retry={() => void retry()} busy={busy()} />
  </main>;
}
