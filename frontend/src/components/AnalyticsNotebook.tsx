import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import PageHeader from './ui/PageHeader';
import SegmentedControl from './ui/SegmentedControl';
import NotebookIllustration from './NotebookIllustration';
import './AnalyticsNotebook.css';

type Kind = 'book'|'essay'|'manga';
type Group = {name:string;calls:number;measured_calls:number;unknown_calls:number;cost_eur:number|null;input_tokens:number;output_tokens:number};
interface Stats {
  total:number;completed:number;active:number;paused:number;drafts:number;words:number;comic_pages:number;
  cost_eur:number|null;cost_complete_works:number;cost_partial_works:number;
  comic_formats:Record<string,number>;
  types:{type:Kind;label:string;works:number;completed:number;words:number;chapters:number;pages:number;cost_eur:number|null}[];
  months:{month:string;works:number}[];phases:Group[];models:Group[];
  recent:{session_id:string;content_type:Kind;title:string;status:string;updated_at:string;word_count:number;completed_pages:number}[];
}
const number = (n:number) => n.toLocaleString('it-IT');
const money = (n:number|null) => n==null?'—':new Intl.NumberFormat('it-IT',{style:'currency',currency:'EUR',minimumFractionDigits:2,maximumFractionDigits:n>0 && n<.01?4:2}).format(n);
const statuses:Record<string,string> = {draft:'Bozza',outline:'Struttura',writing:'In scrittura',paused:'In pausa',complete:'Completata'};
const phaseNames:Record<string,string> = {questions:'Domande',draft:'Progetto',outline:'Struttura',chapters:'Scrittura',book:'Scrittura',writing:'Scrittura',research:'Ricerca',review:'Revisione',revision:'Revisione',critique:'Valutazione',cover:'Copertina',manga_planning:'Storyboard',manga_pages:'Tavole',manga_cover:'Copertina fumetto',manga_back_cover:'Retro copertina',memory:'Memoria',plan:'Progetto',source:'Fonti',tts:'Voce'};
Object.assign(phaseNames, {'essay-questions':'Domande dei saggi','essay-plan':'Struttura dei saggi','essay-chapters':'Scrittura dei saggi','essay-review':'Revisione dei saggi','essay-revision':'Correzione dei saggi','essay-cover':'Copertine dei saggi','essay-research':'Ricerca dei saggi','manga-planning':'Storyboard','manga_images':'Disegno dei fumetti'});
Object.assign(phaseNames, {'chapter-generation':'Scrittura della narrativa','narrative-memory':'Continuità narrativa','narrative-memory-repair':'Correzione della continuità'});

