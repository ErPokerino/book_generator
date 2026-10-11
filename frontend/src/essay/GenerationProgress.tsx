import {Project} from './api';

const stages:Record<string,string>={
 questions:'Preparazione delle domande',
 draft:'Preparazione del progetto editoriale',
 memory:'Ricerca e analisi delle fonti',
 review:'Revisione del manoscritto',
 revision:'Applicazione delle correzioni AI',
 cover:'Preparazione della copertina',
};

export function GenerationProgress({project,onPause}:{project:Project;onPause:()=>void}){
 const entries=[
  ['questions',project.questions_progress],['draft',project.draft_progress],
  ['memory',project.memory_progress],['book',project.writing_progress],
  ['revision',project.revision_progress],['review',project.review_progress],['cover',project.cover_progress],
 ] as const;
 const active=entries.find(([,progress])=>progress&&['pending','running'].includes(progress.status));
 if(!active&&!project.active)return null;
 const [kind,progress]=active||['',null];
 const writing=kind==='book';
 const queued=progress?.status==='pending';
 const sections=project.plan?.sections||[];
 const requiresReview=project.form_data.revision_mode==='reviewed';
 const chapterFor=(id:string)=>project.book_chapters.find(chapter=>chapter.section_id===id);
 const ready=(id:string)=>{
  const chapter=chapterFor(id);
  return Boolean(chapter&&(!requiresReview||!chapter.review_stale));
 };
 // Saved chapters also identify the correct chapter when resuming a review:
 // a newly queued job temporarily reports current_step=0 and total_steps=1.
 const total=writing&&sections.length?sections.length:Math.max(1,progress?.total_steps||1);
 const completed=writing&&sections.length
  ?sections.filter(section=>ready(section.id)).length
  :Math.max(0,Math.min(total,progress?.current_step||0));
 const index=writing&&sections.length
  ?sections.findIndex(section=>!ready(section.id))
  :completed<total?completed:-1;
 const section=writing?sections[index]:undefined;
 const ordinal=index+1;
 const reviewing=Boolean(writing&&section&&requiresReview&&chapterFor(section.id)?.review_stale);
 const currentParts=writing&&!queued&&!reviewing&&index>=0&&
  (!section||(progress?.current_step===index&&progress.current_section_name===section.title))&&
  Boolean(progress?.current_part&&progress?.total_parts);
 const heading=writing
  ?index<0?'Salvataggio finale del manoscritto'
   :`Capitolo ${ordinal} di ${total}: ${section?.title||progress?.current_section_name||'Preparazione in corso'}`
  :stages[kind]||'Preparazione in corso';
 const phase=queued?'Operazione in coda. Avvio in attesa.'
  :reviewing?`Revisione del capitolo ${ordinal} in corso`
  :currentParts?`Passaggio di scrittura ${progress!.current_part} di ${progress!.total_parts} · capitolo ${ordinal}`
  :writing&&index>=0?`Preparazione del capitolo ${ordinal} in corso`
  :writing?'Tutti i capitoli sono pronti. Salvataggio in corso.'
  :progress?.current_section_name||'Operazione in corso';
 return <section className="sg-progress" role="status">
  <div className="sg-progress-header">
   <div><span className="sg-eyebrow">{writing?'Scrittura del manoscritto':'Operazione in corso'}</span><strong>{heading}</strong></div>
   {writing&&<span className="sg-progress-count">Capitoli completati: <b>{completed} di {total}</b></span>}
  </div>
  <progress aria-label={writing?'Avanzamento del manoscritto':heading}
   aria-valuetext={writing?`${completed} capitoli completati su ${total}`:phase}
   value={writing?completed:undefined} max={total}/>
  <div className="sg-progress-phase">{phase}</div>
  {writing&&!queued&&index>=0&&<p className="sg-help">
   {reviewing
    ?'Il testo del capitolo è stato riunito. L’AI verifica l’argomentazione e i riferimenti, con eventuali correzioni.'
    :'I passaggi sviluppano porzioni dello stesso capitolo tramite richieste AI; alla fine, il testo viene riunito.'}
   {requiresReview&&!reviewing&&' Segue la revisione del capitolo.'}
  </p>}
  {writing&&<button disabled={project.pause_requested} onClick={onPause}>
   {project.pause_requested?'Pausa richiesta…':'Pausa dopo il capitolo'}
  </button>}
 </section>;
}
