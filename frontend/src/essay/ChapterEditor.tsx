import {useState,useEffect} from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import toast from 'react-hot-toast';
import {api,Chapter,Project} from './api';

export function ChapterEditor({chapter,project,onChange,onOpenSource,onDirty}:{chapter:Chapter;project:Project;onChange:(p:Project)=>void;onOpenSource:(id:string)=>void;onDirty:(dirty:boolean)=>void}) {
 const key='saggia.chapter.'+project.session_id+'.'+chapter.section_id;
 const [editing,setEditing]=useState(false);
 const [text,setText]=useState(()=>{
  try {return JSON.parse(localStorage.getItem(key)||'null')?.content ?? chapter.content}catch{return chapter.content}
 });
 const [hash,setHash]=useState(()=>{
  try {return JSON.parse(localStorage.getItem(key)||'null')?.hash ?? chapter.hash}catch{return chapter.hash}
 });
 const [dirty,setDirty]=useState(text!==chapter.content);
 const [saving,setSaving]=useState(false);
 const [revisions,setRevisions]=useState<{revision:number;created_at:number;content:string}[]|null>(null);
 useEffect(()=>{onDirty(dirty);return()=>onDirty(false)},[dirty,onDirty]);
 useEffect(()=>{
  if(!dirty){setText(chapter.content);setHash(chapter.hash)}
 },[chapter.hash,chapter.content,dirty]);
 useEffect(()=>{
  const beforeUnload=(event:BeforeUnloadEvent)=>{if(dirty){event.preventDefault();event.returnValue=''}};
  window.addEventListener('beforeunload',beforeUnload);
  return()=>window.removeEventListener('beforeunload',beforeUnload);
 },[dirty]);
 function change(value:string){
  setText(value);setDirty(value!==chapter.content);
  try{localStorage.setItem(key,JSON.stringify({content:value,hash}))}catch{/* editing remains available */}
 }
 async function save() {
  setSaving(true);
  try{
   const p=await api<Project>('essays/'+project.session_id+'/chapters/'+chapter.section_index,{method:'PUT',body:JSON.stringify({content:text,expected_hash:hash})});
   try{localStorage.removeItem(key)}catch{/* the server copy is already saved */}setDirty(false);setEditing(false);onChange(p);toast.success('Capitolo salvato. La revisione è da aggiornare.');
  }catch(error){toast.error((error as Error).message)}finally{setSaving(false)}
 }
 return <section className="sg-card sg-chapter">
  <div className="sg-section-top"><div><span className="sg-eyebrow">Capitolo {chapter.section_index+1}</span><h2>{chapter.title}</h2></div><div className="sg-actions">
   <button disabled={project.active} onClick={()=>setEditing(!editing)}>{editing?'Leggi':'Modifica'}</button>
   <button onClick={()=>void api<typeof revisions>('essays/'+project.session_id+'/chapters/'+chapter.section_index+'/revisions').then(setRevisions).catch(e=>toast.error(e.message))}>Versioni</button>
  </div></div>
  {dirty&&<p className="sg-notice">Hai modifiche non salvate, conservate anche su questo dispositivo.</p>}
  {editing?<><textarea className="sg-manuscript-editor" aria-label="Testo del capitolo" value={text} onChange={e=>change(e.target.value)} disabled={project.active}/><div className="sg-actions"><button className="sg-primary" onClick={()=>void save()} disabled={saving||project.active||!dirty}>{saving?'Salvataggio…':'Salva revisione'}</button><button onClick={()=>{if(dirty&&!window.confirm('Scartare le modifiche non salvate?'))return;localStorage.removeItem(key);setText(chapter.content);setHash(chapter.hash);setDirty(false)}}>Ricarica versione salvata</button></div></>:
   <div className="sg-prose"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{a:({href,children})=>href?.startsWith('#source-')?<button className="sg-citation" onClick={()=>onOpenSource(href.slice(8))}>{children}</button>:<a href={href} target="_blank" rel="noreferrer">{children}</a>}}>{chapter.display_content}</ReactMarkdown></div>}
  {chapter.unresolved.length>0&&<details><summary>Lacune dichiarate ({chapter.unresolved.length})</summary><ul>{chapter.unresolved.map((gap,i)=><li key={i}>{gap}</li>)}</ul></details>}
  {revisions&&<details open><summary>Versioni salvate</summary>{revisions.map(version=><div className="sg-version" key={version.revision}><span>Versione {version.revision} · {new Date(version.created_at*1000).toLocaleString('it-IT')}</span><button disabled={project.active} onClick={()=>{change(version.content);setEditing(true);setRevisions(null)}}>Porta nell’editor</button></div>)}</details>}
 </section>;
}
