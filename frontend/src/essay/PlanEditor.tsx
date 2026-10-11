import {useState} from 'react';
import {Plan,Source} from './api';

export function PlanEditor({initial,sources,onSave,onCancel,locked=false,saving=false}:{initial:Plan;sources:Source[];onSave:(plan:Plan)=>void;onCancel:()=>void;locked?:boolean;saving?:boolean}) {
 const [plan,setPlan]=useState<Plan>(structuredClone(initial));
 const changeClaim=(index:number,key:string,value:unknown)=>setPlan(p=>({...p,claims:p.claims.map((c,i)=>i===index?{...c,[key]:value}:c)}));
 const changeSection=(index:number,key:string,value:unknown)=>setPlan(p=>({...p,sections:p.sections.map((s,i)=>i===index?{...s,[key]:value}:s)}));
 const evidence=sources.filter(s=>s.status!=='excluded').flatMap(s=>s.evidence.map(e=>({...e,title:s.title})));
 const text=(label:string,value:string,onChange:(v:string)=>void)=><label className="sg-field">{label}<textarea rows={3} value={value} onChange={e=>onChange(e.target.value)}/></label>;
 return <form onSubmit={e=>{e.preventDefault();onSave(plan)}} className="sg-plan-editor">
  <div className="sg-grid-two">{text('Titolo',plan.title,v=>setPlan(p=>({...p,title:v})))}{text('Sottotitolo',plan.subtitle,v=>setPlan(p=>({...p,subtitle:v})))}</div>
  {text('Direzione del libro',plan.direction,v=>setPlan(p=>({...p,direction:v})))}
  {text('Metodo',plan.method,v=>setPlan(p=>({...p,method:v})))}
  {text('Definizioni · una per riga',plan.definitions.join('\n'),v=>setPlan(p=>({...p,definitions:v.split('\n').filter(Boolean)})))}
  <h3>Argomenti</h3>
  {plan.claims.map((claim,index)=><details className="sg-subcard" key={claim.id} open={index===0}><summary>{index+1}. {claim.text || 'Nuovo argomento'}</summary>
   {text('Affermazione',claim.text,v=>changeClaim(index,'text',v))}
   <label className="sg-field">Tipo<select value={claim.kind} onChange={e=>changeClaim(index,'kind',e.target.value)}>{[['factual','Fattuale'],['interpretive','Interpretativa'],['normative','Normativa'],['hypothesis','Ipotesi'],['experience','Esperienza dichiarata']].map(([k,l])=><option key={k} value={k}>{l}</option>)}</select></label>
   {text('Ragione o premessa',claim.reason,v=>changeClaim(index,'reason',v))}
   <div className="sg-grid-two">{text('Obiezione',claim.objection,v=>changeClaim(index,'objection',v))}{text('Risposta',claim.response,v=>changeClaim(index,'response',v))}</div>
   {text('Lacuna o limite',claim.gap,v=>changeClaim(index,'gap',v))}
   <details><summary>Collega le evidenze ({claim.evidence_ids.length})</summary>{evidence.length===0?<p>Nessun estratto disponibile. Importa e analizza una fonte.</p>:evidence.map(e=><label className="sg-evidence-choice" key={e.id}><input type="checkbox" checked={claim.evidence_ids.includes(e.id)} onChange={event=>changeClaim(index,'evidence_ids',event.target.checked?[...claim.evidence_ids,e.id]:claim.evidence_ids.filter(x=>x!==e.id))}/><span><strong>{e.title}</strong><small>{e.locator}</small>{e.quote}</span></label>)}</details>
   <button type="button" className="sg-text-button" onClick={()=>setPlan(p=>({...p,claims:p.claims.filter(c=>c.id!==claim.id),sections:p.sections.map(s=>({...s,claim_ids:s.claim_ids.filter(id=>id!==claim.id)}))}))}>Rimuovi argomento</button>
  </details>)}
  <button type="button" onClick={()=>setPlan(p=>({...p,claims:[...p.claims,{id:'A'+Date.now(),text:'',kind:'interpretive',reason:'',evidence_ids:[],objection:'',response:'',gap:''}]}))}>Aggiungi argomento</button>
  <h3>Indice</h3>
  {plan.sections.map((section,index)=><details className="sg-subcard" key={section.id}><summary>{index+1}. {section.title}</summary>
   {text('Titolo',section.title,v=>changeSection(index,'title',v))}
   {text('Funzione nel libro',section.purpose,v=>changeSection(index,'purpose',v))}
   {text('Contenuto da sviluppare',section.description,v=>changeSection(index,'description',v))}
   <label className="sg-field">Parole indicative<input type="number" min={200} max={8000} value={section.word_target} onChange={e=>changeSection(index,'word_target',Number(e.target.value))}/></label>
   <fieldset><legend>Argomenti da sviluppare</legend>{plan.claims.map(c=><label className="sg-evidence-choice" key={c.id}><input type="checkbox" checked={section.claim_ids.includes(c.id)} onChange={e=>changeSection(index,'claim_ids',e.target.checked?[...section.claim_ids,c.id]:section.claim_ids.filter(x=>x!==c.id))}/><span>{c.text}</span></label>)}</fieldset>
   {!locked&&<div className="sg-actions"><button type="button" disabled={index===0} aria-label={'Sposta in alto '+section.title} onClick={()=>setPlan(p=>{const next=[...p.sections];[next[index-1],next[index]]=[next[index],next[index-1]];return {...p,sections:next}})}>↑</button><button type="button" disabled={index===plan.sections.length-1} aria-label={'Sposta in basso '+section.title} onClick={()=>setPlan(p=>{const next=[...p.sections];[next[index+1],next[index]]=[next[index],next[index+1]];return {...p,sections:next}})}>↓</button><button type="button" onClick={()=>setPlan(p=>({...p,sections:p.sections.filter(s=>s.id!==section.id)}))}>Rimuovi capitolo</button></div>}
  </details>)}
  {!locked&&<button type="button" onClick={()=>setPlan(p=>({...p,sections:[...p.sections,{id:'C'+Date.now(),title:'Nuovo capitolo',purpose:'',description:'',claim_ids:[],word_target:1000}]}))}>Aggiungi capitolo</button>}
  {text('Limiti dichiarati · uno per riga',plan.limits.join('\n'),v=>setPlan(p=>({...p,limits:v.split('\n').filter(Boolean)})))}
  <div className="sg-actions"><button className="sg-primary" disabled={saving}>{saving?'Salvataggio…':'Salva piano'}</button><button type="button" onClick={onCancel}>Annulla</button></div>
 </form>;
}
