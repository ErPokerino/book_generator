import { existsSync, readFileSync, readdirSync, renameSync, unlinkSync, writeFileSync } from 'node:fs';
import { resolve, sep } from 'node:path';
import type { Plugin } from 'vite';

// Open tabs may still import a previous build's lazy chunks. Keep three builds
// on disk, while the service worker precaches only the current build.
export function retainAssets(): { plugin: Plugin; isCurrentAsset: (url: string) => boolean } {
  let directory: string;
  let history: string[][] = [];
  let current = new Set<string>();
  const historyName = '.asset-history.json';
  return {
    isCurrentAsset: url => !url.startsWith('assets/') || current.has(url),
    plugin: {
      name: 'retain-previous-assets',
      apply: 'build',
      configResolved(config) {
        directory = resolve(config.root, config.build.outDir);
      },
      buildStart() {
        const file = resolve(directory, historyName);
        if (existsSync(file)) {
          history = JSON.parse(readFileSync(file, 'utf8'));
          if (!Array.isArray(history) || !history.every(build => Array.isArray(build) && build.every(path => typeof path === 'string'))) {
            throw new Error('Cronologia degli asset non valida: build interrotta senza eliminare file.');
          }
        } else {
          const assets = resolve(directory, 'assets');
          history = existsSync(assets) ? [readdirSync(assets).map(name => `assets/${name}`)] : [];
        }
      },
      generateBundle(_options, bundle) {
        current = new Set(Object.keys(bundle).filter(name => name.startsWith('assets/')));
      },
      writeBundle() {
        // Failed compilation never reaches this hook; the previous build stays usable.
        const signature = (assets: string[]) => [...assets].sort().join('\n');
        const builds = [[...current], ...history.filter(assets => signature(assets) !== signature([...current]))];
        const retained = builds.slice(0, 3);
        const keep = new Set(retained.flat());
        const assetRoot = resolve(directory, 'assets') + sep;
        for (const asset of new Set(builds.slice(3).flat())) {
          if (keep.has(asset)) continue;
          const target = resolve(directory, asset);
          if (!target.startsWith(assetRoot)) throw new Error('Percorso asset fuori dalla directory di build.');
          if (existsSync(target)) unlinkSync(target);
        }
        const file = resolve(directory, historyName);
        writeFileSync(file + '.tmp', JSON.stringify(retained));
        renameSync(file + '.tmp', file);
      },
    },
  };
}
