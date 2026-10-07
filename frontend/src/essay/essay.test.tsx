import {afterEach,describe,it,expect,vi} from 'vitest';
import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react';
import {BriefForm} from './BriefForm';
import {ChapterEditor} from './ChapterEditor';
import {SourcePanel,SourceDialog} from './SourcePanel';
import {defaultBrief,Config,Project,Chapter,Source} from './api';
import toast from 'react-hot-toast';
vi.mock('react-hot-toast',()=>({default:{success:vi.fn(),error:vi.fn()}}));
const config:Config={name:'SaggIA',default_model:'gemini-3.8-flash',models:[{id:'gemini-3.8-flash',label:'Gemini 3.8 Flash'}],stages:{chapters:'Scrittura'},api_key_ready:true,
 profiles:{
 argumentative:{label:'Argomentativo',description:'Ragioni',defaults:{purpose:'argomentare',structure:'thesis',language_register:'clear',citation_style:'numeric'}},
 popular:{label:'Divulgativo',description:'Concetti',defaults:{purpose:'divulgare',structure:'thematic',language_register:'clear',citation_style:'numeric'}},
 academic:{label:'Accademico',description:'Metodo',defaults:{purpose:'analizzare',structure:'problem',language_register:'academic',citation_style:'author_date'}}},
 roles:{challenge:{label:'Metti alla prova',description:'Critica'},support:{label:'Sostieni',description:'Posizione'},explore:{label:'Esplora',description:'Alternative'}}};
