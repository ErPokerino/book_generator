// @vitest-environment node
import { mkdtempSync, mkdirSync, writeFileSync, existsSync, rmSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, expect, it } from 'vitest';
import { retainAssets } from './retainAssets';

const directories: string[] = [];
afterEach(() => { for (const path of directories.splice(0)) rmSync(path, { recursive: true, force: true }); });

it('keeps lazy chunks for previous tabs, bounds retention and precaches only current assets', () => {
  const root = mkdtempSync(join(tmpdir(), 'narrai-assets-')); directories.push(root);
  mkdirSync(join(root, 'assets'));
  writeFileSync(join(root, 'assets/old.js'), 'old');
  const build = (name: string) => {
    const retained = retainAssets();
    const plugin = retained.plugin as any;
    plugin.configResolved({ root, build: { outDir: '.' } });
    plugin.buildStart();
    plugin.generateBundle({}, { [`assets/${name}.js`]: {}, 'index.html': {} });
    writeFileSync(join(root, `assets/${name}.js`), name);
    plugin.writeBundle();
    return retained;
  };
  const first = build('first');
  expect(existsSync(join(root, 'assets/old.js'))).toBe(true);
  expect(first.isCurrentAsset('assets/old.js')).toBe(false);
  expect(first.isCurrentAsset('assets/first.js')).toBe(true);
  expect(first.isCurrentAsset('index.html')).toBe(true);
  build('second'); build('second');
  expect(existsSync(join(root, 'assets/old.js'))).toBe(true);
  build('third');
  expect(existsSync(join(root, 'assets/old.js'))).toBe(false);
  expect(existsSync(join(root, 'assets/first.js'))).toBe(true);
  expect(JSON.parse(readFileSync(join(root, '.asset-history.json'), 'utf8'))).toHaveLength(3);
});
