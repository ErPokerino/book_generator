import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ArrowLeft, List, Minus, Plus, ChevronLeft, ChevronRight } from 'lucide-react';
import { getCompleteBook, getManga, getCoverImageUrl, getMangaPageImageUrl } from '../api/client';
import { api, ESSAY_API, type Project } from '../essay/api';
import NotebookIllustration from './NotebookIllustration';
import AudioPlayer from './AudioPlayer';
import './WorkReader.css';

type Leaf = { title: string; text?: string; image?: string; chapterIndex?: number };
type Reading = { title: string; author: string; leaves: Leaf[]; incomplete: boolean };

export default function WorkReader() {
  const params = useParams();
  const id = params.id || params.sessionId || '';
  const kind = params.kind || 'book';
  const studio = kind === 'essay' ? `/essay/${id}` : kind === 'manga' ? `/comics?session=${id}` : `/studio/${id}`;
  const [reading, setReading] = useState<Reading | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [index, setIndex] = useState(0);
  const [toc, setToc] = useState(false);
  const [size, setSize] = useState(19);

  useEffect(() => {
    let cancelled = false;
    setReading(null); setError(''); setIndex(0);
    async function load() {
      let next: Reading;
      if (kind === 'essay') {
        const p = await api<Project>(`essays/${id}`);
        const title = p.form_data.title || p.plan?.title || p.form_data.topic;
        next = {title, author:p.form_data.author_name, incomplete:!p.writing_progress || p.writing_progress.status !== 'completed', leaves:[
          {title:'Copertina', image:p.cover_image_path ? `${ESSAY_API}essays/${id}/cover?v=${p.current_version}` : undefined},
          ...[...p.book_chapters].sort((a,b)=>a.section_index-b.section_index).map(c => ({title:c.title,text:c.display_content || c.content})),
          ...(p.bibliography.length ? [{title:'Bibliografia',text:p.bibliography.map(b => `${b.label} ${b.text}`).join('\n\n')}] : []),
        ]};
      } else if (kind === 'manga') {
        const p = await getManga(id);
        next = {title:p.title,author:'',incomplete:!p.is_complete,leaves:[
          {title:'Copertina',image:p.cover_image_url || undefined},
          ...p.pages.filter(p => p.status === 'completed').sort((a,b)=>a.page_number-b.page_number).map(p => ({title:`Tavola ${p.page_number}`,image:p.image_url || getMangaPageImageUrl(id,p.page_number)})),
          ...(p.back_cover_image_url ? [{title:'Retro copertina',image:p.back_cover_image_url}] : []),
        ]};
      } else if (kind === 'book') {
        const p = await getCompleteBook(id,true);
        next = {title:p.title,author:p.author,incomplete:p.is_complete===false,leaves:[{title:'Copertina',image:getCoverImageUrl(id)},...p.chapters.map((c,chapterIndex) => ({title:c.title,text:c.content,chapterIndex}))]};
      } else throw new Error('Tipo di opera non riconosciuto.');
      if (!cancelled) {
        setReading(next);
        try {const saved = Number(localStorage.getItem(`narrai.read.${kind}.${id}`) || 0);setIndex(Number.isFinite(saved) ? Math.max(0,Math.min(saved,next.leaves.length-1)) : 0);} catch { /* optional bookmark */ }
      }
    }
    void load().catch(e => {if (!cancelled) setError(e instanceof Error ? e.message : 'Lettura non disponibile');});
    return () => {cancelled = true;};
  }, [id,kind,retry]);

  useEffect(() => {
    if (!reading) return;
    try {localStorage.setItem(`narrai.read.${kind}.${id}`,String(index));} catch { /* optional bookmark */ }
    window.scrollTo({top:0,behavior:'instant'});
  }, [index,reading,id,kind]);

  useEffect(() => {
    const onKey = (e:KeyboardEvent) => {
      if (['INPUT','TEXTAREA','SELECT','BUTTON'].includes((e.target as HTMLElement)?.tagName)) return;
      if (e.key === 'ArrowRight') setIndex(i => Math.min(i+1,(reading?.leaves.length || 1)-1));
      if (e.key === 'ArrowLeft') setIndex(i => Math.max(i-1,0));
      if (e.key === 'Escape') setToc(false);
    };
    window.addEventListener('keydown',onKey);return () => window.removeEventListener('keydown',onKey);
  }, [reading]);

  const leaf = reading?.leaves[index];
  return <div className={`work-reader ${kind==='manga'?'work-reader-comic':''}`}>
    <header className="work-reader-toolbar">
      <Link to="/library" aria-label="Torna alle opere" className="reader-back"><ArrowLeft size={18}/><span>Opere</span></Link>
      <span className="reader-book-title">{reading?.title || 'Lettura'}</span>
      <div className="reader-toolbar-actions"><Link to={studio}>Apri studio</Link><button className="ui-icon-button" type="button" aria-label="Indice" aria-expanded={toc} onClick={()=>setToc(v=>!v)}><List size={20}/></button></div>
    </header>
    {toc && reading && <nav className="work-reader-toc" aria-label="Indice dell’opera">{reading.leaves.map((l,i)=><button type="button" key={i} aria-current={i===index?'page':undefined} onClick={()=>{setIndex(i);setToc(false);}}>{l.title}</button>)}</nav>}
    {error ? <div className="reader-empty" role="alert"><h1>La lettura non è disponibile</h1><p>{error}</p><button type="button" className="action-btn" onClick={()=>setRetry(v=>v+1)}>Riprova</button><Link to={studio}>Apri studio</Link></div> : !reading ? <p className="reader-empty" role="status">Apro l’opera…</p> : <>
      {reading.incomplete && <p className="reader-progress-note">Questa opera è ancora in lavorazione. Stai leggendo le pagine disponibili.</p>}
      <main className="work-reader-sheet" style={{fontSize:size}}>
        {index===0 ? <div className="reader-frontispiece">
          {leaf?.image ? <img src={leaf.image} alt={`Copertina di ${reading.title}`} onError={e=>{e.currentTarget.hidden=true;}}/> : <NotebookIllustration medium={kind==='essay'?'essay':kind==='manga'?'manga':'book'}/>}
          <h1>{reading.title}</h1>{reading.author && <p>{reading.author}</p>}
          {reading.leaves.length===1 && <p>Le prime pagine devono ancora essere scritte. <Link to={studio}>Continua nello studio</Link>.</p>}
        </div> : leaf?.image ? <img className="reader-comic-page" src={leaf.image} alt={leaf.title}/> : <article className="reader-prose"><span className="notebook-eyebrow">{leaf?.title==='Bibliografia'?'Fonti':`Capitolo ${index}`}</span><h1>{leaf?.title}</h1><ReactMarkdown remarkPlugins={[remarkGfm]}>{leaf?.text || ''}</ReactMarkdown>{kind==='book' && leaf?.chapterIndex!=null && <AudioPlayer sessionId={id} type="chapter" chapterIndex={leaf.chapterIndex}/>}</article>}
      </main>
      <footer className="work-reader-controls">
        <button type="button" className="ui-icon-button" aria-label="Pagina precedente" disabled={index===0} onClick={()=>setIndex(i=>i-1)}><ChevronLeft size={21}/></button>
        <span>{index+1} / {reading.leaves.length}</span>
        {kind!=='manga' && <div className="reader-font-controls"><button type="button" className="ui-icon-button" aria-label="Riduci testo" disabled={size<=15} onClick={()=>setSize(s=>s-1)}><Minus size={15}/></button><span>Aa</span><button type="button" className="ui-icon-button" aria-label="Ingrandisci testo" disabled={size>=28} onClick={()=>setSize(s=>s+1)}><Plus size={15}/></button></div>}
        <button type="button" className="ui-icon-button" aria-label="Pagina successiva" disabled={index>=reading.leaves.length-1} onClick={()=>setIndex(i=>i+1)}><ChevronRight size={21}/></button>
      </footer>
    </>}
  </div>;
}
