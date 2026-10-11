import {useState,useEffect,useRef} from 'react';
import toast from 'react-hot-toast';
import {api,write,Project,Source} from './api';

export function SourcePanel({project,onChange,onOpen,onJob}:{project:Project;onChange:(p:Project)=>void;onOpen:(id:string)=>void;onJob:(kind:string)=>void}) {
 const [query,setQuery]=useState(project.form_data.topic);
 const [title,setTitle]=useState('');
 const [url,setUrl]=useState('');
 const [text,setText]=useState('');
 const [author,setAuthor]=useState('');
 const [published,setPublished]=useState('');
 const [kind,setKind]=useState('author_notes');
 const [busy,setBusy]=useState(false);
 const disabled=busy||project.active;
 async function run(action:()=>Promise<Project>,message:string) {
  setBusy(true);try{onChange(await action());toast.success(message);return true}catch(error){toast.error((error as Error).message);return false}finally{setBusy(false)}
 }
 return <div className="sg-sources">
  <section className="sg-card"><span className="sg-eyebrow">Documentazione</span><h2>Fonti e materiali</h2><p>Raccogli prove a favore, obiezioni e contesto. Le fonti diventano citabili quando hanno un estratto localizzato.</p>
   <form onSubmit={e=>{e.preventDefault();void run(()=>api<Project>('essays/'+project.session_id+'/research',write({query})),'Ricerca avviata')}}>
    <label className="sg-field">Cerca sul web<textarea rows={2} value={query} minLength={3} required onChange={e=>setQuery(e.target.value)} placeholder="Tema, domanda o affermazione da documentare"/></label><button disabled={disabled||query.trim().length<3}>Cerca e analizza fonti</button>
   </form>
   <p className="sg-help">La ricerca usa Google e ha consumi propri. Un documento non accessibile resta segnalato.</p>
   <details><summary>Importa un documento</summary><p>PDF testuale, DOCX, TXT o Markdown · fino a 12 MB.</p>
    <label className="sg-field">Autore o ente<input value={author} onChange={e=>setAuthor(e.target.value)}/></label><label className="sg-field">Data di pubblicazione<input value={published} placeholder="Se disponibile" onChange={e=>setPublished(e.target.value)}/></label>
    <label className="sg-upload">Scegli documento<input type="file" disabled={disabled} accept=".pdf,.docx,.txt,.md,.markdown" onChange={e=>{const file=e.target.files?.[0];if(!file)return;const data=new FormData();data.append('file',file);data.append('author',author);data.append('published',published);void run(()=>api<Project>('essays/'+project.session_id+'/upload',{method:'POST',body:data}),'Documento importato');e.target.value=''}}/></label>
   </details>
   <details><summary>Aggiungi un link o incolla un testo</summary><form onSubmit={e=>{e.preventDefault();void run(()=>api<Project>('essays/'+project.session_id+'/sources',write({title,author,published,url,text,kind})),'Materiale aggiunto').then(ok=>{if(ok){setTitle('');setUrl('');setText('')}})}}>
    <label className="sg-field">Titolo<input required value={title} onChange={e=>setTitle(e.target.value)}/></label>
    <label className="sg-field">Autore o ente<input value={author} onChange={e=>setAuthor(e.target.value)}/></label>
    <label className="sg-field">Data di pubblicazione<input value={published} onChange={e=>setPublished(e.target.value)}/></label>
    <label className="sg-field">URL pubblico<input type="url" value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://…"/></label>
    {!url&&<><label className="sg-field">Tipo di materiale<select value={kind} onChange={e=>setKind(e.target.value)}><option value="author_notes">Appunti o esperienza dell’autore</option><option value="document">Documento esterno</option></select></label><label className="sg-field">Testo<textarea rows={6} minLength={20} value={text} required onChange={e=>setText(e.target.value)}/></label></>}
    <button disabled={disabled}>Aggiungi materiale</button>
   </form></details>
  </section>
  <section className="sg-card"><div className="sg-section-top"><h3>Registro delle fonti <span className="sg-count">{project.sources.length}</span></h3><button disabled={disabled||!project.sources.some(s=>s.status==='acquired')} onClick={()=>onJob('memory')}>Analizza materiali</button></div>
   {project.sources.length===0?<div className="sg-empty-small">Aggiungi una fonte o avvia una ricerca. Puoi preparare il piano anche adesso, con le lacune esplicite.</div>:project.sources.map(source=><article key={source.id} id={'source-'+source.id} className={'sg-source '+(source.status==='excluded'?'sg-muted':'')}>
    <div className="sg-section-top"><strong>{source.title}</strong><span className={'sg-badge '+source.status}>{({proposed:'Da acquisire',acquired:'Acquisita',analyzed:'Analizzata',failed:'Non acquisita',excluded:'Esclusa'} as Record<string,string>)[source.status]}</span></div>
    <small>{source.author||'Autore non disponibile'} · {source.published||'Data non disponibile'} · {source.kind==='author_notes'?'Materiale dell’autore':source.kind==='web'?'Web':'Documento'}</small>
    {source.error&&<p className="sg-error-inline">{source.error}</p>}
    <p>{source.evidence.length} {source.evidence.length===1?'estratto localizzato':'estratti localizzati'}</p>
    <div className="sg-actions"><button onClick={()=>onOpen(source.id)}>Apri fonte</button><button disabled={disabled} onClick={()=>void run(()=>api<Project>('essays/'+project.session_id+'/sources/'+source.id+'/exclude',write({})),source.status==='excluded'?'Fonte inclusa':'Fonte esclusa')}>{source.status==='excluded'?'Includi':'Escludi'}</button></div>
   </article>)}
  </section>
  {project.research_log.length>0&&<details className="sg-card"><summary>Ricerche effettuate</summary>{project.research_log.map((research,i)=><div key={i} className="sg-source"><strong>{research.query}</strong><p>{research.found} fonti individuate · {new Date(research.at).toLocaleString('it-IT')}</p><small>{research.provider_queries.join(' · ')}</small>{research.suggestions_html&&<iframe title={'Suggerimenti di ricerca '+(i+1)} sandbox="" srcDoc={research.suggestions_html} className="sg-search-suggestions"/>}</div>)}</details>}
 </div>;
}

