import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import AudioPlayer from './AudioPlayer';

const { getChapterAudio } = vi.hoisted(() => ({ getChapterAudio: vi.fn() }));
vi.mock('../api/client', () => ({ getChapterAudio, getCritiqueAudio: vi.fn() }));

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.clearAllMocks(); });

describe('AudioPlayer', () => {
  it('discards audio arriving for a previous chapter', async () => {
    let finish!: (blob: Blob) => void;
    getChapterAudio.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    const createUrl = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test');
    const { rerender } = render(<AudioPlayer sessionId="book" type="chapter" chapterIndex={0} />);
    fireEvent.click(screen.getByRole('button', { name: 'Ascolta capitolo' }));
    expect(screen.getByRole('button')).toBeDisabled();
    rerender(<AudioPlayer sessionId="book" type="chapter" chapterIndex={1} />);
    expect(screen.getByRole('button')).toBeEnabled();
    await act(async () => finish(new Blob(['old audio'])));
    expect(createUrl).not.toHaveBeenCalled();
  });
});
