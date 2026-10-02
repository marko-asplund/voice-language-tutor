import { For, Show } from 'solid-js';
import type { Session } from '../types';
export default function ReviewPanel(props:{session:Session|null;retry:()=>void;busy:boolean}) {
 return <section aria-live="polite"><h2>Session review</h2><Show when={props.session?.partial}><p>Partial session after a disconnect.</p></Show>
 <Show when={props.session?.state === 'transcript_pending'}><p>Waiting for ElevenLabs to finalize the transcript…</p></Show>
 <Show when={props.session?.state === 'reviewing'}><p>Preparing grounded feedback…</p></Show>
 <Show when={props.session?.error}>{error=><p role="alert">{error().message} <Show when={error().retryable}><button disabled={props.busy} onClick={props.retry}>Retry review</button></Show></p>}</Show>
 <Show when={props.session?.review}>{review=><><p>{review().summary}</p><h3>Corrections</h3><Show when={!review().mistakes.length}><p>No corrections suggested.</p></Show><For each={review().mistakes}>{m=><article><p>“{m.original}” → {m.corrected}</p><p>{m.explanation}</p><small>Evidence: {m.turn_id} · {m.category}</small></article>}</For><h3>Vocabulary</h3><For each={review().new_vocabulary}>{v=><article><strong>{v.term}</strong> — {v.translation}<p>{v.example}</p><small>{v.example_kind === 'generated'?'Generated example':'Conversation example'} · {v.turn_id}</small></article>}</For><h3>Next topics</h3><ul><For each={review().suggested_next_topics}>{topic=><li>{topic}</li>}</For></ul></>}</Show></section>;
}
