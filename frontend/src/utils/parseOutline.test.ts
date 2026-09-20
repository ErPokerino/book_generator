import { describe, expect, it } from 'vitest';
import { parseOutlineSections } from './parseOutline';

describe('parseOutlineSections', () => {
  it.each(['## Capitolo 1', '## Parte I\n### Capitolo 1'])('preserves prologue and epilogue with %s', chapter => {
    const outline = `## Prologo\nLa promessa.\n${chapter}\nIl viaggio.\n## Epilogo\nLa conseguenza.`;
    expect(parseOutlineSections(outline).map(section => section.title)).toEqual(['Prologo', 'Capitolo 1', 'Epilogo']);
  });
  it('ignores empty headings without duplicating the previous chapter', () => {
    expect(parseOutlineSections('## Capitolo 1\nLa promessa.\n##\n## Capitolo 2\nIl viaggio.').map(section => section.title))
      .toEqual(['Capitolo 1', 'Capitolo 2']);
  });
});
