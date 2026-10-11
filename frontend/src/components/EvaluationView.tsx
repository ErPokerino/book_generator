import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { type LibraryEntry, type LiteraryCritique, getLibrary } from '../api/client';
import PageHeader from './ui/PageHeader';
import SegmentedControl from './ui/SegmentedControl';
import Button from './ui/Button';
import CritiqueBlock from './CritiqueBlock';
import './BenchmarkView.css';
import './EvaluationView.css';

type Kind = 'book'|'essay'|'manga';
const rubrics:Record<Kind,string[]> = {
  book:['Struttura e ritmo','Personaggi e punto di vista','Stile e dialoghi','Coerenza e originalità'],
  essay:['Domanda e tesi','Argomentazione e obiezioni','Evidenze e fonti','Metodo e limiti','Chiarezza espositiva'],
  manga:['Narrazione visiva','Regia e leggibilità delle vignette','Disegno e continuità','Dialoghi e lettering','Arco narrativo'],
};
export default function EvaluationView() {
  const [params] = useSearchParams();
  const initialType = params.get('type');
  const [kind,setKind] = useState<Kind>(initialType==='essay'||initialType==='manga'?initialType:'book');
  const [source,setSource] = useState(params.get('session')?'library':'pdf');
  const [works,setWorks] = useState<LibraryEntry[]>([]);
  const [selected,setSelected] = useState(params.get('session') || '');
  const [file,setFile] = useState<File|null>(null);
  const [title,setTitle] = useState('');
  const [author,setAuthor] = useState('');
  const [loading,setLoading] = useState(false);
  const [libraryLoading,setLibraryLoading] = useState(false);
  const [error,setError] = useState('');
  const [libraryError,setLibraryError] = useState('');
  const [retry,setRetry] = useState(0);
  const [critique,setCritique] = useState<LiteraryCritique|null>(null);
  const request = useRef<AbortController|null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  useEffect(()=>()=>request.current?.abort(),[]);
  useEffect(()=>{
    const controller = new AbortController();
    setLibraryLoading(true);setLibraryError('');setWorks([]);
    async function load() {
      const all:LibraryEntry[] = [];
      let more = true;
      while (more) {
        const batch = await getLibrary({content_type:kind,skip:all.length,limit:200},controller.signal);
        all.push(...batch.books);more=!!batch.has_more && !!batch.books.length;
      }
      if (!controller.signal.aborted) setWorks(all);
    }
    void load().catch(e=>{if (!controller.signal.aborted) setLibraryError(e instanceof Error?e.message:'Biblioteca non disponibile');}).finally(()=>{if(!controller.signal.aborted)setLibraryLoading(false);});
    return ()=>controller.abort();
  },[kind,retry]);
  const work = works.find(w=>w.session_id===selected);
  const ready = source==='pdf' ? !!file : !!work && !work.active && (kind==='manga' ? !!work.completed_pages : work.completed_chapters>0);
  const changeKind = (value:string) => {setKind(value as Kind);setSelected('');setCritique(null);setError('');};
  async function evaluate(e:React.FormEvent) {
    e.preventDefault();if(!ready||loading)return;
    const controller=new AbortController();request.current=controller;
    const timeout=window.setTimeout(()=>controller.abort(),10*60*1000);
    setLoading(true);setError('');setCritique(null);
    try {
      let body:FormData|undefined;
      if(source==='pdf'&&file){body=new FormData();body.append('file',file);body.append('work_type',kind);if(title.trim())body.append('title',title.trim());if(author.trim())body.append('author',author.trim());}
      const url=source==='pdf'?'/api/critique/analyze-pdf':`/api/critique/analyze-work/${kind}/${encodeURIComponent(selected)}`;
      const response=await fetch(url,{method:'POST',body,signal:controller.signal});
      const result=await response.json();
      if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:'La valutazione non è stata completata.');
      if(!controller.signal.aborted)setCritique(result);
    } catch(e) {
      if(request.current===controller)setError(controller.signal.aborted?'La valutazione ha superato il tempo di attesa.':e instanceof Error?e.message:'Errore nella valutazione.');
    } finally {window.clearTimeout(timeout);if(request.current===controller){setLoading(false);request.current=null;}}
  }
  return <div className="page-shell evaluation-view">
    <PageHeader title="Valuta" description="Un secondo sguardo alla tua opera, con i criteri adatti alla sua forma."/>
    <SegmentedControl name="evaluation-kind" ariaLabel="Formato da valutare" value={kind} options={[{value:'book',label:'Narrativa'},{value:'essay',label:'Saggio'},{value:'manga',label:'Fumetto'}]} onChange={value=>{if(!loading)changeKind(value);}}/>
    <section className="evaluation-rubric"><span className="notebook-eyebrow">Su cosa si concentra la lettura</span><ul>{rubrics[kind].map(r=><li key={r}>{r}</li>)}</ul>{kind==='manga'&&<p>Il modello legge anche le immagini delle tavole e valuta il linguaggio di Manga o Graphic Novel.</p>}</section>
    <form className="evaluation-form notebook-panel" onSubmit={evaluate}>
      <fieldset disabled={loading}>
        <legend>Scegli l’opera</legend>
        <div className="evaluation-source"><label><input type="radio" name="evaluation-source" checked={source==='pdf'} onChange={()=>{setSource('pdf');setCritique(null);setError('');}}/> Carica un PDF</label><label><input type="radio" name="evaluation-source" checked={source==='library'} onChange={()=>{setSource('library');setCritique(null);setError('');}}/> Dal tuo tavolo</label></div>
        {source==='pdf'?<>
          <label className="evaluation-file">File PDF<input ref={fileInput} type="file" accept=".pdf,application/pdf" onChange={e=>{const f=e.target.files?.[0]||null;setCritique(null);setError('');if(f&&(!f.name.toLowerCase().endsWith('.pdf')||f.size>50*1024*1024||!f.size)){setFile(null);e.target.value='';setError('Scegli un PDF non vuoto, fino a 50 MB.');return;}setFile(f);}}/></label>
          <div className="evaluation-fields"><label>Titolo (opzionale)<input value={title} onChange={e=>{setTitle(e.target.value);setCritique(null);}} placeholder="Titolo dell’opera"/></label><label>Autore (opzionale)<input value={author} onChange={e=>{setAuthor(e.target.value);setCritique(null);}} placeholder="Nome dell’autore"/></label></div>
        </>:<>
          {libraryError?<p role="alert">{libraryError} <button type="button" onClick={()=>setRetry(v=>v+1)}>Riprova</button></p>:libraryLoading?<p role="status">Apro la biblioteca…</p>:!works.length?<p>Non ci sono opere di questo formato sul tuo tavolo.</p>:<label>Opera<select value={selected} onChange={e=>{setSelected(e.target.value);setCritique(null);setError('');}}><option value="">Scegli un’opera</option>{works.map(w=><option key={w.session_id} value={w.session_id}>{w.title}</option>)}</select></label>}
          {work&&!ready&&<p>La valutazione richiede almeno {kind==='manga'?'una tavola':'un capitolo'} e la lavorazione in pausa.</p>}
        </>}
      </fieldset>
      <p className="evaluation-note">La valutazione usa il modello AI configurato e comporta consumi API. Il risultato resta in questa pagina; per un’opera del tavolo i consumi sono registrati nelle sue analisi. Il voto va interpretato insieme ai commenti e al formato.</p>
      <Button type="submit" disabled={!ready||loading}>{loading?'Valutazione in corso…':'Valuta l’opera'}</Button>
      {loading&&<p role="status">Leggo il PDF e preparo il parere editoriale. Può richiedere alcuni minuti.</p>}
      {error&&<p role="alert" className="evaluation-error">{error}</p>}
    </form>
    {critique&&<div className="evaluation-result"><CritiqueBlock critique={critique}/>{!!critique.criteria?.length&&<section className="notebook-panel"><h2>Uno sguardo ai singoli criteri</h2>{critique.criteria.map(c=><article className="evaluation-criterion" key={c.name}><h3>{c.name}<span>{c.score.toFixed(1)} / 10</span></h3><p>{c.explanation}</p></article>)}</section>}</div>}
  </div>;
}
