import { For } from 'solid-js';
import type { Turn } from '../types';
export default function Transcript(props:{turns:Turn[]}) {
 return <section><h2>Transcript</h2><ol><For each={props.turns}>{turn=><li><strong>{turn.speaker === 'learner'?'You':'Tutor'}</strong><p>{turn.text}</p><small>{turn.turn_id}</small></li>}</For></ol></section>;
}
