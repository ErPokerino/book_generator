import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import type { LibraryEntry } from '../api/client';
import DynamicForm from './DynamicForm';
import MangaBetaView from './MangaBetaView';
import BookCard from './BookCard';
import SettingsView from './SettingsView';
import Navigation from './Navigation';
import { NotebookSoundProvider } from '../hooks/useNotebookSound';

const mocks = vi.hoisted(()=>({restore:vi.fn(),start:vi.fn(),deleteBook:vi.fn(),essay:vi.fn(),toast:{error:vi.fn(),success:vi.fn()}, config:vi.fn()}));
vi.mock('../api/client',()=>({restoreSession:mocks.restore,startMangaGeneration:mocks.start,deleteBook:mocks.deleteBook,
  fetchConfig:()=>Promise.resolve({llm_models:[],fields:[{id:'plot',label:'Trama',type:'text',required:true}]}),getAppConfig:mocks.config,
  getMangaProgress:()=>new Promise(()=>{}),getManga:()=>new Promise(()=>{})}));
vi.mock('../essay/api',()=>({api:mocks.essay}));
vi.mock('../hooks/useToast',()=>({useToast:()=>mocks.toast}));
vi.mock('./ModelSettingsPanel',()=>({default:()=>null,BOOK_STAGES:[],MANGA_STAGES:[],DEFAULT_TEXT_MODEL:'gemini-3.8-flash',buildModelOverrides:()=>({})}));
vi.mock('./ExportDropdown',()=>({default:()=>null}));

beforeEach(()=>{localStorage.clear();mocks.config.mockResolvedValue({});mocks.deleteBook.mockResolvedValue({});mocks.essay.mockResolvedValue(undefined);});
afterEach(()=>{cleanup();vi.clearAllMocks();});
const wrap=(node:React.ReactNode,path='/new')=>render(<MemoryRouter initialEntries={[path]}>{node}</MemoryRouter>);
const work=(kind:LibraryEntry['content_type']):LibraryEntry=>({session_id:'W1',content_type:kind,title:'La mia opera',author:'Ada',llm_model:'Standard',status:'complete',created_at:'2026-10-01',updated_at:'2026-10-01',total_chapters:1,completed_chapters:1});

describe('creation and common bookshelf actions',()=>{
  it('opens a new narrative even when a completed book is saved locally',async()=>{
    localStorage.setItem('current_book_session_id','old-book');
    localStorage.setItem('dynamicForm.formData',JSON.stringify({plot:'La Liturgia del Ferro Rosso'}));
    localStorage.setItem('newBook.plot','La Liturgia del Ferro Rosso');
    wrap(<DynamicForm/>);
    expect(await screen.findByRole('heading',{name:'Crea narrativa'})).toBeInTheDocument();
    expect(mocks.restore).not.toHaveBeenCalled();
    expect(await screen.findByRole('textbox',{name:/Trama/})).toHaveValue('');
  });
  it('resumes narrative only when its session is explicitly requested',async()=>{
    mocks.restore.mockResolvedValue({session_id:'chosen',form_data:{plot:'Scelta',llm_model:'gemini-3.8-flash'},content_type:'book',current_step:'form'});
    wrap(<DynamicForm/>,'/new?session=chosen');
    await waitFor(()=>expect(mocks.restore).toHaveBeenCalledWith('chosen'));
  });
  it('does not resume a stored comic when entering creation',async()=>{
    localStorage.setItem('current_manga_session_id','old-comic');
    wrap(<MangaBetaView/>,'/comics');
    expect(await screen.findByRole('heading',{name:'Crea un fumetto'})).toBeInTheDocument();
    expect(mocks.restore).not.toHaveBeenCalled();
  });
  it('switches comic formats and sends the selected graphic novel genre',async()=>{
    mocks.start.mockResolvedValue({session_id:'new-comic'});
    wrap(<MangaBetaView/>,'/comics');
    await screen.findByRole('heading',{name:'Crea un fumetto'});
    fireEvent.change(screen.getByLabelText('Sottogenere'),{target:{value:'sports'}});
    fireEvent.click(screen.getByRole('radio',{name:/Graphic Novel/}));
    expect(screen.queryByLabelText('Pubblico manga')).not.toBeInTheDocument();
    expect(screen.queryByRole('option',{name:'Sport'})).not.toBeInTheDocument();
    expect(screen.getByLabelText('Sottogenere')).toHaveValue('literary');
    fireEvent.change(screen.getByLabelText('Sottogenere'),{target:{value:'memoir'}});
    fireEvent.change(screen.getByRole('textbox',{name:/Trama di partenza/}),{target:{value:'Una memoria d’infanzia'}});
    fireEvent.change(screen.getByRole('textbox',{name:/Nome/}),{target:{value:'Ada'}});
    fireEvent.change(screen.getByRole('textbox',{name:/Descrizione/}),{target:{value:'Una viaggiatrice'}});
    fireEvent.click(screen.getByRole('button',{name:'Inizia'}));
    await waitFor(()=>expect(mocks.start).toHaveBeenCalledWith(expect.objectContaining({comic_format:'graphic_novel',comic_genre:'memoir'})));
  });
  it.each(['book','essay','manga'] as const)('opens %s from cover and title in reading mode',kind=>{
    const onRead=vi.fn();wrap(<BookCard book={work(kind)} onDelete={vi.fn()} onRead={onRead}/>,'/library');
    const route=kind==='book'?'/book/W1':`/read/${kind}/W1`;
    expect(screen.getByRole('link',{name:'Leggi La mia opera'})).toHaveAttribute('href',route);
    expect(screen.getByRole('link',{name:'La mia opera'})).toHaveAttribute('href',route);
    fireEvent.click(screen.getByRole('button',{name:'Leggi'}));expect(onRead).toHaveBeenCalledWith(expect.objectContaining({session_id:'W1'}));
  });
  it.each(['book','essay','manga'] as const)('deletes %s through a visible common action after confirmation',async kind=>{
    const onDelete=vi.fn();wrap(<BookCard book={work(kind)} onDelete={onDelete}/>,'/library');
    fireEvent.click(screen.getByRole('button',{name:'Elimina La mia opera'}));
    expect(onDelete).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button',{name:'Elimina'}));
    await waitFor(()=>expect(onDelete).toHaveBeenCalledWith('W1'));
    if(kind==='essay')expect(mocks.essay).toHaveBeenCalledWith('essays/W1',{method:'DELETE'});
    else expect(mocks.deleteBook).toHaveBeenCalledWith('W1');
  });
  it('keeps active deletion unavailable until the saved generation stops',()=>{
    wrap(<BookCard book={{...work('manga'),active:true,status:'writing'}} onDelete={vi.fn()}/>,'/library');
    expect(screen.getByRole('button',{name:'Elimina La mia opera'})).toBeDisabled();
  });
  it('moves the persistent sound preference into settings',()=>{
    wrap(<NotebookSoundProvider><Navigation/><SettingsView/></NotebookSoundProvider>,'/settings');
    expect(screen.getByRole('link',{name:'Impostazioni'})).toHaveAttribute('href','/settings');
    expect(screen.queryByRole('button',{name:/suoni di scrittura/})).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox',{name:'Attiva i suoni'}));
    expect(localStorage.getItem('narrai.notebook-sounds')).toBe('true');
  });
});
