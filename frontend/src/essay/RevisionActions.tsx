import {Project} from './api';

export interface RevisionRequest {
 expected_version:number;expected_hashes:Record<string,string>;expected_review_at:string;resume:boolean;
}
export function RevisionActions({project,disabled,onStart}:{project:Project;disabled:boolean;onStart:(value:RevisionRequest)=>void}){
 const progress=project.revision_progress;
 const pending=Boolean(progress&&['pending','running'].includes(progress.status));
 const resume=Boolean(project.can_resume_revision&&progress?.status==='failed');
 const available=Boolean(project.review?.issues.length);
 function start(){
  onStart({expected_version:project.current_version,
   expected_hashes:Object.fromEntries(project.book_chapters.map(chapter=>[chapter.section_id,chapter.hash])),
   expected_review_at:project.review?.at||'',resume});
 }
 return <div className="sg-subcard sg-revision-actions">
  <h3>Delega le correzioni all’AI</h3>
  <p>L’AI applica gli interventi ai capitoli interessati e verifica di nuovo il manoscritto, con fino a due passaggi automatici. Le versioni precedenti restano recuperabili da “Versioni” nel capitolo.</p>
  <p className="sg-help">Mantiene la direzione del saggio e usa le fonti disponibili. Le lacune che richiedono nuovi materiali restano segnalate. Correzioni e verifiche hanno consumi propri, registrati nello studio.</p>
  <button className="sg-primary" disabled={disabled||pending||(!available&&!resume)} onClick={start}>
   {pending?'Correzioni AI in corso…':resume?'Riprendi le correzioni AI':'Applica tutte le correzioni con l’AI'}
  </button>
  {!available&&!pending&&!resume&&!progress&&<p className="sg-help">Il comando si attiva quando una revisione propone interventi.</p>}
  {pending&&<p role="status">{progress?.phase==='checking'?'Verifica del manoscritto corretto':'Applicazione delle correzioni'} · passaggio {progress?.pass_number||1} di 2</p>}
  {progress?.status==='completed'&&<p role="status">Ciclo completato: {progress.updated_sections||0} {progress.updated_sections===1?'capitolo aggiornato.':'capitoli aggiornati.'} {progress.remaining_issues?String(progress.remaining_issues)+' interventi ancora segnalati nella nuova revisione.':'La nuova revisione non segnala altri interventi.'}</p>}
  {progress?.status==='failed'&&<p role="alert">Correzioni interrotte: {progress.error} {resume?'Puoi riprendere dai capitoli già salvati.':'Aggiorna la revisione prima di avviare nuove correzioni.'}</p>}
 </div>;
}
