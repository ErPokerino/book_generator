import {useEffect,useRef,useState} from 'react';
import {Link} from 'react-router-dom';
import {ArrowRight,BookOpen,Feather,Plus,Search,Trash2} from 'lucide-react';
import toast from 'react-hot-toast';
import {api,Config,LibraryItem} from './api';

const profiles:Record<string,string>={argumentative:'Argomentativo',popular:'Divulgativo',academic:'Accademico'};
const statuses:Record<string,string>={draft:'In preparazione',planned:'Piano pronto',pending:'In coda',running:'Scrittura in corso',paused:'In pausa',completed:'Manoscritto completo',failed:'Da riprendere'};
const euros=new Intl.NumberFormat('it-IT',{style:'currency',currency:'EUR',minimumFractionDigits:3,maximumFractionDigits:3});

export function EssayLibrary({config}:{config:Config}){
 const [items,setItems]=useState<LibraryItem[]|null>(null);
 const [error,setError]=useState('');
 const [search,setSearch]=useState('');
 const [filter,setFilter]=useState('');
 const [removing,setRemoving]=useState<LibraryItem|null>(null);
 const [deleting,setDeleting]=useState(false);
 const [deleteError,setDeleteError]=useState('');
 const dialog=useRef<HTMLElement>(null);
 const cancel=useRef<HTMLButtonElement>(null);
 const load=()=>{setError('');void api<LibraryItem[]>('essays').then(setItems).catch(e=>setError(e.message))};
 useEffect(load,[]);
 useEffect(()=>{
  if(!removing)return;
  const previous=document.activeElement as HTMLElement;
  cancel.current?.focus();
  return()=>previous?.focus();
 },[removing]);
 const shown=(items||[]).filter(item=>(!filter||item.profile===filter)&&[item.title,item.topic].join(' ').toLowerCase().includes(search.toLowerCase()));
 const close=()=>{if(!deleting){setRemoving(null);setDeleteError('')}};
 async function remove(){
  if(!removing||deleting)return;
  setDeleting(true);setDeleteError('');
  try{
   await api('essays/'+encodeURIComponent(removing.id),{method:'DELETE'});
   const id=removing.id;
   setItems(old=>(old||[]).filter(item=>item.id!==id));
   try{
    for(const key of Object.keys(localStorage)){
     if(key==='saggia.tab.'+id||key.startsWith('saggia.chapter.'+id+'.'))localStorage.removeItem(key);
    }
   }catch{/* The server already removed the project. */}
   setRemoving(null);toast.success('Libro eliminato');
  }catch(e){setDeleteError((e as Error).message)}finally{setDeleting(false)}
 }
 return <div className="sg-page">
  <header className="sg-page-header"><div><span className="sg-eyebrow">La tua biblioteca</span><h1>Le idee prendono forma.</h1><p>Un luogo per costruire ragioni, confrontare fonti e scrivere libri.</p></div><Link className="sg-primary sg-button-link" to="/new"><Plus size={18}/>Nuovo saggio</Link></header>
  {!config.api_key_ready&&<p className="sg-notice">Puoi preparare i progetti. Per generare testi e ricercare fonti, configura la chiave Gemini nel file .env.</p>}
  {error?<div className="sg-card"><p role="alert">{error}</p><button onClick={load}>Riprova</button></div>:items===null?<div className="sg-loading" role="status">Caricamento della biblioteca…</div>:items.length===0?<section className="sg-empty"><div className="sg-empty-mark"><Feather size={38}/></div><span className="sg-eyebrow">Il primo libro comincia da una domanda</span><h2>Quale idea vuoi approfondire?</h2><p>Scegli il tipo di saggio e il modo di lavorare con l’AI.<br/>La posizione e il percorso restano nelle tue mani.</p><Link className="sg-primary sg-button-link" to="/new">Crea il tuo primo saggio <ArrowRight size={18}/></Link><div className="sg-profile-note"><span>Argomentativo</span><span>Divulgativo</span><span>Accademico</span></div></section>:<>
   <div className="sg-filters"><label><Search size={17}/><input aria-label="Cerca nei saggi" placeholder="Cerca titolo o tema" value={search} onChange={e=>setSearch(e.target.value)}/></label><select aria-label="Filtra per tipo" value={filter} onChange={e=>setFilter(e.target.value)}><option value="">Tutti i saggi</option>{Object.entries(profiles).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></div>
   <div className="sg-library-grid">{shown.map(item=><article key={item.id} className="sg-book-card" aria-label={item.title}>
    <div className="sg-book-spine"><BookOpen size={26}/><span>{profiles[item.profile]}</span></div>
    <div className="sg-book-info"><span className="sg-badge">{statuses[item.status]||item.status}</span><h2><Link to={'/essay/'+item.id}>{item.title}</Link></h2><p>{item.topic}</p>
     <dl className="sg-book-metrics"><div><dt>{item.pdf_pages!=null?'Pagine PDF':'Pagine stimate'}</dt><dd>{(item.pdf_pages??item.estimated_pages??Math.ceil(item.words/250)).toLocaleString('it-IT')}</dd></div><div><dt>Costo generazione</dt><dd>{item.generation_cost_eur==null?(item.generation_calls?'Non disponibile':'Non ancora generato'):euros.format(item.generation_cost_eur)}{item.generation_cost_eur!=null&&!item.cost_coverage_complete&&<span className="sg-cost-partial">parziale</span>}</dd></div></dl>
     {item.generation_calls>0&&!item.cost_coverage_complete&&<p className="sg-book-cost-note">Totale misurato: alcuni costi non sono quantificati.</p>}
     <small>{item.words.toLocaleString('it-IT')} parole · Aggiornato il {new Date(item.updated_at).toLocaleDateString('it-IT')}</small>
     <div className="sg-book-actions"><Link className="sg-open" to={'/essay/'+item.id}>Apri studio <ArrowRight size={16}/></Link><button className="sg-text-button sg-danger" aria-label={'Elimina '+item.title} disabled={item.active} title={item.active?'Attendi la pausa o la fine della generazione per eliminare il libro.':undefined} onClick={()=>{setDeleteError('');setRemoving(item)}}><Trash2 size={15}/>Elimina</button></div>
    </div>
   </article>)}</div>{shown.length===0&&<p>Nessun saggio corrisponde ai filtri.</p>}
  </>}
  {removing&&<div className="sg-dialog-backdrop" onClick={close}><section ref={dialog} className="sg-dialog sg-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="delete-book-title" aria-describedby="delete-book-description" onClick={e=>e.stopPropagation()} onKeyDown={e=>{
   if(e.key==='Escape')close();
   if(e.key==='Tab'){
    const nodes=Array.from(dialog.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')||[]);
    if(e.shiftKey&&document.activeElement===nodes[0]){e.preventDefault();nodes[nodes.length-1]?.focus()}
    else if(!e.shiftKey&&document.activeElement===nodes[nodes.length-1]){e.preventDefault();nodes[0]?.focus()}
   }
  }}><span className="sg-eyebrow">Gestione delle opere</span><h2 id="delete-book-title">Eliminare questo libro?</h2><p className="sg-delete-book-name">{removing.title}</p><p id="delete-book-description">Il progetto, i capitoli, lo storico e i materiali associati saranno eliminati definitivamente.</p>{deleteError&&<p role="alert" className="sg-error-inline">{deleteError}</p>}<div className="sg-actions"><button ref={cancel} disabled={deleting} onClick={close}>Annulla</button><button className="sg-delete-confirm" disabled={deleting} onClick={()=>void remove()}>{deleting?'Eliminazione…':'Elimina definitivamente'}</button></div></section></div>}
 </div>;
}
