import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { NotebookSoundProvider, useNotebookSound } from './useNotebookSound';

afterEach(() => { cleanup(); localStorage.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function Controls() {
  const sound = useNotebookSound();
  return <><button onClick={sound.toggle} data-sound-toggle>Suoni</button>
    <a href="#" className="notebook-mode-card"><span>Narrativa</span></a><button>Azione</button></>;
}

function audioMock() {
  const start = vi.fn(), create = vi.fn(), volumes: number[] = [];
  class Audio {
    state = 'running'; sampleRate = 1000; destination = {};
    constructor() { create(); }
    createBuffer() { return { getChannelData: () => new Float32Array(130) }; }
    createBufferSource() { return { connect: vi.fn(), disconnect: vi.fn(), start, onended: null }; }
    createBiquadFilter() { return { connect: vi.fn(), disconnect: vi.fn(), frequency: {}, Q: {} }; }
    createGain() { return { connect: vi.fn(), disconnect: vi.fn(), gain: { set value(value: number) { volumes.push(value); } } }; }
    suspend() { this.state = 'suspended'; return Promise.resolve(); }
    resume() { this.state = 'running'; return Promise.resolve(); }
    close() { return Promise.resolve(); }
  }
  vi.stubGlobal('AudioContext', Audio);
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true })));
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
  return { start, create, volumes };
}

function hover(target: Element, relatedTarget?: Element, pointerType = 'mouse') {
  const event = new Event('pointerover', { bubbles: true });
  Object.assign(event, { pointerType, relatedTarget });
  fireEvent(target, event);
}

it('i suoni sono spenti per default e hover non sblocca l’audio', () => {
  const audio = audioMock();
  render(<NotebookSoundProvider><Controls /></NotebookSoundProvider>);
  hover(screen.getByText('Narrativa')); fireEvent.click(screen.getByText('Azione'));
  expect(audio.create).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('Suoni'));
  hover(screen.getByText('Narrativa'));
  expect(audio.create).not.toHaveBeenCalled();
});

it('hover è leggero, limitato alle modalità e non si ripete entrando nei figli o su touch', () => {
  const audio = audioMock();
  localStorage.setItem('narrai.notebook-sounds', 'true');
  render(<NotebookSoundProvider><Controls /></NotebookSoundProvider>);
  fireEvent.click(screen.getByText('Azione'));
  const card = screen.getByRole('link');
  hover(card);
  expect(audio.start).toHaveBeenCalledTimes(2);
  expect(audio.volumes).toEqual([.035, .008]);
  hover(screen.getByText('Narrativa'), card);
  hover(card); hover(card, undefined, 'touch'); hover(screen.getByText('Azione'));
  expect(audio.start).toHaveBeenCalledTimes(2);
  fireEvent.click(screen.getByText('Suoni'));
  hover(card);
  expect(audio.start).toHaveBeenCalledTimes(2);
});