const project=()=>({session_id:'Ptest',form_data:{...defaultBrief(),topic:'Il valore del confronto'},active:false,sources:[],research_log:[],book_chapters:[]} as unknown as Project);
const chapter:Chapter={section_id:'C1',section_index:0,title:'Premesse',content:'Testo originale.',display_content:'Testo originale.',hash:'hash-originale',unresolved:[]};
afterEach(()=>{cleanup();localStorage.clear();vi.restoreAllMocks();vi.unstubAllGlobals()});
describe('scelte editoriali indipendenti',()=>{
 for(const [profile,label] of [['argumentative','Argomentativo'],['popular','Divulgativo'],['academic','Accademico']] as const)
  for(const [role,roleLabel] of [['challenge','Metti alla prova'],['support','Sostieni'],['explore','Esplora']] as const)
   it(profile+' con '+role,()=>{
    const save=vi.fn();render(<BriefForm initial={{...defaultBrief(),topic:'Un tema valido'}} config={config} onSave={save}/>);
    fireEvent.click(screen.getByRole('radio',{name:new RegExp(label)}));fireEvent.click(screen.getByRole('radio',{name:new RegExp(roleLabel)}));
    fireEvent.click(screen.getByRole('button',{name:'Crea progetto'}));
    expect(save).toHaveBeenCalledWith(expect.objectContaining({profile,ai_role:role}));
   });
 it('aggiorna i valori standard ma conserva le scelte esplicite',()=>{
  const save=vi.fn();render(<BriefForm initial={{...defaultBrief(),topic:'Un tema valido',language_register:'essayistic'}} config={config} onSave={save}/>);
  fireEvent.click(screen.getByRole('radio',{name:/Accademico/}));fireEvent.click(screen.getByRole('button',{name:'Crea progetto'}));
  expect(save).toHaveBeenCalledWith(expect.objectContaining({language_register:'essayistic',purpose:'analizzare',citation_style:'author_date',ai_role:'challenge'}));
 });
});
describe('editor e fonti',()=>{
 it('conserva la bozza dopo un conflitto, anche riaprendo il capitolo',async()=>{
  const fetch=vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:'Il capitolo è cambiato.'}),{status:409}));vi.stubGlobal('fetch',fetch);
  const props={chapter,project:project(),onChange:vi.fn(),onOpenSource:vi.fn(),onDirty:vi.fn()};
  const view=render(<ChapterEditor {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Modifica'}));
  fireEvent.change(screen.getByRole('textbox',{name:'Testo del capitolo'}),{target:{value:'La mia revisione da conservare.'}});
  fireEvent.click(screen.getByRole('button',{name:'Salva revisione'}));
  await waitFor(()=>expect(toast.error).toHaveBeenCalledWith('Il capitolo è cambiato.'));
  expect(screen.getByRole('textbox')).toHaveValue('La mia revisione da conservare.');
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({content:'La mia revisione da conservare.',expected_hash:'hash-originale'});
  view.unmount();render(<ChapterEditor {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Modifica'}));
  expect(screen.getByRole('textbox')).toHaveValue('La mia revisione da conservare.');
 });
 it('rimuove la bozza locale soltanto dopo il salvataggio riuscito',async()=>{
  const next={...project(),book_chapters:[{...chapter,content:'Revisionato.',hash:'nuovo'}]};
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify(next))));
  const change=vi.fn();render(<ChapterEditor chapter={chapter} project={project()} onChange={change} onOpenSource={vi.fn()} onDirty={vi.fn()}/>);
  fireEvent.click(screen.getByRole('button',{name:'Modifica'}));
  fireEvent.change(screen.getByRole('textbox'),{target:{value:'Revisionato.'}});
  fireEvent.click(screen.getByRole('button',{name:'Salva revisione'}));
  await waitFor(()=>expect(change).toHaveBeenCalledWith(next));expect(localStorage.getItem('saggia.chapter.Ptest.C1')).toBeNull();
 });
 it('non perde il testo di una fonte quando l’importazione fallisce',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:'Documento non accessibile'}),{status:422})));
  render(<SourcePanel project={project()} onChange={vi.fn()} onOpen={vi.fn()} onJob={vi.fn()}/>);
  fireEvent.click(screen.getByText('Aggiungi un link o incolla un testo'));
  fireEvent.change(screen.getByLabelText('Titolo'),{target:{value:'Il mio materiale'}});
  fireEvent.change(screen.getByLabelText('Testo'),{target:{value:'Appunti personali abbastanza lunghi da poter essere importati.'}});
  fireEvent.click(screen.getByRole('button',{name:'Aggiungi materiale'}));
  await waitFor(()=>expect(toast.error).toHaveBeenCalledWith('Documento non accessibile'));
  expect(screen.getByLabelText('Titolo')).toHaveValue('Il mio materiale');
  expect(screen.getByLabelText('Testo')).toHaveValue('Appunti personali abbastanza lunghi da poter essere importati.');
 });
 it('apre la fonte corretta e non esegue HTML del manoscritto',()=>{
  const open=vi.fn();render(<ChapterEditor chapter={{...chapter,display_content:'Prova [1](#source-S42).\n\n<script>alert(1)</script>'}} project={project()} onChange={vi.fn()} onOpenSource={open} onDirty={vi.fn()}/>);
  fireEvent.click(screen.getByRole('button',{name:'1'}));expect(open).toHaveBeenCalledWith('S42');expect(document.querySelector('script')).toBeNull();
 });
 it('il dialogo delle fonti si chiude con Escape',()=>{
  const close=vi.fn();render(<SourceDialog source={{id:'S1',title:'Fonte',evidence:[],url:'',author:'',published:'',error:''} as unknown as Source} projectId="Ptest" disabled={false} onClose={close} onUpdate={vi.fn()}/>);
  fireEvent.keyDown(document,{key:'Escape'});expect(close).toHaveBeenCalledTimes(1);
 });
});

