import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import EvaluationView from './EvaluationView';
import AnalyticsNotebook from './AnalyticsNotebook';

const library=vi.hoisted(()=>vi.fn());
vi.mock('../api/client',()=>({getLibrary:library}));
vi.mock('./CritiqueBlock',()=>({default:({critique}:{critique:{summary:string}})=><p>{critique.summary}</p>}));
beforeEach(()=>{library.mockResolvedValue({books:[],total:0,has_more:false});});
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.clearAllMocks();});

it('evaluates an essay from the bookshelf using the essay endpoint and renders its criteria',async()=>{
  library.mockResolvedValue({books:[{session_id:'E1',content_type:'essay',title:'Una tesi',completed_chapters:1,active:false}],total:1,has_more:false});
  const fetch=vi.fn().mockResolvedValue({ok:true,json:()=>Promise.resolve({summary:'Tesi solida',score:8,pros:[],cons:[],criteria:[{name:'Argomentazione',score:8,explanation:'La conclusione segue le premesse.'}]})});
  vi.stubGlobal('fetch',fetch);
  render(<MemoryRouter initialEntries={['/benchmark?type=essay&session=E1']}><EvaluationView/></MemoryRouter>);
  await screen.findByRole('option',{name:'Una tesi'});
  fireEvent.click(screen.getByRole('button',{name:'Valuta l’opera'}));
  expect(await screen.findByText('Tesi solida')).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith('/api/critique/analyze-work/essay/E1',expect.objectContaining({method:'POST'}));
  expect(screen.getByText('La conclusione segue le premesse.')).toBeInTheDocument();
});

it('uploads a comic PDF with the visual evaluation format',async()=>{
  const fetch=vi.fn().mockResolvedValue({ok:true,json:()=>Promise.resolve({summary:'Tavole chiare',score:7,pros:[],cons:[]})});
  vi.stubGlobal('fetch',fetch);
  render(<MemoryRouter><EvaluationView/></MemoryRouter>);
  fireEvent.click(screen.getByRole('radio',{name:'Fumetto'}));
  expect(screen.getByText('Narrazione visiva')).toBeInTheDocument();
  const file=new File(['%PDF-1.4 comic'],'comic.pdf',{type:'application/pdf'});
  fireEvent.change(screen.getByLabelText('File PDF'),{target:{files:[file]}});
  fireEvent.click(screen.getByRole('button',{name:'Valuta l’opera'}));
  await screen.findByText('Tavole chiare');
  const body=fetch.mock.calls[0][1].body as FormData;
  expect(body.get('work_type')).toBe('manga');expect(body.get('file')).toBe(file);
});

it('does not evaluate an empty or active work',async()=>{
  library.mockResolvedValue({books:[{session_id:'B1',title:'In corso',completed_chapters:1,active:true}],total:1,has_more:false});
  render(<MemoryRouter initialEntries={['/benchmark?session=B1']}><EvaluationView/></MemoryRouter>);
  await screen.findByRole('option',{name:'In corso'});
  expect(screen.getByRole('button',{name:'Valuta l’opera'})).toBeDisabled();
});

it('reports an analytics failure with retry and no misleading zero totals',async()=>{
  const fetch=vi.fn().mockRejectedValueOnce(new Error('Offline')).mockResolvedValue({ok:true,json:()=>Promise.resolve({total:0,months:[],phases:[],models:[],types:[],recent:[],comic_formats:{}})});
  vi.stubGlobal('fetch',fetch);
  render(<MemoryRouter><AnalyticsNotebook/></MemoryRouter>);
  expect(await screen.findByRole('alert')).toHaveTextContent('Offline');
  expect(screen.queryByText('Opere sul tavolo')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Riprova'}));
  expect(await screen.findByText('Un foglio ancora bianco')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('radio',{name:'Fumetti'}));
  await waitFor(()=>expect(fetch).toHaveBeenLastCalledWith('/api/works/analytics?content_type=manga',expect.objectContaining({signal:expect.any(AbortSignal)})));
});