export function SourceDialog({source,onClose,onUpdate,projectId,disabled}:{source:Source;onClose:()=>void;onUpdate:(p:Project)=>void;projectId:string;disabled:boolean}) {
 const [quote,setQuote]=useState('');
 const [stance,setStance]=useState('context');
 const [explanation,setExplanation]=useState('');
 const [busy,setBusy]=useState(false);
 const [metadata,setMetadata]=useState({title:source.title,author:source.author,published:source.published});
 const [metadataVersion,setMetadataVersion]=useState(source.version);
 const dialog=useRef<HTMLElement>(null);
 const closeRef=useRef(onClose);
 closeRef.current=onClose;
 useEffect(()=>{
  const previous=document.activeElement as HTMLElement;
  const key=(event:KeyboardEvent)=>{
   if(event.key==='Escape')closeRef.current();
   if(event.key==='Tab'){
    const nodes=Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input:not(:disabled),textarea:not(:disabled),select:not(:disabled),summary')||[]);
    const first=nodes[0],last=nodes[nodes.length-1];
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}
   }
  };
  document.addEventListener('keydown',key);
  return()=>{document.removeEventListener('keydown',key);previous?.focus()};
 },[]);
 return <div className="sg-dialog-backdrop" onClick={onClose}><section ref={dialog} className="sg-dialog" role="dialog" aria-modal="true" aria-labelledby="source-dialog-title" onClick={e=>e.stopPropagation()}>
  <div className="sg-section-top"><h2 id="source-dialog-title">{source.title}</h2><button onClick={onClose} autoFocus aria-label="Chiudi fonte">×</button></div>
  <p>{source.author||'Autore non disponibile'} · {source.published||'Data non disponibile'}</p>
  {source.url&&<a href={source.url} target="_blank" rel="noreferrer">Apri documento originale ↗</a>}
  {source.error&&<p role="alert" className="sg-error-inline">{source.error}</p>}
  <details><summary>Dati bibliografici</summary><form onSubmit={e=>{e.preventDefault();setBusy(true);void api<Project>('essays/'+projectId+'/sources/'+source.id,{method:'PUT',body:JSON.stringify({...metadata,expected_version:metadataVersion})}).then(p=>{onUpdate(p);setMetadataVersion(p.sources.find(s=>s.id===source.id)?.version||metadataVersion);toast.success('Dati bibliografici aggiornati')}).catch(error=>toast.error(error.message)).finally(()=>setBusy(false))}}>
   <label className="sg-field">Titolo della fonte<input required value={metadata.title} onChange={e=>setMetadata(old=>({...old,title:e.target.value}))}/></label>
   <label className="sg-field">Autore o ente della fonte<input value={metadata.author} onChange={e=>setMetadata(old=>({...old,author:e.target.value}))}/></label>
   <label className="sg-field">Data della fonte<input value={metadata.published} onChange={e=>setMetadata(old=>({...old,published:e.target.value}))}/></label>
   <button disabled={busy||disabled}>Salva dati bibliografici</button>
  </form></details>
  {source.url&&['failed','proposed'].includes(source.status)&&<button disabled={busy||disabled} onClick={()=>{setBusy(true);void api<Project>('essays/'+projectId+'/sources/'+source.id+'/retry',write({})).then(p=>{onUpdate(p);toast.success('Fonte acquisita. Puoi analizzarla dal registro.')}).catch(error=>toast.error(error.message)).finally(()=>setBusy(false))}}>Riprova acquisizione</button>}
  <h3>Estratti e relazione con la tesi</h3>
  {source.evidence.map(e=><div className="sg-subcard" key={e.id}><span className="sg-badge">{({supports:'A favore',contradicts:'Contrario',mixed:'Riscontro misto',context:'Contesto'} as Record<string,string>)[e.stance]}</span><blockquote>{e.quote}</blockquote><small>{e.locator} · {e.reviewed?'Inserito dall’autore':'Analisi AI'}</small><p>{e.explanation}</p><code>{'[@'+e.id+']'}</code><p className="sg-help">Usa questo riferimento nell’editor per citare l’estratto.</p></div>)}
  {source.text&&<><details open><summary>Testo acquisito</summary><div className="sg-source-text">{source.text}</div></details><form onSubmit={e=>{e.preventDefault();setBusy(true);void api<Project>('essays/'+projectId+'/sources/'+source.id+'/evidence',write({quote,stance,explanation})).then(p=>{onUpdate(p);toast.success('Estratto registrato');setQuote('');setExplanation('')}).catch(error=>toast.error(error.message)).finally(()=>setBusy(false))}}>
   <h3>Aggiungi un estratto</h3><label className="sg-field">Passaggio esatto dal testo<textarea required minLength={8} rows={3} value={quote} onChange={e=>setQuote(e.target.value)}/></label>
   <label className="sg-field">Relazione<select value={stance} onChange={e=>setStance(e.target.value)}><option value="context">Contesto</option><option value="supports">A favore</option><option value="contradicts">Contrario</option><option value="mixed">Riscontro misto</option></select></label>
   <label className="sg-field">Che cosa sostiene, e quali sono i limiti?<textarea value={explanation} onChange={e=>setExplanation(e.target.value)}/></label><button disabled={busy||disabled}>Registra estratto</button>
  </form></>}
 </section></div>;
}
