import {useEffect,useState} from 'react';
import {Project} from './api';

export type Publication = Pick<Project['form_data'],'author_name'|'title'|'subtitle'|'back_cover_text'> & {expected_version:number};
function values(project:Project):Publication {
 return {
  author_name:project.form_data.author_name||'',
  title:project.form_data.title||project.plan?.title||'',
  subtitle:project.form_data.subtitle||project.plan?.subtitle||'',
  back_cover_text:project.form_data.back_cover_text||project.plan?.back_cover_text||project.plan?.direction||project.form_data.thesis||project.form_data.topic,
  expected_version:project.current_version,
 };
}
export function PublicationForm({project,disabled,onSave,onDirty}:{project:Project;disabled:boolean;onSave:(value:Publication)=>Promise<boolean>;onDirty:(dirty:boolean)=>void}){
 const [value,setValue]=useState(()=>values(project));
 const [dirty,setDirty]=useState(false);
 useEffect(()=>{if(!dirty)setValue(values(project))},[project,dirty]);
 useEffect(()=>{onDirty(dirty);return()=>onDirty(false)},[dirty,onDirty]);
 function update(field:keyof Omit<Publication,'expected_version'>,text:string){
  setValue(old=>({...old,[field]:text}));setDirty(true);
 }
 async function save(){
  if(await onSave(value))setDirty(false);
 }
 return <section className="sg-card"><h2>Autore, titolo e retro</h2>
  <p className="sg-help">Puoi aggiornare questi dati anche a libro completato. Il piano approvato e i capitoli restano validi.</p>
  <form onSubmit={e=>{e.preventDefault();void save()}}>
   <div className="sg-grid-two">
    <label className="sg-field">Nome autore<input maxLength={200} value={value.author_name} onChange={e=>update('author_name',e.target.value)} placeholder="Nome o pseudonimo da stampare"/><small>Compare sulla copertina e nel frontespizio.</small></label>
    <label className="sg-field">Titolo del libro<input maxLength={300} value={value.title} onChange={e=>update('title',e.target.value)}/><small>Preferisci 2-6 parole; lascia i dettagli al sottotitolo.</small></label>
    <label className="sg-field">Sottotitolo<input maxLength={500} value={value.subtitle} onChange={e=>update('subtitle',e.target.value)}/></label>
   </div>
   <label className="sg-field">Testo della quarta di copertina<textarea rows={5} maxLength={1500} value={value.back_cover_text} onChange={e=>update('back_cover_text',e.target.value)}/><small>Presentazione del libro sul retro, come ultima pagina del PDF. Consigliate 80-140 parole.</small></label>
   <button className="sg-primary" disabled={disabled||!dirty} type="submit">Salva autore e copertina</button>
   <p className="sg-help">La copertina tipografica si aggiorna al salvataggio. Le copertine illustrate create prima di questa funzione richiedono “Ricrea copertina”.</p>
  </form>
 </section>;
}
