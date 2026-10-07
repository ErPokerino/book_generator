import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {RevisionActions} from './RevisionActions';
import {GenerationProgress} from './GenerationProgress';
import {Project,defaultBrief} from './api';
afterEach(cleanup);
const project=(overrides:Partial<Project>={}):Project=>({
 session_id:'Ptest',current_version:3,form_data:defaultBrief(),active:false,
 book_chapters:[{section_id:'C1',section_index:0,title:'Premesse',hash:'current-hash',content:'Testo',display_content:'Testo',unresolved:[]}],
 review:{at:'report-at',summary:'Un problema.',strengths:[],partial:false,issues:[{section_id:'C1',quote:'',category:'style',severity:'important',explanation:'Rendi chiaro.',suggestion:'Precisare.'}]},
 ...overrides,
} as Project);
it('delega tutti gli interventi con la versione del rapporto e gli hash attuali',()=>{
 const start=vi.fn();render(<RevisionActions project={project()} disabled={false} onStart={start}/>);
 fireEvent.click(screen.getByRole('button',{name:'Applica tutte le correzioni con l’AI'}));
 expect(start).toHaveBeenCalledWith({expected_version:3,expected_hashes:{C1:'current-hash'},expected_review_at:'report-at',resume:false});
 expect(screen.getByText(/versioni precedenti restano recuperabili/)).toBeInTheDocument();
});
it('non permette la delega senza interventi o con modifiche non salvate',()=>{
 const start=vi.fn();
 const view=render(<RevisionActions project={project({review:null})} disabled={false} onStart={start}/>);
 expect(screen.getByRole('button')).toBeDisabled();
 view.rerender(<RevisionActions project={project()} disabled={true} onStart={start}/>);
 expect(screen.getByRole('button')).toBeDisabled();
});
it('mostra avanzamento e blocca i doppi avvii durante le correzioni',()=>{
 const p=project({active:true,revision_progress:{status:'running',phase:'checking',pass_number:2,current_section_name:'Verifica finale'}});
 render(<RevisionActions project={p} disabled={true} onStart={vi.fn()}/>);
 expect(screen.getByRole('button',{name:'Correzioni AI in corso…'})).toBeDisabled();
 expect(screen.getByRole('status')).toHaveTextContent('Verifica del manoscritto corretto · passaggio 2 di 2');
});
it('riprende le correzioni interrotte anche se il vecchio rapporto è già stato invalidato',()=>{
 const start=vi.fn();
 render(<RevisionActions project={project({review:null,can_resume_revision:true,revision_progress:{status:'failed',error:'Rete interrotta'}})} disabled={false} onStart={start}/>);
 fireEvent.click(screen.getByRole('button',{name:'Riprendi le correzioni AI'}));
 expect(start).toHaveBeenCalledWith(expect.objectContaining({resume:true,expected_hashes:{C1:'current-hash'},expected_review_at:''}));
 expect(screen.getByRole('alert')).toHaveTextContent('riprendere dai capitoli già salvati');
});
it('distingue il completamento del ciclo dagli interventi ancora da risolvere',()=>{
 render(<RevisionActions project={project({revision_progress:{status:'completed',updated_sections:2,remaining_issues:3}})} disabled={false} onStart={vi.fn()}/>);
 expect(screen.getByRole('status')).toHaveTextContent('2 capitoli aggiornati. 3 interventi ancora segnalati');
});
it('indica quando la nuova revisione non segnala altri interventi',()=>{
 render(<RevisionActions project={project({review:null,revision_progress:{status:'completed',updated_sections:1,remaining_issues:0}})} disabled={false} onStart={vi.fn()}/>);
 expect(screen.getByRole('status')).toHaveTextContent('La nuova revisione non segnala altri interventi.');
 expect(screen.getByRole('button')).toBeDisabled();
});
it('l’avanzamento generale riconosce il nuovo processo',()=>{
 render(<GenerationProgress project={project({active:true,revision_progress:{status:'running',phase:'writing',current_section_name:'Premesse'}})} onPause={vi.fn()}/>);
 expect(screen.getByText('Applicazione delle correzioni AI')).toBeInTheDocument();
 expect(screen.getByText('Premesse')).toBeInTheDocument();
 expect(screen.queryByRole('button',{name:'Pausa dopo il capitolo'})).not.toBeInTheDocument();
});