it('autosalva il brief durante la scrittura, prima di creare il progetto',async()=>{
 const draft=vi.fn();render(<BriefForm initial={defaultBrief()} config={config} onSave={vi.fn()} onDraft={draft}/>);
 fireEvent.change(screen.getByLabelText(/Tema del libro/),{target:{value:'La bozza del mio nuovo libro'}});
 await waitFor(()=>expect(draft).toHaveBeenLastCalledWith(expect.objectContaining({topic:'La bozza del mio nuovo libro'})));
});
it('non aggiorna silenziosamente il riferimento di versione mentre si modificano i dati di una fonte',async()=>{
 const original={id:'S1',version:1,title:'Fonte originale',author:'Autore',published:'2020',status:'analyzed',url:'',error:'',evidence:[]} as unknown as Source;
 const fetch=vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:'Dati della fonte cambiati'}),{status:409}));vi.stubGlobal('fetch',fetch);
 const props={projectId:'Ptest',disabled:false,onClose:vi.fn(),onUpdate:vi.fn()};
 const view=render(<SourceDialog {...props} source={original}/>);
 fireEvent.click(screen.getByText('Dati bibliografici'));
 fireEvent.change(screen.getByLabelText('Titolo della fonte'),{target:{value:'La mia modifica'}});
 view.rerender(<SourceDialog {...props} source={{...original,version:2,title:'Modifica da altra scheda'}}/>);
 fireEvent.click(screen.getByRole('button',{name:'Salva dati bibliografici'}));
 await waitFor(()=>expect(toast.error).toHaveBeenCalledWith('Dati della fonte cambiati'));
 expect(JSON.parse(fetch.mock.calls[0][1].body).expected_version).toBe(1);
 expect(screen.getByLabelText('Titolo della fonte')).toHaveValue('La mia modifica');
});

describe('autore e quarta di copertina',()=>{
 it('mostra il nome autore nel brief senza aprire impostazioni avanzate',()=>{
  const save=vi.fn();render(<BriefForm initial={{...defaultBrief(),topic:'Un tema valido'}} config={config} onSave={save}/>);
  const author=screen.getByLabelText('Nome autore');
  expect(author.closest('details')).toBeNull();
  fireEvent.change(author,{target:{value:'Ada Rossi'}});
  fireEvent.click(screen.getByRole('button',{name:'Crea progetto'}));
  expect(save).toHaveBeenCalledWith(expect.objectContaining({author_name:'Ada Rossi'}));
 });
 it('conserva autore, bozza e versione durante polling e conflitti',async()=>{
  const save=vi.fn().mockResolvedValue(false);const dirty=vi.fn();
  const p={...project(),current_version:7,plan:{title:'Titolo breve',subtitle:'Dettagli',direction:'Una presentazione automatica.'}} as Project;
  const {PublicationForm}=await import('./PublicationForm');
  const view=render(<PublicationForm project={p} disabled={false} onSave={save} onDirty={dirty}/>);
  fireEvent.change(screen.getByLabelText(/Nome autore/),{target:{value:'Ada Rossi'}});
  view.rerender(<PublicationForm project={{...p,current_version:8,form_data:{...p.form_data,author_name:'Altra scheda'}}} disabled={false} onSave={save} onDirty={dirty}/>);
  fireEvent.click(screen.getByRole('button',{name:'Salva autore e copertina'}));
  await waitFor(()=>expect(save).toHaveBeenCalledWith(expect.objectContaining({author_name:'Ada Rossi',expected_version:7,back_cover_text:'Una presentazione automatica.'})));
  expect(screen.getByLabelText(/Nome autore/)).toHaveValue('Ada Rossi');
  expect(screen.getByRole('button',{name:'Salva autore e copertina'})).toBeEnabled();
 });
 it('disabilita il salvataggio durante i processi e segnala solo le modifiche non salvate',async()=>{
  const save=vi.fn().mockResolvedValue(true);const dirty=vi.fn();
  const {PublicationForm}=await import('./PublicationForm');
  const p={...project(),current_version:3};
  const view=render(<PublicationForm project={p} disabled={true} onSave={save} onDirty={dirty}/>);
  fireEvent.change(screen.getByLabelText(/Nome autore/),{target:{value:'Ada Rossi'}});
  expect(screen.getByRole('button',{name:'Salva autore e copertina'})).toBeDisabled();
  view.rerender(<PublicationForm project={p} disabled={false} onSave={save} onDirty={dirty}/>);
  fireEvent.click(screen.getByRole('button',{name:'Salva autore e copertina'}));
  await waitFor(()=>expect(dirty).toHaveBeenLastCalledWith(false));
  expect(screen.getByRole('button',{name:'Salva autore e copertina'})).toBeDisabled();
 });
});
