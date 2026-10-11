import { useState,useEffect } from 'react';
import { Brief, Config, Profile, AiRole } from './api';
import { EssayForecast } from './EssayForecast';

export function BriefForm({initial,config,onSave,saving=false,submitLabel='Crea progetto',onDraft}:{
 initial:Brief;config:Config;onSave:(brief:Brief)=>void;saving?:boolean;submitLabel?:string;onDraft?:(brief:Brief)=>void
}) {
 const [value,setValue] = useState<Brief>(initial);
 useEffect(()=>{onDraft?.(value)},[value,onDraft]);
 function update<K extends keyof Brief>(key:K,next:Brief[K]) { setValue(old=>({...old,[key]:next})); }
 function selectProfile(profile:Profile) {
  const oldDefaults = config.profiles[value.profile].defaults;
  const newDefaults = config.profiles[profile].defaults;
  setValue(old=>{
   const next = {...old,profile};
   for (const key of Object.keys(newDefaults) as (keyof Brief)[]) {
    if (old[key] === oldDefaults[key]) Object.assign(next,{[key]:newDefaults[key]});
   }
   return next;
  });
 }
 const text = (key:keyof Brief,label:string,placeholder='',rows=2) => <label className="sg-field">{label}<textarea maxLength={key==='back_cover_text'?1500:undefined} value={String(value[key] ?? '')} rows={rows} placeholder={placeholder} onChange={e=>update(key,e.target.value as never)}/></label>;
 const input = (key:keyof Brief,label:string,placeholder='') => <label className="sg-field">{label}<input maxLength={key==='author_name'?200:key==='title'?300:key==='subtitle'?500:undefined} value={String(value[key] ?? '')} placeholder={placeholder} onChange={e=>update(key,e.target.value as never)}/></label>;
 const select = (key:keyof Brief,label:string,options:[string,string][]) => <label className="sg-field">{label}<select value={String(value[key])} onChange={e=>update(key,e.target.value as never)}>{options.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>;
 return <form onSubmit={e=>{e.preventDefault();onSave(value)}} className="sg-brief">
  <section className="sg-card">
   <span className="sg-eyebrow">Il punto di partenza</span>
   <h2>Di cosa vuoi scrivere?</h2>
   <label className="sg-field">Tema del libro <span className="sg-required">Obbligatorio</span><textarea required minLength={3} rows={4} value={value.topic} onChange={e=>update('topic',e.target.value)} placeholder="Un problema, un’idea o una questione che merita un libro…"/></label>
   <div className="sg-grid-two">
    {text('question','Domanda centrale','Quale domanda vuoi affrontare?')}
    {text('thesis','Tesi iniziale, se ne hai una','Quale posizione vuoi sostenere o mettere alla prova?')}
   </div>
   <p className="sg-help">Puoi partire dal solo tema: le domande e il progetto editoriale ti aiuteranno a definire una direzione.</p>
  </section>
  <section className="sg-card">
   <span className="sg-eyebrow">Due scelte indipendenti</span><h2>Il tuo saggio, il tuo metodo</h2>
   <fieldset><legend>Tipo di saggio</legend><div className="sg-choices">{(Object.keys(config.profiles) as Profile[]).map(profile=><label key={profile} className={'sg-choice '+(value.profile===profile?'selected':'')}><input type="radio" name="profile" value={profile} checked={value.profile===profile} onChange={()=>selectProfile(profile)}/><strong>{config.profiles[profile].label}</strong><span>{config.profiles[profile].description}</span></label>)}</div></fieldset>
   <fieldset><legend>Come vuoi lavorare con l’AI?</legend><div className="sg-choices">{(Object.keys(config.roles) as AiRole[]).map(role=><label key={role} className={'sg-choice '+(value.ai_role===role?'selected':'')}><input type="radio" name="ai_role" value={role} checked={value.ai_role===role} onChange={()=>update('ai_role',role)}/><strong>{config.roles[role].label}</strong><span>{config.roles[role].description}</span></label>)}</div></fieldset>
  </section>
  <section className="sg-card"><h2>Lettore e ampiezza</h2>
   <div className="sg-grid-two">
    {select('reader_level','Competenza del lettore adulto',[['general','Generalista'],['informed','Informato sul tema'],['specialist','Specialista']])}
    {input('discipline','Disciplina o ambito','Per esempio: filosofia, storia, tecnologia…')}
    <label className="sg-field">Lunghezza obiettivo <select aria-label="Ampiezza del saggio" value={[15000,35000,60000].includes(value.target_words)?String(value.target_words):'custom'} onChange={e=>{if(e.target.value!=='custom')update('target_words',Number(e.target.value));else update('target_words',10000)}}><option value="15000">Breve · 60 pagine</option><option value="35000">Medio · 140 pagine</option><option value="60000">Ampio · 240 pagine</option><option value="custom">Personalizzata</option></select><input aria-label="Numero di pagine" type="number" required min={4} max={480} step={1} value={Math.ceil(value.target_words/250)} onChange={e=>update('target_words',Number(e.target.value)*250)}/><small>Pagine di testo indicative; l’impaginazione finale può variare. L’ampiezza resta distinta dalla revisione.</small></label>
    {text('reader_needs','Cosa deve ricavarne il lettore?','Comprendere, riconsiderare, orientare una scelta…')}
   </div>
  </section>
  <details className="sg-card" open={value.profile==='academic'}><summary>Perimetro, concetti e metodo</summary><div className="sg-grid-two">
   {text('scope','Perimetro','Periodo, paesi, aspetti inclusi…')}
   {text('exclusions','Aspetti da escludere')}
   {text('concepts','Concetti e termini chiave')}
   {text('premises','Premesse e assunzioni')}
   {input('purpose','Finalità')}
   {select('approach','Approccio',[['analytical','Analitico'],['critical','Critico'],['comparative','Comparativo'],['propositive','Propositivo']])}
   {text('methodology','Metodo','Analisi concettuale, ricostruzione storica, analisi della letteratura…')}
   {text('corpus','Corpus e materiali','Quali documenti, casi o dati intendi analizzare?')}
   {text('source_criteria','Criteri per le fonti','Quali fonti includere o escludere e perché?')}
   {input('source_period','Periodo delle fonti o dei dati')}
  </div></details>
  <details className="sg-card"><summary>Voce e organizzazione</summary><div className="sg-grid-two">
   {select('voice','Persona dell’esposizione',[['impersonal','Impersonale'],['first_singular','Prima persona singolare'],['first_plural','Prima persona plurale']])}
   {select('tone','Tono',[['analytical','Analitico'],['reflective','Riflessivo'],['dialogic','Dialogico'],['assertive','Assertivo'],['polemical','Polemico']])}
   {select('language_register','Registro',[['clear','Chiaro e divulgativo'],['essayistic','Saggistico'],['technical','Tecnico'],['academic','Accademico']])}
   {select('structure','Progressione',[['thesis','Tesi, argomenti e obiezioni'],['problem','Problema, analisi e proposta'],['comparative','Comparativa'],['thematic','Tematica'],['chronological','Cronologica']])}
   {select('density','Densità',[['concise','Sintetica'],['balanced','Equilibrata'],['deep','Approfondita']])}
   {select('example_policy','Esempi',[['documented','Casi documentati'],['hypothetical','Esempi ipotetici dichiarati'],['mixed','Casi ed esempi dichiarati']])}
   {text('editorial_references','Riferimenti editoriali','Caratteristiche di esposizione che ti interessano, distinte dalle fonti da citare')}
  </div><p className="sg-help">Limiti e incertezze vengono sempre dichiarati. Gli esempi ipotetici sono riconoscibili nel testo.</p></details>
  <section className="sg-card"><h2>La tua firma</h2>{input('author_name','Nome autore')}<p className="sg-help">Il nome che comparirà sulla copertina e nel tuo libro.</p></section>
  <details className="sg-card"><summary>Titolo e copertina</summary><div className="sg-grid-two">
   {input('title','Titolo, se già scelto')}
   {input('subtitle','Sottotitolo')}
   {text('back_cover_text','Testo del retro, facoltativo','Se lasci vuoto, viene proposto con il progetto editoriale.')}
   {select('citation_style','Citazioni',[['numeric','Riferimenti numerici'],['author_date','Autore e data']])}
   {select('cover_style','Stile copertina',[['typographic','Tipografica'],['conceptual','Concettuale'],['photographic','Fotografica'],['illustrated','Illustrata']])}
  </div><p className="sg-help">Il nome autore compare sulla copertina e nel libro. Se non scegli un titolo, l’AI propone un titolo breve e sposta i dettagli nel sottotitolo. Il retro diventa l’ultima pagina del PDF. La copertina tipografica non richiede una generazione AI.</p></details>
  <details className="sg-card"><summary>Scrittura, modelli e consumi</summary><div className="sg-grid-two">
   {select('revision_mode','Percorso di scrittura',[['reviewed','Scrittura con revisione dei capitoli'],['writing','Scrittura, poi revisione separata']])}
   {select('llm_model','Modello predefinito',config.models.map(m=>[m.id,m.label]))}
   <label className="sg-field">Limite di spesa, facoltativo (€)<input type="number" min={.01} step={.1} value={value.budget_eur ?? ''} onChange={e=>update('budget_eur',e.target.value ? Number(e.target.value) : null)}/><small>Controllato fra le richieste. Una richiesta già avviata può superare il limite; eventuali costi del servizio di ricerca restano separati.</small></label>
  </div><details><summary>Personalizza i modelli per fase</summary><div className="sg-grid-two">{Object.entries(config.stages).map(([id,label])=><label className="sg-field" key={id}>{label}<select value={value.model_overrides[id] || ''} onChange={e=>{const next={...value.model_overrides}; if(e.target.value)next[id]=e.target.value;else delete next[id];update('model_overrides',next)}}><option value="">Modello predefinito</option>{config.models.map(m=><option key={m.id} value={m.id}>{m.label}</option>)}</select></label>)}</div></details><p className="sg-help">La previsione si aggiorna con ampiezza, percorso e modelli. Ricerca e revisione separata hanno consumi propri; il costo effettivo compare nello studio.</p></details>
  <EssayForecast brief={value}/>
  <div className="sg-actions"><button className="sg-primary" disabled={saving || !value.topic.trim()} type="submit">{saving?'Salvataggio…':submitLabel}</button></div>
 </form>;
}
