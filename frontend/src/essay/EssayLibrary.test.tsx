import {afterEach,describe,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {EssayLibrary} from './EssayLibrary';
import {Config,LibraryItem} from './api';
import toast from 'react-hot-toast';

vi.mock('react-hot-toast',()=>({default:{success:vi.fn(),error:vi.fn()}}));
const book=(changes:Partial<LibraryItem>={}):LibraryItem=>({
 id:'P1',title:'Il valore del confronto',topic:'Ragioni e fonti',profile:'argumentative',ai_role:'challenge',
 status:'completed',updated_at:'2026-10-07T10:00:00Z',words:1000,estimated_pages:4,pdf_pages:null,
 generation_cost_eur:.302,cost_coverage_complete:true,generation_calls:23,active:false,...changes,
});
const config={api_key_ready:true} as Config;
function mount(items:LibraryItem[],remove?:()=>Promise<Response>){
 const fetch=vi.fn().mockImplementation((_url:string,options?:RequestInit)=>
  options?.method==='DELETE'?(remove?remove():Promise.resolve(new Response(null,{status:204}))):
  Promise.resolve(new Response(JSON.stringify(items))));
 vi.stubGlobal('fetch',fetch);
 render(<MemoryRouter><EssayLibrary config={config}/></MemoryRouter>);
 return fetch;
}
afterEach(()=>{cleanup();localStorage.clear();vi.restoreAllMocks();vi.unstubAllGlobals()});
describe('gestione delle opere',()=>{
 it('mostra pagine e costo con unità e precisione italiane',async()=>{
  mount([book()]);await screen.findByRole('article',{name:'Il valore del confronto'});
  expect(screen.getByText('Pagine stimate')).toBeInTheDocument();
  expect(screen.getByText('4')).toBeInTheDocument();
  expect(screen.getByText(/0,302/)).toHaveTextContent('0,302');
  expect(screen.queryByText('parziale')).not.toBeInTheDocument();
 });
 it('mostra le pagine effettive del PDF quando l’edizione è disponibile',async()=>{
  mount([book({pdf_pages:8})]);
  expect(await screen.findByText('Pagine PDF')).toBeInTheDocument();
  expect(screen.getByText('8')).toBeInTheDocument();
  expect(screen.queryByText('Pagine stimate')).not.toBeInTheDocument();
 });
 it('distingue un totale parziale e un costo non ancora disponibile',async()=>{
  mount([book({cost_coverage_complete:false}),book({id:'P2',title:'In preparazione',words:0,estimated_pages:0,generation_cost_eur:null,generation_calls:0})]);
  await screen.findByText('parziale');
  expect(screen.getByText('Totale misurato: alcuni costi non sono quantificati.')).toBeInTheDocument();
  expect(screen.getByText('Non ancora generato')).toBeInTheDocument();
 });
 it('non rappresenta un costo ignoto come zero',async()=>{
  mount([book({generation_cost_eur:null,cost_coverage_complete:false})]);
  expect(await screen.findByText('Non disponibile')).toBeInTheDocument();
  expect(screen.queryByText(/0,000/)).not.toBeInTheDocument();
 });
 it('annullare la conferma non elimina e non apre lo studio',async()=>{
  const fetch=mount([book()]);
  fireEvent.click(await screen.findByRole('button',{name:'Elimina Il valore del confronto'}));
  const dialog=screen.getByRole('dialog',{name:'Eliminare questo libro?'});
  expect(within(dialog).getByText(/eliminati definitivamente/)).toBeInTheDocument();
  expect(within(dialog).getByRole('button',{name:'Annulla'})).toHaveFocus();
  fireEvent.keyDown(dialog,{key:'Escape'});
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledOnce();
  expect(screen.getByRole('article')).toBeInTheDocument();
 });
 it('elimina solo il libro confermato e le sue bozze locali',async()=>{
  const fetch=mount([book(),book({id:'P2',title:'Un altro libro'})]);
  localStorage.setItem('saggia.chapter.P1.C1','bozza');
  localStorage.setItem('saggia.tab.P1','manuscript');
  localStorage.setItem('saggia.chapter.P2.C1','da conservare');
  fireEvent.click(await screen.findByRole('button',{name:'Elimina Il valore del confronto'}));
  fireEvent.click(screen.getByRole('button',{name:'Elimina definitivamente'}));
  await waitFor(()=>expect(screen.queryByRole('article',{name:'Il valore del confronto'})).not.toBeInTheDocument());
  expect(fetch).toHaveBeenCalledWith('/api/essays/P1',expect.objectContaining({method:'DELETE'}));
  expect(screen.getByRole('article',{name:'Un altro libro'})).toBeInTheDocument();
  expect(localStorage.getItem('saggia.chapter.P1.C1')).toBeNull();
  expect(localStorage.getItem('saggia.tab.P1')).toBeNull();
  expect(localStorage.getItem('saggia.chapter.P2.C1')).toBe('da conservare');
  expect(toast.success).toHaveBeenCalledWith('Libro eliminato');
 });
 it('conserva la scheda e mostra il conflitto se un processo parte nel frattempo',async()=>{
  mount([book()],()=>Promise.resolve(new Response(JSON.stringify({detail:'Attendi la pausa o la fine del processo prima di modificare.'}),{status:409})));
  fireEvent.click(await screen.findByRole('button',{name:'Elimina Il valore del confronto'}));
  fireEvent.click(screen.getByRole('button',{name:'Elimina definitivamente'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Attendi la pausa');
  expect(screen.getByRole('article')).toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Elimina definitivamente'})).toBeEnabled();
 });
 it('impedisce una doppia richiesta durante l’eliminazione',async()=>{
  let resolve:(response:Response)=>void=()=>{};
  const fetch=mount([book()],()=>new Promise<Response>(done=>{resolve=done}));
  fireEvent.click(await screen.findByRole('button',{name:'Elimina Il valore del confronto'}));
  fireEvent.click(screen.getByRole('button',{name:'Elimina definitivamente'}));
  expect(screen.getByRole('button',{name:'Eliminazione…'})).toBeDisabled();
  expect(screen.getByRole('button',{name:'Annulla'})).toBeDisabled();
  resolve(new Response(null,{status:204}));
  await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  expect(fetch).toHaveBeenCalledTimes(2);
 });
 it('segnala perché l’eliminazione è disabilitata durante la generazione',async()=>{
  mount([book({active:true,status:'running'})]);
  const button=await screen.findByRole('button',{name:'Elimina Il valore del confronto'});
  expect(button).toBeDisabled();
  expect(button).toHaveAttribute('title',expect.stringContaining('Attendi la pausa'));
 });
});
