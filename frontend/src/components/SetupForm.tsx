import type { Setup } from '../types';
export default function SetupForm(props:{value:Setup;disabled:boolean;change:(key:keyof Setup,value:string)=>void}) {
  return <fieldset disabled={props.disabled}><legend>Your practice</legend>
    <label>Target language<input required maxlength="80" value={props.value.target_language} onInput={e=>props.change('target_language',e.currentTarget.value)} /></label>
    <label>Native language<input required maxlength="80" value={props.value.native_language} onInput={e=>props.change('native_language',e.currentTarget.value)} /></label>
    <label>Level<select value={props.value.level} onChange={e=>props.change('level',e.currentTarget.value)}>{['A1','A2','B1','B2','C1','C2'].map(level=><option>{level}</option>)}</select></label>
    <label>Topic<input required maxlength="200" value={props.value.topic} onInput={e=>props.change('topic',e.currentTarget.value)} /></label>
    <label>Name (optional)<input maxlength="80" value={props.value.student_name} onInput={e=>props.change('student_name',e.currentTarget.value)} /></label>
  </fieldset>;
}
