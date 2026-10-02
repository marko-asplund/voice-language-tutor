export default function ConversationControls(props:{active:boolean;busy:boolean;muted:boolean;status:string;start:()=>void;end:()=>void;mute:()=>void}) {
 return <div class="controls"><button disabled={props.busy || props.active} onClick={props.start}>Start</button><button disabled={props.busy || !props.active} onClick={props.end}>End</button><button disabled={!props.active || props.busy} onClick={props.mute}>{props.muted?'Unmute':'Mute'}</button><span role="status">{props.status}</span></div>;
}
