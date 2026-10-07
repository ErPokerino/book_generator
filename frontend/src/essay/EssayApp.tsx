import {useState,useEffect,useCallback,useRef} from 'react';
import {BrowserRouter,Link,Routes,Route,useNavigate,useParams} from 'react-router-dom';
import {Toaster} from 'react-hot-toast';
import toast from 'react-hot-toast';
import {BookOpen,Plus,Check,Library as LibraryIcon} from 'lucide-react';
import {api,write,Brief,Config,Project,Source,Progress,defaultBrief} from './api';
import {BriefForm} from './BriefForm';
import {PublicationForm} from './PublicationForm';
import {PlanEditor} from './PlanEditor';
import {SourcePanel,SourceDialog} from './SourcePanel';
import {ChapterEditor} from './ChapterEditor';
import {GenerationProgress} from './GenerationProgress';
import {EssayLibrary} from './EssayLibrary';
import './essay.css';

const profiles:Record<string,string>={argumentative:'Argomentativo',popular:'Divulgativo',academic:'Accademico'};
const tabs=[['project','Progetto'],['questions','Domande'],['plan','Argomenti e fonti'],['outline','Indice'],['manuscript','Manoscritto'],['review','Revisione']];
function message(error:unknown){return (error as Error).message || 'La richiesta non è riuscita.'}
function Loading(){return <div className="sg-loading" role="status">Caricamento dello studio…</div>}

function NewEssay({config}:{config:Config}){
 const navigate=useNavigate();
 const [saving,setSaving]=useState(false);
 const [initial]=useState<Brief>(()=>{try{return {...defaultBrief(),...JSON.parse(localStorage.getItem('saggia.new.brief')||'{}')}}catch{return defaultBrief()}});
 async function create(brief:Brief){
  setSaving(true);
  try{const p=await api<Project>('essays',write(brief));try{localStorage.removeItem('saggia.new.brief')}catch{/* keep saved project accessible */}navigate('/essay/'+p.session_id)}catch(error){toast.error(message(error))}finally{setSaving(false)}
 }
 return <div className="sg-page sg-create-page"><header className="sg-page-header"><div><span className="sg-eyebrow">Un nuovo libro di saggistica</span><h1>Parti da un’idea.<br/>Costruisci un’argomentazione.</h1><p>Un tema basta per iniziare. Tesi, fonti e struttura si affinano insieme.</p></div><div className="sg-margin-note">Per lettori adulti.<br/>Con una voce che resta tua.</div></header><BriefForm initial={initial} config={config} saving={saving} onDraft={brief=>{try{localStorage.setItem('saggia.new.brief',JSON.stringify(brief))}catch{/* form remains editable */}}} onSave={brief=>void create(brief)}/></div>;
}

