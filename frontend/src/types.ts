export type Setup = {target_language:string; native_language:string; level:string; topic:string; student_name:string};
export type Turn = {turn_id:string; speaker:'learner'|'tutor'; text:string};
export type Review = {summary:string; mistakes:{turn_id:string;original:string;corrected:string;explanation:string;category:string}[];new_vocabulary:{turn_id:string;term:string;translation:string;example:string;example_kind:string}[];suggested_next_topics:string[]};
export type Session = {id:string;state:string;transcript:Turn[];review:Review|null;partial:boolean;error:{code:string;message:string;retryable:boolean}|null};
export type Connection = Session & {mode:'fake'|'live';signed_url:string|null;conversation_id:string|null;dynamic_variables:Setup};
