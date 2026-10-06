export type Profile = 'argumentative' | 'popular' | 'academic';
export type AiRole = 'challenge' | 'support' | 'explore';
export interface Brief {
  topic: string; profile: Profile; ai_role: AiRole; question: string; thesis: string;
  discipline: string; reader_level: string; reader_needs: string; target_words: number;
  concepts: string; premises: string; scope: string; exclusions: string; purpose: string;
  approach: string; voice: string; tone: string; language_register: string; structure: string;
  density: string; example_policy: string; methodology: string; corpus: string;
  source_criteria: string; source_period: string; editorial_references: string;
  author_name: string; title: string; subtitle: string; citation_style: string;
  revision_mode: string; cover_style: string; llm_model: string; model_overrides: Record<string,string>;
  budget_eur: number | null;
}
export interface Config {
  name: string; models: {id:string;label:string}[]; default_model:string; stages:Record<string,string>;
  profiles: Record<Profile,{label:string;description:string;defaults:Partial<Brief>}>;
  roles: Record<AiRole,{label:string;description:string}>;
  api_key_ready:boolean;
}
export interface Evidence { id:string; source_id:string; quote:string; locator:string; stance:string; explanation:string; reviewed:boolean }
export interface Source { version:number; id:string; title:string; author:string; published:string; url:string; kind:string; status:string; error:string; text?:string; text_length:number; evidence:Evidence[]; selection_reason:string }
export interface Claim {id:string;text:string;kind:string;reason:string;evidence_ids:string[];objection:string;response:string;gap:string}
export interface Section {id:string;title:string;purpose:string;description:string;claim_ids:string[];word_target:number}
export interface Plan { title:string; subtitle:string; direction:string; method:string; definitions:string[]; claims:Claim[]; sections:Section[]; limits:string[] }
export interface Chapter { section_id:string;section_index:number;title:string;content:string;display_content:string;hash:string;unresolved:string[] }
export interface Issue {section_id:string;quote:string;category:string;severity:string;explanation:string;suggestion:string}
export interface Progress {status:string;error?:string;current_step?:number;total_steps?:number;current_section_name?:string;current_part?:number;total_parts?:number;updated_at?:string}
export interface Project {
 session_id:string;form_data:Brief;current_version:number;plan:Plan|null;validated:boolean;
 generated_questions:{id:string;text:string}[];answers:Record<string,string>;sources:Source[];
 research_log:{query:string;provider_queries:string[];at:string;found:number;summary:string;suggestions_html:string}[];
 book_chapters:Chapter[];active:boolean;words:number;estimated_pages:number;pause_requested:boolean;
 review:{summary:string;strengths:string[];issues:Issue[];partial:boolean;at:string}|null;
 questions_progress:Progress|null;draft_progress:Progress|null;memory_progress:Progress|null;
 writing_progress:Progress|null;review_progress:Progress|null;cover_progress:Progress|null;cover_image_path:string|null;
 bibliography:{id:string;label:string;text:string}[];reference_checks:{citations:number;evidence:number;issues:Issue[]};
 usage:{converted_cost_eur:number|null;cost_usd:number|null;coverage_complete:boolean;calls:number;tool_cost_unknown?:boolean;events:{id:string;phase:string;model:string;status:string;cost_usd:number|null;usage?:{input_tokens:number;output_tokens:number}}[]};
}
export interface LibraryItem {id:string;title:string;topic:string;profile:Profile;ai_role:AiRole;status:string;updated_at:string;words:number}

export const defaultBrief = (): Brief => ({
 topic:'', profile:'argumentative',ai_role:'challenge',question:'',thesis:'',discipline:'',
 reader_level:'general',reader_needs:'',target_words:35000,concepts:'',premises:'',scope:'',exclusions:'',
 purpose:'argomentare',approach:'analytical',voice:'impersonal',tone:'analytical',language_register:'clear',
 structure:'thesis',density:'balanced',example_policy:'mixed',methodology:'',corpus:'',source_criteria:'',
 source_period:'',editorial_references:'',author_name:'',title:'',subtitle:'',citation_style:'numeric',
 revision_mode:'reviewed',cover_style:'typographic',llm_model:'gemini-3.8-flash',model_overrides:{},budget_eur:null,
});
export async function api<T>(path:string, options:RequestInit = {}):Promise<T> {
 const response = await fetch('/api/' + path,{...options,headers: options.body instanceof FormData ? options.headers : {'Content-Type':'application/json',...options.headers}});
 if (!response.ok) {
  let message = 'Il server non ha completato la richiesta.';
  try { const error = await response.json(); message = typeof error.detail === 'string' ? error.detail : (error.detail || []).map((x:{msg:string})=>x.msg).join(' · '); } catch { /* preserve network status */ }
  throw new Error(message);
 }
 if (response.status === 204) return undefined as T;
 return response.json();
}
export const write = (value:unknown) => ({method:'POST',body:JSON.stringify(value)});