export default function AnalyticsNotebook() {
  const [kind,setKind] = useState('all');
  const [data,setData] = useState<Stats|null>(null);
  const [error,setError] = useState('');
  const [retry,setRetry] = useState(0);
  useEffect(()=>{
    const controller = new AbortController();
    setData(null);setError('');
    async function load() {
      const response = await fetch(`/api/works/analytics${kind==='all'?'':`?content_type=${kind}`}`,{signal:controller.signal});
      if (!response.ok) throw new Error('Non riesco a leggere le analisi. Riprova tra poco.');
      const next = await response.json();
      if (!controller.signal.aborted) setData(next);
    }
    void load().catch(e=>{if (!controller.signal.aborted) setError(e instanceof Error?e.message:'Analisi non disponibile');});
    return ()=>controller.abort();
  },[kind,retry]);
  const maxWorks = Math.max(1,...(data?.months?.map(m=>m.works) || []));
  const maxCost = Math.max(.0001,...(data?.phases?.map(p=>p.cost_eur || 0) || []));
  return <div className="page-shell analytics-notebook">
    <PageHeader title="Analisi" description="Uno sguardo al lavoro che prende forma sul tuo tavolo." />
    <SegmentedControl name="analytics-kind" ariaLabel="Tipo di opera nelle analisi" value={kind} options={[{value:'all',label:'Tutte'},{value:'book',label:'Narrativa'},{value:'essay',label:'Saggi'},{value:'manga',label:'Fumetti'}]} onChange={setKind}/>
    {error ? <div className="notebook-panel" role="alert"><p>{error}</p><button type="button" className="action-btn" onClick={()=>setRetry(v=>v+1)}>Riprova</button></div> : !data ? <p role="status" className="analytics-loading">Raccolgo le tue pagine…</p> : !data.total ? <div className="analytics-empty"><NotebookIllustration medium="book"/><h2>Un foglio ancora bianco</h2><p>Le analisi compariranno quando ci saranno opere in questo percorso.</p><Link to={kind==='essay'?'/new/essay':kind==='manga'?'/comics':'/new'} className="action-btn">Crea un’opera</Link></div> : <>
      <div className="analytics-summary">
        <article><span>Opere sul tavolo</span><strong>{number(data.total)}</strong><small>{data.completed} completate · {data.drafts} in preparazione</small></article>
        <article><span>In lavorazione</span><strong>{number(data.active)}</strong><small>{data.paused} in pausa</small></article>
        <article><span>{kind==='manga'?'Tavole disegnate':'Parole scritte'}</span><strong>{number(kind==='manga'?data.comic_pages:data.words)}</strong><small>{kind==='manga'?'Tavole pronte · copertine escluse':'Narrativa e saggi · contenuto salvato'}</small></article>
        <article><span>{kind==='all'?'Tavole disegnate':kind==='manga'?'Graphic Novel':'Capitoli scritti'}</span><strong>{number(kind==='all'?data.comic_pages:kind==='manga'?(data.comic_formats.graphic_novel || 0):data.types.reduce((n,t)=>n+t.chapters,0))}</strong><small>{kind==='all'?'Manga e Graphic Novel · copertine escluse':kind==='manga'?`${data.comic_formats.manga || 0} manga sul tavolo`:'Capitoli salvati, anche in opere incomplete'}</small></article>
      </div>
      <section className="analytics-cost notebook-panel">
        <div><span className="notebook-eyebrow">Consumi API registrati</span><h2>{money(data.cost_eur)}</h2><p>{data.cost_partial_works ? `Dati parziali per ${data.cost_partial_works} ${data.cost_partial_works===1?'opera':'opere'} su ${data.total}. Il totale include solo le chiamate quantificabili.` : 'Dati disponibili per tutte le opere di questa selezione.'}</p></div>
        <div className="analytics-cost-note"><span className="handwritten">ogni pagina ha il suo percorso.</span><p>Stima dai consumi del provider e dai listini salvati per ogni chiamata. Conversione EUR al cambio configurato; crediti, sconti e tasse esclusi. Le valutazioni di PDF esterni non sono associate alle opere.</p></div>
      </section>
      <div className="analytics-types">{data.types.filter(t=>kind==='all'||kind===t.type).map(t=><article className="notebook-panel" key={t.type}><NotebookIllustration medium={t.type}/><div><h2>{t.label}</h2><strong>{number(t.works)} {t.works===1?'opera':'opere'}</strong><p>{t.completed} completate</p><p>{t.type==='manga'?`${number(t.pages)} tavole`:`${number(t.words)} parole · ${t.chapters} capitoli`}</p><small>Consumi registrati {money(t.cost_eur)}</small></div></article>)}</div>
      <div className="analytics-two-columns">
        <section className="notebook-panel"><h2>Le idee nel tempo</h2><p className="analytics-caption">Opere create per mese</p><div className="analytics-months">{data.months.slice(-12).map(m=><div className="analytics-bar-row" key={m.month}><span>{new Date(`${m.month}-01T12:00:00`).toLocaleDateString('it-IT',{month:'short',year:'2-digit'})}</span><div className="analytics-bar-track"><div style={{width:`${m.works/maxWorks*100}%`}}/></div><strong>{m.works}</strong></div>)}</div></section>
        <section className="notebook-panel"><h2>Dove va il lavoro</h2><p className="analytics-caption">Consumi quantificabili per fase</p>{!data.phases.length?<p>Le opere presenti non hanno ancora un registro delle chiamate API.</p>:data.phases.map(p=><div className="analytics-phase" key={p.name}><div><span>{phaseNames[p.name] || p.name.replace(/_/g,' ')}</span><strong>{money(p.cost_eur)}</strong></div><div className="analytics-bar-track"><div style={{width:`${(p.cost_eur || 0)/maxCost*100}%`}}/></div><small>{p.calls} chiamate{p.unknown_calls>0?` · ${p.unknown_calls} con costo incompleto`:''}</small></div>)}</section>
      </div>
      <section className="notebook-panel"><h2>Modelli al lavoro</h2><p className="analytics-caption">Chiamate e token misurati; i costi mancanti restano segnalati.</p>{data.models.length ? <div className="analytics-table-scroll"><table><thead><tr><th>Modello</th><th>Chiamate</th><th>Token in / out</th><th>Consumi</th><th>Copertura</th></tr></thead><tbody>{data.models.map(m=><tr key={m.name}><td>{m.name}</td><td>{number(m.calls)}</td><td>{number(m.input_tokens)} / {number(m.output_tokens)}</td><td>{money(m.cost_eur)}</td><td>{m.unknown_calls?`${m.unknown_calls} chiamate incomplete`:'Disponibile'}</td></tr>)}</tbody></table></div>:<p>I dati per modello saranno disponibili per le nuove chiamate registrate.</p>}</section>
      <section className="analytics-recent notebook-panel"><h2>Le ultime pagine sul tavolo</h2>{data.recent.map(p=><Link key={`${p.content_type}-${p.session_id}`} to={p.content_type==='book'?`/book/${p.session_id}`:`/read/${p.content_type}/${p.session_id}`}><div><strong>{p.title}</strong><span>{statuses[p.status] || p.status} · {p.content_type==='manga'?`${p.completed_pages} tavole`:`${number(p.word_count)} parole`}</span></div><time dateTime={p.updated_at}>{new Date(p.updated_at).toLocaleDateString('it-IT')}</time></Link>)}</section>
    </>}
  </div>;
}