function Workspace({config,onUnsaved}:{config:Config;onUnsaved:(dirty:boolean)=>void}){
 const {id=''}=useParams();
 const navigate=useNavigate();
 const [project,setProject]=useState<Project|null>(null);
 const [error,setError]=useState('');
 const [tab,setTab]=useState('questions');
 const [editingBrief,setEditingBrief]=useState(false);
 const [editingPlan,setEditingPlan]=useState(false);
 const [editingVersion,setEditingVersion]=useState(0);
 const [selected,setSelected]=useState(0);
 const [dirty,setDirty]=useState(false);
 const [publicationDirty,setPublicationDirty]=useState(false);
 const [source,setSource]=useState<Source|null>(null);
 const [answers,setAnswers]=useState<Record<string,string>>({});
 const [busy,setBusy]=useState(false);
 const projectRef=useRef<Project|null>(null);
 useEffect(()=>{onUnsaved(dirty||publicationDirty||editingBrief||editingPlan);return()=>onUnsaved(false)},[dirty,publicationDirty,editingBrief,editingPlan,onUnsaved]);
 const accept=useCallback((p:Project)=>{
  projectRef.current=p;setProject(p);setError('');
  setSource(old=>old?{...old,...p.sources.find(s=>s.id===old.id),text:old.text}:null);
 },[]);
 useEffect(()=>{
  let stopped=false,timer:ReturnType<typeof setTimeout>,failures=0;
  async function poll(){
   try{
    const p=await api<Project>('essays/'+id);
    if(stopped)return;
    accept(p);failures=0;
    if(!projectRef.current?.active){setAnswers(old=>Object.keys(old).length?old:p.answers)}
   }catch(e){if(!stopped){failures++;setError(message(e))}}
   if(!stopped)timer=setTimeout(()=>void poll(),Math.min(15000,2000*Math.pow(2,failures)));
  }
  void poll();
  try{setTab(localStorage.getItem('saggia.tab.'+id)||'questions')}catch{/* default */}
  return()=>{stopped=true;clearTimeout(timer)};
 },[id,accept]);
 function guard(action:()=>void){if((dirty||publicationDirty||editingBrief||editingPlan)&&!window.confirm('Hai modifiche non salvate. Vuoi comunque cambiare vista?'))return;action()}
 function chooseTab(next:string){guard(()=>{setTab(next);setEditingBrief(false);setEditingPlan(false);try{localStorage.setItem('saggia.tab.'+id,next)}catch{/* navigation remains available */}})}
 async function perform(path:string,options:RequestInit=write({}),success=''){
  setBusy(true);
  try{accept(await api<Project>('essays/'+id+'/'+path,options));if(success)toast.success(success);return true}catch(e){toast.error(message(e));return false}finally{setBusy(false)}
 }
 async function job(kind:string){
  if(dirty||publicationDirty||editingPlan||editingBrief){toast.error('Salva le modifiche prima di avviare un processo.');return}
  await perform('jobs/'+kind,write({}),'Operazione avviata');
 }
 async function openSource(sourceId:string){
  try{setSource(await api<Source>('essays/'+id+'/sources/'+sourceId))}catch(e){toast.error(message(e))}
 }
 if(!project)return <div className="sg-page">{error?<div className="sg-card"><p role="alert">{error}</p><Link to="/">Torna alla biblioteca</Link></div>:<Loading/>}</div>;
 const disabled=project.active||busy;
 const progressItems=[project.questions_progress,project.draft_progress,project.memory_progress,project.writing_progress,project.review_progress,project.cover_progress].filter(Boolean) as Progress[];
 const lastProgress=[...progressItems].sort((a,b)=>(b.updated_at||'').localeCompare(a.updated_at||''))[0];
 const chapters=project.book_chapters;
 const chapter=chapters[selected];
 const hasTitle=Boolean(project.form_data.title||project.plan?.title);
 const title=project.form_data.title||project.plan?.title||project.form_data.topic;
 const claims=project.plan?.claims||[];
 async function download(format:string){
  try{
   const response=await fetch('/api/essays/'+id+'/export/'+format);
   if(!response.ok){const error=await response.json();throw new Error(error.detail||'Esportazione non riuscita')}
   const blob=await response.blob();const href=URL.createObjectURL(blob);const link=document.createElement('a');
   link.href=href;link.download=title.slice(0,100)+'.'+format;document.body.appendChild(link);link.click();link.remove();URL.revokeObjectURL(href);
  }catch(e){toast.error(message(e))}
 }
 const publicationForm=<PublicationForm project={project} disabled={disabled} onDirty={setPublicationDirty} onSave={value=>perform('publication',{method:'PUT',body:JSON.stringify(value)},'Autore e copertina aggiornati')}/>;
 return <div className="sg-page sg-workspace">
  <header className="sg-page-header"><div><span className="sg-eyebrow">{profiles[project.form_data.profile]} · {config.roles[project.form_data.ai_role].label}</span><h1 className={hasTitle?undefined:"sg-topic-heading"}>{title}</h1><p>{project.form_data.target_words.toLocaleString('it-IT')} parole obiettivo · Lettori adulti · {project.validated?'Progetto approvato':'Progetto da approvare'}</p></div><div className="sg-actions"><Link to="/" onClick={e=>{if((dirty||publicationDirty)&&!window.confirm('Lasciare lo studio con modifiche non salvate?'))e.preventDefault()}}>Biblioteca</Link></div></header>
  {error&&<p className="sg-notice" role="alert">Connessione interrotta: {error}. Nuovo tentativo automatico in corso.</p>}
  <GenerationProgress project={project} onPause={()=>void perform('pause',write({}),'Pausa richiesta')}/>
  {!project.active&&lastProgress?.error&&<div className="sg-notice" role="alert"><strong>Operazione da riprendere</strong><p>{lastProgress.error}</p></div>}
  <nav className="sg-journey" aria-label="Fasi del saggio">{tabs.map(([key,label],i)=><button className={tab===key?'current':''} key={key} onClick={()=>chooseTab(key)} aria-current={tab===key?'step':undefined}><span>{i+1}</span>{label}</button>)}</nav>
  {tab==='project'&&<section>{!editingBrief&&publicationForm}{editingBrief?<BriefForm key={'brief-'+editingVersion} initial={project.form_data} config={config} saving={busy} submitLabel="Salva impostazioni" onSave={brief=>void perform('brief',{method:'PUT',body:JSON.stringify({brief,expected_version:editingVersion})},'Impostazioni salvate').then(ok=>{if(ok)setEditingBrief(false)})}/>:<div className="sg-card"><div className="sg-section-top"><h2>Il brief del libro</h2><button disabled={disabled} onClick={()=>guard(()=>{setEditingVersion(project.current_version);setEditingBrief(true)})}>Modifica impostazioni</button></div><dl className="sg-brief-summary"><dt>Tema</dt><dd>{project.form_data.topic}</dd><dt>Domanda</dt><dd>{project.form_data.question||'Da affinare con le domande'}</dd><dt>Tesi iniziale</dt><dd>{project.form_data.thesis||'Da definire nel progetto editoriale'}</dd><dt>Perimetro</dt><dd>{project.form_data.scope||'Da precisare'}</dd><dt>Metodo</dt><dd>{project.form_data.methodology||project.plan?.method||'Da definire'}</dd></dl><p className="sg-help">Cambiare profilo o direzione richiede una nuova approvazione del piano. I capitoli già scritti conservano le loro versioni.</p><button className="sg-text-button sg-danger" disabled={disabled} onClick={()=>{if(window.confirm('Eliminare questo saggio e i suoi materiali?')){void api('essays/'+id,{method:'DELETE'}).then(()=>navigate('/')).catch(e=>toast.error(e.message))}}}>Elimina progetto</button></div>}</section>}
  {tab==='questions'&&<section className="sg-card"><span className="sg-eyebrow">Chiarire la direzione</span><h2>Le domande giuste, prima di scrivere.</h2>
   {project.generated_questions.length===0?<><p>L’editor parte dal tuo brief e chiede solo ciò che può cambiare il libro.</p><button className="sg-primary" disabled={disabled} onClick={()=>void job('questions')}>Genera domande</button></>:<form onSubmit={e=>{e.preventDefault();void perform('answers',write({answers}),'Risposte salvate').then(ok=>{if(ok)chooseTab('plan')})}}>{project.generated_questions.map(q=><label className="sg-field" key={q.id}>{q.text}<textarea rows={3} value={answers[q.id]??project.answers[q.id]??''} onChange={e=>setAnswers(old=>({...old,[q.id]:e.target.value}))}/></label>)}<div className="sg-actions"><button className="sg-primary" disabled={disabled}>Salva e prosegui</button><button type="button" onClick={()=>chooseTab('plan')}>Prosegui senza rispondere</button></div></form>}
  </section>}
  {tab==='plan'&&<div className="sg-work-grid"><div>
   <section className="sg-card"><span className="sg-eyebrow">La direzione del libro</span><div className="sg-section-top"><h2>Progetto editoriale</h2>{project.plan&&!editingPlan&&<button disabled={disabled} onClick={()=>{setEditingVersion(project.current_version);setEditingPlan(true)}}>Modifica piano</button>}</div>
    {!project.plan?<><p>Tesi o domanda guida, ragioni, obiezioni e struttura. Le fonti disponibili entrano nel piano; le lacune restano dichiarate.</p><button className="sg-primary" disabled={disabled} onClick={()=>void job('draft')}>Prepara progetto editoriale</button></>:editingPlan?<PlanEditor initial={project.plan} sources={project.sources} locked={chapters.length>0} saving={busy} onCancel={()=>setEditingPlan(false)} onSave={plan=>void perform('plan',{method:'PUT',body:JSON.stringify({plan,expected_version:editingVersion})},'Piano salvato').then(ok=>{if(ok)setEditingPlan(false)})}/>:<>
     <h3>{project.plan.title}</h3>{project.plan.subtitle&&<p>{project.plan.subtitle}</p>}<blockquote className="sg-direction">{project.plan.direction}</blockquote>
     {project.plan.method&&<><h3>Metodo</h3><p>{project.plan.method}</p></>}
     {project.plan.definitions.length>0&&<details><summary>Definizioni</summary><ul>{project.plan.definitions.map((d,i)=><li key={i}>{d}</li>)}</ul></details>}
     <h3>Ragioni e obiezioni</h3>{claims.map((claim,i)=><details key={claim.id} className="sg-subcard"><summary>{i+1}. {claim.text}</summary><p><strong>Ragione:</strong> {claim.reason}</p>{claim.objection&&<p><strong>Obiezione:</strong> {claim.objection}</p>}{claim.response&&<p><strong>Risposta:</strong> {claim.response}</p>}{claim.gap&&<p className="sg-notice"><strong>Da documentare:</strong> {claim.gap}</p>}<p>{claim.evidence_ids.length} evidenze collegate</p></details>)}
     {project.plan.limits.length>0&&<details><summary>Limiti dichiarati</summary><ul>{project.plan.limits.map((limit,i)=><li key={i}>{limit}</li>)}</ul></details>}
     <div className="sg-actions">{project.validated?<span className="sg-approved"><Check size={16}/>Piano approvato</span>:<button className="sg-primary" disabled={disabled} onClick={()=>void perform('approve',write({expected_version:project.current_version}),'Piano approvato').then(ok=>{if(ok)chooseTab('outline')})}>Approva direzione e piano</button>}<button disabled={disabled||chapters.length>0} onClick={()=>void job('draft')}>Rigenera con i materiali attuali</button></div>
    </>}
   </section>
  </div><SourcePanel project={project} onChange={accept} onOpen={sourceId=>void openSource(sourceId)} onJob={kind=>void job(kind)}/></div>}
  {tab==='outline'&&<section className="sg-card"><div className="sg-section-top"><h2>L’indice ragionato</h2>{project.plan&&<button disabled={disabled} onClick={()=>{setEditingVersion(project.current_version);setTab('plan');setEditingPlan(true)}}>Modifica struttura</button>}</div>
   {!project.plan?<p>Prepara prima il progetto editoriale nella fase Argomenti e fonti.</p>:<><ol className="sg-outline">{project.plan.sections.map(section=><li key={section.id}><h3>{section.title}</h3><p>{section.purpose}</p><details><summary>Contenuto da sviluppare</summary><p>{section.description}</p></details><small>Circa {section.word_target.toLocaleString('it-IT')} parole · {section.claim_ids.length} argomenti</small></li>)}</ol><div className="sg-actions"><button className="sg-primary" disabled={disabled||!project.validated||project.writing_progress?.status==='completed'} onClick={()=>{setTab('manuscript');void job('book')}}>{chapters.length?'Riprendi scrittura':'Inizia scrittura'}</button>{!project.validated&&<span>Approva il progetto editoriale per iniziare.</span>}</div></>}
  </section>}
  {tab==='manuscript'&&<div className="sg-studio-grid"><aside className="sg-card sg-index"><h3>Manoscritto</h3><p>{project.words.toLocaleString('it-IT')} parole · circa {project.estimated_pages} pagine</p>
   {project.plan?.sections.map((section,i)=><button className={selected===i?'selected':''} key={section.id} disabled={!chapters.some(c=>c.section_id===section.id)} onClick={()=>guard(()=>setSelected(i))}><span>{i+1}</span>{section.title}{chapters.some(c=>c.section_id===section.id)&&<Check size={14}/>}</button>)}
   <div className="sg-actions"><button disabled={disabled||!project.validated||project.writing_progress?.status==='completed'} onClick={()=>void job('book')}>{chapters.length?'Riprendi scrittura':'Inizia scrittura'}</button></div>
  </aside><main>{chapter?<ChapterEditor key={chapter.section_id} chapter={chapter} project={project} onChange={accept} onOpenSource={sourceId=>void openSource(sourceId)} onDirty={setDirty}/>:<div className="sg-card sg-empty-small"><BookOpen size={32}/><h2>Il manoscritto appare qui.</h2><p>I capitoli diventano leggibili appena salvati. Puoi chiudere la pagina e ritrovare il lavoro nello studio.</p></div>}
   {project.bibliography.length>0&&<section className="sg-card"><h3>Bibliografia</h3>{project.bibliography.map(s=><p key={s.id}><button className="sg-citation" onClick={()=>void openSource(s.id)}>[{s.label}]</button> {s.text}</p>)}</section>}
  </main></div>}
  {tab==='review'&&<div className="sg-work-grid"><section className="sg-card"><div className="sg-section-top"><div><span className="sg-eyebrow">Argomentazione e chiarezza</span><h2>Revisione del saggio</h2></div><button className="sg-primary" disabled={disabled||chapters.length===0} onClick={()=>void job('review')}>{project.review?'Aggiorna revisione':'Avvia revisione'}</button></div>
   {!project.review?<p>Il rapporto segnala passaggi da migliorare, lacune documentali e problemi di metodo secondo il profilo scelto.</p>:<>{project.review.partial&&<p className="sg-notice">Revisione parziale: il manoscritto non è ancora completo.</p>}<p>{project.review.summary}</p>{project.review.strengths.length>0&&<><h3>Punti di forza</h3><ul>{project.review.strengths.map((strength,i)=><li key={i}>{strength}</li>)}</ul></>}<h3>Interventi proposti ({project.review.issues.length})</h3>{project.review.issues.map((issue,i)=><article className="sg-subcard" key={i}><span className={'sg-badge '+issue.severity}>{({blocking:'Da risolvere',important:'Importante',suggestion:'Suggerimento'} as Record<string,string>)[issue.severity]}</span>{issue.quote&&<blockquote>{issue.quote}</blockquote>}<p>{issue.explanation}</p><p><strong>Intervento:</strong> {issue.suggestion}</p>{issue.section_id&&<button onClick={()=>guard(()=>{const index=chapters.findIndex(c=>c.section_id===issue.section_id);if(index>=0)setSelected(index);setTab('manuscript')})}>Apri capitolo</button>}</article>)}</>}
  </section><aside>{publicationForm}<section className="sg-card"><h3>Copertina ed esportazioni</h3>{project.cover_image_path&&<img className="sg-cover-preview" src={'/api/essays/'+id+'/cover?v='+project.current_version+'-'+project.cover_progress?.updated_at} alt="Copertina del saggio"/>}<button disabled={disabled||!project.plan} onClick={()=>void job('cover')}>{project.cover_image_path?'Ricrea copertina':'Crea copertina'}</button><p className="sg-help">Stile: {({typographic:'tipografico',conceptual:'concettuale',photographic:'fotografico',illustrated:'illustrato'} as Record<string,string>)[project.form_data.cover_style]}. Modificabile nelle impostazioni.</p><h3>Scarica il libro</h3><div className="sg-actions">{['pdf','epub','docx'].map(format=><button disabled={chapters.length===0||dirty||publicationDirty} key={format} onClick={()=>void download(format)}>{format.toUpperCase()}</button>)}</div><p className="sg-help">Gli export includono autore, citazioni, bibliografia e quarta di copertina. Puoi scaricare una versione di lavoro anche prima della revisione finale.</p></section></aside></div>}
  <details className="sg-card sg-ledger"><summary>Consumi e documentazione · {project.usage.calls} richieste · {project.usage.converted_cost_eur==null?'Nessun costo misurato':(project.usage.coverage_complete?'Totale misurato: ':'Totale misurato parziale: ')+project.usage.converted_cost_eur.toFixed(3)+' €'}</summary><p>{project.reference_checks.citations} riferimenti nel testo · {project.reference_checks.evidence} estratti disponibili.</p>{project.usage.tool_cost_unknown&&<p className="sg-notice">Il totale non include eventuali costi del servizio di ricerca Google, che dipendono dal tuo piano.</p>}<div className="sg-table-wrap"><table><thead><tr><th>Fase</th><th>Modello</th><th>Input / output</th><th>Costo USD</th></tr></thead><tbody>{project.usage.events.map(event=><tr key={event.id}><td>{event.phase.replace('essay-','')}</td><td>{event.model}</td><td>{event.usage?event.usage.input_tokens+' / '+event.usage.output_tokens:'Non disponibile'}</td><td>{event.cost_usd==null?'Non quantificato':event.cost_usd.toFixed(5)}</td></tr>)}</tbody></table></div></details>
  {source&&<SourceDialog source={source} projectId={id} disabled={disabled} onClose={()=>setSource(null)} onUpdate={accept}/>}
 </div>;
}

