import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useBlocker, useParams } from 'react-router-dom';
import { ArrowLeft, BookOpen, Check, Feather, History, List, NotebookPen, Pause, Play, Save } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getStudio, getRevisions, pauseWriting, saveChapter, rebuildMemory, type StudioData, type ChapterRevision } from '../api/studio';
import { resumeBookGeneration, startBookGeneration } from '../api/client';
import ExportDropdown from './ExportDropdown';
import './ManuscriptStudio.css';

const money = (value: number | null, currency: string) => value == null ? 'Da verificare' : new Intl.NumberFormat('it-IT', { style: 'currency', currency, minimumFractionDigits: 4, maximumFractionDigits: 4 }).format(value);
const labels: Record<string, string> = { complete: 'Manoscritto completo', writing: 'Scrittura in corso', paused: 'In pausa', outline: 'Pronto per la scrittura', draft: 'Progetto in preparazione' };
type Pane = 'outline' | 'manuscript' | 'notes';

export default function ManuscriptStudio() {
  const { sessionId = '' } = useParams();
  const [data, setData] = useState<StudioData | null>(null);
  const [selected, setSelected] = useState(0);
  const [text, setText] = useState('');
  const [baseHash, setBaseHash] = useState('');
  const [dirty, setDirty] = useState(false);
  const dirtyRef = useRef(false);
  dirtyRef.current = dirty;
  const [editing, setEditing] = useState(false);
  const [pane, setPane] = useState<Pane>('manuscript');
  const [noteTab, setNoteTab] = useState<'facts' | 'costs' | 'revisions'>('facts');
  const [revisions, setRevisions] = useState<ChapterRevision[]>([]);
  const [revision, setRevision] = useState<ChapterRevision | null>(null);
  const [error, setError] = useState('');
  const [connectionError, setConnectionError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const editorRef = useRef<HTMLTextAreaElement>(null);
  const blocker = useBlocker(dirty || busy);
  const chapter = data?.chapters.find(c => c.section_index === selected);
  const section = data?.sections.find(s => s.section_index === selected);
  const writingActive = data?.jobs.some(j => j.kind === 'book' && ['pending', 'running'].includes(j.status)) || false;
  const active = data?.jobs.some(j => ['pending', 'running'].includes(j.status)) || false;
  const canEdit = !!chapter && !active;

  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function poll() {
      try {
        const next = await getStudio(sessionId, controller.signal);
        if (!disposed) { setData(next); setConnectionError(''); }
      } catch (e) {
        if (!disposed) setConnectionError(e instanceof Error ? e.message : 'Impossibile caricare il manoscritto');
      } finally {
        if (!disposed) timer = setTimeout(poll, 4000);
      }
    }
    setData(null); setDirty(false); setEditing(false); setSelected(0);
    void poll();
    return () => { disposed = true; controller.abort(); clearTimeout(timer); };
  }, [sessionId, refreshKey]);

  useEffect(() => {
    if (!dirtyRef.current) { setText(chapter?.content || ''); setBaseHash(chapter?.content_hash || ''); }
  }, [chapter?.content, chapter?.content_hash, selected]);

  useEffect(() => {
    if (!dirty) return;
    const prevent = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener('beforeunload', prevent);
    return () => window.removeEventListener('beforeunload', prevent);
  }, [dirty]);

  useEffect(() => {
    let disposed = false;
    setRevision(null); setRevisions([]);
    if (noteTab === 'revisions' && chapter) {
      getRevisions(sessionId, selected).then(rows => { if (!disposed) setRevisions(rows); })
        .catch(e => { if (!disposed) setError(e.message); });
    }
    return () => { disposed = true; };
  }, [noteTab, sessionId, selected, chapter?.content_hash]);

  const save = useCallback(async () => {
    if (!dirty || busy) return;
    setBusy(true); setError('');
    try {
      const next = await saveChapter(sessionId, selected, text, baseHash);
      setData(next); setDirty(false); setNotice('Revisione salvata. La memoria dei capitoli successivi sarà aggiornata alla ripresa.');
      setBaseHash(next.chapters.find(c => c.section_index === selected)?.content_hash || '');
    } catch (e) { setError(e instanceof Error ? e.message : 'Salvataggio non riuscito'); }
    finally { setBusy(false); }
  }, [dirty, busy, sessionId, selected, text, baseHash]);

  useEffect(() => {
    const keyboardSave = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 's') { event.preventDefault(); void save(); }
    };
    window.addEventListener('keydown', keyboardSave);
    return () => window.removeEventListener('keydown', keyboardSave);
  }, [save]);

  async function generate() {
    setBusy(true); setError('');
    try {
      if (data?.status === 'paused') await resumeBookGeneration(sessionId);
      else await startBookGeneration({ session_id: sessionId });
      setData(await getStudio(sessionId)); setNotice('Scrittura avviata. Puoi chiudere questa pagina: il lavoro prosegue nel backend.');
    } catch (e) { setError(e instanceof Error ? e.message : 'Avvio non riuscito'); }
    finally { setBusy(false); }
  }

  function select(index: number) {
    if (dirty || busy) { setNotice('Attendi il salvataggio oppure salva o annulla le modifiche prima di cambiare capitolo.'); return; }
    setSelected(index); setEditing(false); setPane('manuscript'); setNotice('');
  }

  function revealEvidence(evidence: string) {
    setPane('manuscript');
    if (!canEdit) return;
    setEditing(true);
    setTimeout(() => {
      const start = text.indexOf(evidence); // DOM selection uses UTF-16, unlike Python offsets.
      if (start >= 0) { editorRef.current?.focus(); editorRef.current?.setSelectionRange(start, start + evidence.length); }
    }, 0);
  }

  if (!data) return <main className="studio-loading"><Feather size={32} /><p role={connectionError ? 'alert' : 'status'}>{connectionError || 'Apertura del manoscritto…'}</p>{connectionError && <button onClick={() => setRefreshKey(k => k + 1)}>Riprova</button>}<Link to="/library">Torna alle opere</Link></main>;
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  const facts = data.memory.facts.filter(f => f.section_index === selected);
  const check = data.memory.checks.find(c => c.section_index === selected);
  const allWords = data.chapters.reduce((n, c) => n + c.content.trim().split(/\s+/).filter(Boolean).length, 0);

  return <main className="manuscript-studio">
    <header className="studio-topbar">
      <Link className="studio-back" to="/library" aria-label="Torna alle opere"><ArrowLeft size={20} /></Link>
      <div className="studio-project"><span className="studio-eyebrow">NARRAI / STUDIO DI SCRITTURA</span><h1>{data.title}</h1></div>
      <span className="studio-saved" role="status">{!dirty && <Check size={14} />}{dirty ? 'Modifiche da salvare' : 'Salvato'}</span>
      {data.status === 'complete' && <Link className="studio-reading" to={`/book/${sessionId}`}><BookOpen size={17} /> Lettura</Link>}
      <ExportDropdown sessionId={sessionId} disabled={data.status !== 'complete' || dirty || active} />
    </header>
    <nav className="studio-mobile-tabs" aria-label="Pannelli dello studio">{([
      ['outline', 'Indice', List], ['manuscript', 'Manoscritto', Feather], ['notes', 'Taccuino', NotebookPen],
    ] as const).map(([value, label, Icon]) => <button key={value} aria-pressed={pane === value} onClick={() => setPane(value)}><Icon size={17} />{label}</button>)}</nav>
    {(error || connectionError || notice) && <div className={`studio-message ${error ? 'is-error' : ''}`} role={error ? 'alert' : 'status'}>{error || connectionError || notice}<button aria-label="Chiudi messaggio" onClick={() => { setError(''); setNotice(''); }}>×</button></div>}
    {blocker.state === 'blocked' && <div className="studio-message" role="alert">{busy ? 'Attendi la fine dell’operazione.' : 'Hai modifiche da salvare.'}<button onClick={() => blocker.reset()}>Resta nello studio</button><button disabled={busy} onClick={() => blocker.proceed()}>Esci senza salvare</button></div>}
    <div className="studio-layout">
      <aside className={`studio-outline ${pane === 'outline' ? 'mobile-visible' : ''}`} aria-label="Indice del manoscritto">
        <div className="studio-panel-heading"><span>IL MANOSCRITTO</span><span>{data.chapters.length}/{data.sections.length}</span></div>
        <p className="studio-word-total">{allWords.toLocaleString('it-IT')} parole</p>
        <ol>{data.sections.map((s, index) => {
          const saved = data.chapters.some(c => c.section_index === s.section_index);
          return <li key={s.section_index}><button aria-current={selected === s.section_index ? 'true' : undefined} onClick={() => select(s.section_index)}>
            <span className="studio-chapter-number">{String(index + 1).padStart(2, '0')}</span><span>{s.title}<small>{saved ? 'Scritto' : 'Da scrivere'}</small></span>{saved && <Check size={13} />}
          </button></li>;
        })}</ol>
        {!data.sections.length && <p>L’indice apparirà dopo la preparazione del progetto.</p>}
        <div className="studio-progress">
          <span className={`studio-status-dot ${active ? 'active' : ''}`} /> {active ? 'Lavoro in corso' : labels[data.status] || data.status}
          <progress aria-label="Capitoli scritti" value={data.chapters.length} max={Math.max(1, data.sections.length)} />
          {data.progress?.error && <p>{data.progress.error}</p>}
          {writingActive ? <button disabled={busy || data.progress?.pause_requested} onClick={async () => {
            setBusy(true); try { const result = await pauseWriting(sessionId); setNotice(result.message); setData(await getStudio(sessionId)); }
            catch (e) { setError((e as Error).message); } finally { setBusy(false); }
          }}><Pause size={15} />{data.progress?.pause_requested ? 'Pausa richiesta' : 'Pausa dopo il capitolo'}</button>
            : !active && (data.status === 'paused' || (data.status === 'outline' && data.validated)) && <button className="studio-primary" disabled={busy || dirty} onClick={generate}><Play size={15} />{data.status === 'paused' ? 'Riprendi scrittura' : 'Inizia scrittura'}</button>}
          {data.status === 'draft' && <Link to="/new" onClick={() => localStorage.setItem('current_book_session_id', sessionId)}>Completa la preparazione</Link>}
        </div>
      </aside>
      <section className={`studio-manuscript ${pane === 'manuscript' ? 'mobile-visible' : ''}`} aria-label="Manoscritto">
        <div className="studio-editor-toolbar"><span>{chapter ? `${words.toLocaleString('it-IT')} parole` : 'Piano del capitolo'}</span><div>
          {canEdit && <button aria-pressed={editing} onClick={() => setEditing(!editing)}>{editing ? 'Anteprima' : 'Modifica testo'}</button>}
          {dirty && <><button disabled={busy} onClick={() => { setText(chapter?.content || ''); setDirty(false); setNotice('Modifiche annullate.'); }}>Annulla</button><button className="studio-primary" disabled={busy} onClick={save}><Save size={14} />{busy ? 'Salvataggio…' : 'Salva'}</button></>}
        </div></div>
        <article className="studio-paper">
          <span className="studio-eyebrow">{chapter ? 'IL TESTO' : 'LA PROSSIMA PAGINA'} · {String(selected + 1).padStart(2, '0')}</span>
          <h2>{chapter?.title || section?.title || 'La tua storia comincia qui'}</h2>
          <div className="studio-paper-rule" />
          {chapter ? editing ? <textarea ref={editorRef} aria-label="Testo del capitolo" value={text} readOnly={busy || active} spellCheck onChange={event => { setText(event.target.value); setDirty(event.target.value !== chapter.content); }} />
            : <div className="studio-prose"><ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml>{text}</ReactMarkdown></div>
            : <div className="studio-unwritten"><p>{section?.description || data.draft || 'Completa la preparazione per dare una struttura al manoscritto.'}</p><p className="studio-muted">{active ? 'Il testo comparirà qui appena il capitolo sarà salvato.' : 'Qui troverai il testo, le sue revisioni e le prove della continuità narrativa.'}</p></div>}
        </article>
      </section>
      <aside className={`studio-notes ${pane === 'notes' ? 'mobile-visible' : ''}`} aria-label="Taccuino editoriale">
        <div className="studio-panel-heading"><span>IL TACCUINO</span><NotebookPen size={17} /></div>
        <nav className="studio-note-tabs" aria-label="Contenuti del taccuino">{(['facts', 'costs', 'revisions'] as const).map(tab => <button key={tab} aria-pressed={noteTab === tab} onClick={() => setNoteTab(tab)}>{({ facts: 'Fatti', costs: 'Costi', revisions: 'Revisioni' })[tab]}</button>)}</nav>
        {noteTab === 'facts' && <div className="studio-note-body">
          <h3>Memoria del capitolo</h3>
          {data.jobs.find(j => j.kind === 'memory')?.error && <p role="alert">{data.jobs.find(j => j.kind === 'memory')?.error}</p>}
          {!!data.chapters.length && <button disabled={active || dirty || busy} onClick={async () => { setBusy(true); try { await rebuildMemory(sessionId); setData(await getStudio(sessionId)); setNotice('Analisi della memoria avviata. I consumi sono inclusi nel dettaglio dei costi.'); } catch (e) { setError((e as Error).message); } finally { setBusy(false); } }}>Aggiorna memoria</button>}<p className="studio-muted">Ogni informazione rimanda al testo che la sostiene. Le inferenze restano ipotesi.</p>
          {check?.contradictions.map((c, i) => <div className="studio-conflict" key={i}><strong>Continuità da verificare</strong><p>{c.explanation}</p><blockquote>{c.evidence}</blockquote></div>)}
          {!facts.length && <p className="studio-empty-note">{chapter ? 'Analisi non ancora disponibile per questa revisione. Sarà eseguita prima di proseguire la scrittura.' : 'I fatti appariranno dopo la scrittura del capitolo.'}</p>}
          {facts.map(f => <details className="studio-fact" key={f.id}><summary><span>{f.subject}</span><small>{f.certainty === 'explicit' ? 'Documentato' : 'Inferito'}</small><p>{f.predicate}: {f.value}</p></summary><blockquote>{f.evidence}</blockquote><button disabled={dirty || busy} onClick={() => revealEvidence(f.evidence)}>Vai alla prova nel testo</button></details>)}
        </div>}
        {noteTab === 'costs' && <div className="studio-note-body">
          <h3>Consumi di questo progetto</h3><span className="studio-cost-total">{money(data.costs.cost_usd, 'USD')}</span><p>≈ {money(data.costs.converted_cost_eur, 'EUR')}</p>
          <p className="studio-muted">{data.costs.coverage_complete ? 'Tutte le richieste registrate sono quantificate.' : 'Totale parziale: alcuni consumi non sono ricostruibili.'}</p>
          {data.costs.historical_unverifiable && <p>Il progetto contiene generazioni precedenti al registro dei consumi.</p>}
          {!!data.costs.unquantified_calls && <p>{data.costs.unquantified_calls} richieste da verificare nel conto Google.</p>}
          <p className="studio-muted">{data.costs.note}</p><a href={data.costs.pricing_source} target="_blank" rel="noreferrer">Listino verificato il {data.costs.pricing_verified_at}</a>
          <details className="studio-call-details"><summary>{data.costs.calls} richieste · dettaglio</summary>{data.costs.events.map(e => <div className="studio-call" key={e.id}><strong>{e.phase}</strong><small>{e.model}</small><span>{money(e.cost_usd, 'USD')}</span>{e.usage && <small>Input {e.usage.input_tokens} · output {e.usage.output_tokens}<br />di cui ragionamento {e.usage.thinking_tokens} · cache {e.usage.cached_tokens}</small>}</div>)}</details>
        </div>}
        {noteTab === 'revisions' && <div className="studio-note-body"><h3><History size={16} /> Versioni salvate</h3><p className="studio-muted">Ogni salvataggio conserva il testo precedente.</p>
          {revisions.map(r => <button className="studio-revision" key={r.revision} onClick={() => setRevision(r)}><span>Revisione {r.revision}</span><small>{new Date(r.created_at * 1000).toLocaleString('it-IT')}</small></button>)}
          {!revisions.length && <p>Nessuna revisione disponibile.</p>}
          {revision && <div className="studio-revision-preview"><h4>Revisione {revision.revision}</h4><pre>{revision.content}</pre><button disabled={!canEdit || dirty} onClick={() => { setText(revision.content); setDirty(revision.content !== chapter?.content); setEditing(true); setPane('manuscript'); }}>Porta nell’editor</button><p className="studio-muted">Potrai rileggerla e salvarla come nuova revisione.</p></div>}
        </div>}
      </aside>
    </div>
    <footer className="studio-footer"><span>{data.author || 'Il tuo manoscritto'}</span><span>{dirty ? 'Modifiche da salvare' : `Ultimo salvataggio: ${new Date(data.updated_at).toLocaleTimeString('it-IT')}`}</span></footer>
  </main>;
}
