import {afterEach,describe,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {GenerationProgress} from './GenerationProgress';
import {Chapter,Project,defaultBrief} from './api';

const chapter=(index:number,review_stale=false):Chapter=>({
 section_id:'C'+(index+1),section_index:index,title:'Titolo '+(index+1),
 content:'Testo',display_content:'Testo',hash:'hash',unresolved:[],review_stale,
});
function project(overrides:Partial<Project>={}):Project{
 return {
  form_data:defaultBrief(),active:true,pause_requested:false,
  plan:{title:'Il saggio',subtitle:'',direction:'Tesi',method:'',definitions:[],claims:[],limits:[],
   sections:Array.from({length:7},(_,index)=>({
    id:'C'+(index+1),title:'Titolo '+(index+1),purpose:'Argomentare',
    description:'Contenuto',claim_ids:[],word_target:3000,
   }))},
  book_chapters:[chapter(0),chapter(1),chapter(2)],
  questions_progress:null,draft_progress:null,memory_progress:null,review_progress:null,cover_progress:null,
  writing_progress:{status:'running',current_step:3,total_steps:7,
   current_section_name:'Titolo 4',current_part:3,total_parts:3},
  ...overrides,
 } as Project;
}
afterEach(cleanup);

describe('avanzamento della scrittura',()=>{
 it('distingue il quarto capitolo dai tre già completati e dai suoi tre passaggi',()=>{
  render(<GenerationProgress project={project()} onPause={vi.fn()}/>);
  expect(screen.getByText('Capitolo 4 di 7: Titolo 4')).toBeInTheDocument();
  expect(screen.getByText(/Capitoli completati:/)).toHaveTextContent('Capitoli completati: 3 di 7');
  expect(screen.getByText('Passaggio di scrittura 3 di 3 · capitolo 4')).toBeInTheDocument();
  expect(screen.getByText(/I passaggi sviluppano porzioni dello stesso capitolo tramite richieste AI/)).toBeInTheDocument();
  const bar=screen.getByRole('progressbar',{name:'Avanzamento del manoscritto'});
  expect(bar).toHaveAttribute('value','3');
  expect(bar).toHaveAttribute('max','7');
  expect(bar).toHaveAttribute('aria-valuetext','3 capitoli completati su 7');
 });
 it('distingue la revisione dal passaggio di scrittura appena terminato',()=>{
  render(<GenerationProgress project={project({book_chapters:[chapter(0),chapter(1),chapter(2),chapter(3,true)]})} onPause={vi.fn()}/>);
  expect(screen.getByText('Revisione del capitolo 4 in corso')).toBeInTheDocument();
  expect(screen.getByText(/Il testo del capitolo è stato riunito/)).toBeInTheDocument();
  expect(screen.queryByText(/Passaggio di scrittura/)).not.toBeInTheDocument();
  expect(screen.getByRole('progressbar')).toHaveAttribute('value','3');
 });
 it('usa il piano e i capitoli salvati durante la ripresa in coda',()=>{
  render(<GenerationProgress project={project({writing_progress:{status:'pending',current_step:0,total_steps:1}})} onPause={vi.fn()}/>);
  expect(screen.getByText('Capitolo 4 di 7: Titolo 4')).toBeInTheDocument();
  expect(screen.getByText('Operazione in coda. Avvio in attesa.')).toBeInTheDocument();
  expect(screen.getByRole('progressbar')).toHaveAttribute('max','7');
  expect(screen.getByRole('progressbar')).toHaveAttribute('value','3');
 });
 it('riconosce il capitolo da rivedere dopo un riavvio, anche prima del primo aggiornamento del contatore',()=>{
  render(<GenerationProgress project={project({
   book_chapters:[chapter(0),chapter(1),chapter(2),chapter(3,true)],
   writing_progress:{status:'running',current_step:0,total_steps:1},
  })} onPause={vi.fn()}/>);
  expect(screen.getByText('Capitolo 4 di 7: Titolo 4')).toBeInTheDocument();
  expect(screen.getByText('Revisione del capitolo 4 in corso')).toBeInTheDocument();
 });
 it('non trascina i passaggi del capitolo precedente al successivo',()=>{
  render(<GenerationProgress project={project({
   book_chapters:[chapter(0),chapter(1),chapter(2),chapter(3)],
  })} onPause={vi.fn()}/>);
  expect(screen.getByText('Capitolo 5 di 7: Titolo 5')).toBeInTheDocument();
  expect(screen.getByText('Preparazione del capitolo 5 in corso')).toBeInTheDocument();
  expect(screen.queryByText(/Passaggio di scrittura/)).not.toBeInTheDocument();
 });
 it('non mostra un ottavo capitolo al termine dei sette previsti',()=>{
  render(<GenerationProgress project={project({
   book_chapters:Array.from({length:7},(_,index)=>chapter(index)),
   writing_progress:{status:'running',current_step:7,total_steps:7,current_part:3,total_parts:3},
  })} onPause={vi.fn()}/>);
  expect(screen.getByText('Salvataggio finale del manoscritto')).toBeInTheDocument();
  expect(screen.queryByText(/Capitolo 8/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Passaggio di scrittura/)).not.toBeInTheDocument();
  expect(screen.getByRole('progressbar')).toHaveAttribute('value','7');
 });
 it('conta come completi i capitoli salvati quando la revisione automatica è disattivata',()=>{
  render(<GenerationProgress project={project({
   form_data:{...defaultBrief(),revision_mode:'draft'},
   book_chapters:[chapter(0,true),chapter(1,true),chapter(2,true)],
  })} onPause={vi.fn()}/>);
  expect(screen.getByText(/Capitoli completati:/)).toHaveTextContent('3 di 7');
  expect(screen.getByText('Passaggio di scrittura 3 di 3 · capitolo 4')).toBeInTheDocument();
  expect(screen.queryByText(/Segue la revisione/)).not.toBeInTheDocument();
 });
 it('mantiene la pausa dopo il capitolo e disabilita una richiesta già inoltrata',()=>{
  const pause=vi.fn();
  const view=render(<GenerationProgress project={project()} onPause={pause}/>);
  fireEvent.click(screen.getByRole('button',{name:'Pausa dopo il capitolo'}));
  expect(pause).toHaveBeenCalledOnce();
  view.rerender(<GenerationProgress project={project({pause_requested:true})} onPause={pause}/>);
  expect(screen.getByRole('button',{name:'Pausa richiesta…'})).toBeDisabled();
 });
 it('non mostra il pannello quando non è in corso alcuna operazione',()=>{
  render(<GenerationProgress project={project({active:false,writing_progress:{status:'completed'}})} onPause={vi.fn()}/>);
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
 });
 it('mostra lo stato di preparazione senza inventare una percentuale',()=>{
  render(<GenerationProgress project={project({writing_progress:null})} onPause={vi.fn()}/>);
  expect(screen.getByText('Preparazione in corso')).toBeInTheDocument();
  expect(screen.getByRole('progressbar')).not.toHaveAttribute('value');
  expect(screen.queryByText(/Capitoli completati:/)).not.toBeInTheDocument();
 });
 it('nomina la ricerca e la fonte in analisi senza confonderle con i capitoli',()=>{
  render(<GenerationProgress project={project({
   writing_progress:null,memory_progress:{status:'running',current_step:2,total_steps:5,current_section_name:'Fonte attendibile'},
  })} onPause={vi.fn()}/>);
  expect(screen.getByText('Ricerca e analisi delle fonti')).toBeInTheDocument();
  expect(screen.getByText('Fonte attendibile')).toBeInTheDocument();
  expect(screen.getByRole('progressbar')).not.toHaveAttribute('value');
  expect(screen.queryByText(/Capitoli completati:/)).not.toBeInTheDocument();
  expect(screen.queryByRole('button',{name:'Pausa dopo il capitolo'})).not.toBeInTheDocument();
 });
});