export default function EssayApp(){
 const [config,setConfig]=useState<Config|null>(null);
 const [error,setError]=useState('');
 const [unsaved,setUnsaved]=useState(false);
 useEffect(()=>{void api<Config>('essay-config').then(setConfig).catch(e=>setError(e.message))},[]);
 const guardLink=(event:React.MouseEvent)=>{if(unsaved&&!window.confirm('Hai modifiche non salvate. Vuoi cambiare pagina?'))event.preventDefault()};
 return <BrowserRouter><div className="sg-app"><Toaster position="top-right" toastOptions={{style:{background:'#fbf8f3',color:'#163b39',border:'1px solid #d6d0c6'}}}/><header className="sg-navigation"><Link to="/" className="sg-brand" onClick={guardLink}><img src="/saggia-mark.svg" alt="" width={33} height={33}/><span>SaggIA</span></Link><nav aria-label="Navigazione principale"><Link to="/" onClick={guardLink}><LibraryIcon size={17}/>Opere</Link><Link to="/new" onClick={guardLink}><Plus size={17}/>Nuovo saggio</Link></nav><span className="sg-nav-note">Idee. Ragioni. Libri.</span></header><main className="sg-main">{config?<Routes><Route path="/" element={<EssayLibrary config={config}/>}/><Route path="/new" element={<NewEssay config={config}/>}/><Route path="/essay/:id" element={<Workspace config={config} onUnsaved={setUnsaved}/>}/><Route path="*" element={<div className="sg-page"><h1>Pagina non trovata</h1><Link to="/">Apri biblioteca</Link></div>}/></Routes>:error?<div className="sg-page"><h1>Lo studio non è raggiungibile</h1><p role="alert">{error}</p><button onClick={()=>window.location.reload()}>Riprova</button></div>:<Loading/>}</main><footer className="sg-footer"><span>SaggIA · Studio di saggistica per adulti</span><span>Archivio locale · Generazione e ricerca online</span></footer></div></BrowserRouter>;
}
