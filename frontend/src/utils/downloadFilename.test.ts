import { describe, expect, it } from 'vitest';
import { downloadFilename } from './downloadFilename';

describe('downloadFilename', () => {
  it('decodes Unicode exported titles', () => {
    expect(downloadFilename("attachment; filename*=UTF-8''%E6%9C%88_citt%C3%A0.pdf", 'book.pdf')).toBe('月_città.pdf');
  });
  it('supports legacy headers and missing or malformed values', () => {
    expect(downloadFilename('attachment; filename="Una storia.pdf"', 'book.pdf')).toBe('Una storia.pdf');
    expect(downloadFilename(null, 'book.pdf')).toBe('book.pdf');
    expect(downloadFilename("attachment; filename*=UTF-8''%ZZ; filename=book.pdf", 'fallback.pdf')).toBe('book.pdf');
  });
});
