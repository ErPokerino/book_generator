/**
 * PWA Icon Generator for NarrAI
 * Source: public/logo-mark.svg (ink on paper)
 */

import sharp from 'sharp';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { existsSync, readFileSync, writeFileSync } from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const PUBLIC_DIR = join(__dirname, '..', 'public');
const LOGO_PATH = join(PUBLIC_DIR, 'logo-mark.svg');
const BACKGROUND_COLOR = '#FAFAF7';

async function squareIcon(size, paddingRatio = 0, fit = 'cover') {
  const canvas = sharp({
    create: {
      width: size,
      height: size,
      channels: 4,
      background: BACKGROUND_COLOR,
    },
  });

  const inner = Math.max(1, Math.round(size * (1 - paddingRatio)));
  const logo = await sharp(LOGO_PATH)
    .flatten({ background: BACKGROUND_COLOR })
    .resize(inner, inner, { fit, background: BACKGROUND_COLOR })
    .png()
    .toBuffer();

  const meta = await sharp(logo).metadata();
  const left = Math.round((size - (meta.width || inner)) / 2);
  const top = Math.round((size - (meta.height || inner)) / 2);
  return canvas.composite([{ input: logo, left, top }]).png();
}

async function writeIcon(filename, size, paddingRatio = 0, fit = 'cover') {
  await (await squareIcon(size, paddingRatio, fit)).toFile(join(PUBLIC_DIR, filename));
  console.log(`  ✓ ${filename}`);
}

async function generateSvgFavicon() {
  const svg = readFileSync(LOGO_PATH, 'utf8');
  writeFileSync(join(PUBLIC_DIR, 'favicon.svg'), svg);
  console.log('  ✓ favicon.svg');
}

async function main() {
  console.log('\nNarrAI icon generator\n');
  if (!existsSync(LOGO_PATH)) {
    console.error(`Logo not found: ${LOGO_PATH}`);
    process.exit(1);
  }

  await writeIcon('icon-192.png', 192);
  await writeIcon('icon-512.png', 512);
  await writeIcon('icon-192-maskable.png', 192, 0.2);
  await writeIcon('icon-512-maskable.png', 512, 0.2);
  await writeIcon('favicon.png', 32, 0.18, 'contain');
  await writeIcon('favicon-16.png', 16, 0.12, 'contain');
  await writeIcon('apple-touch-icon.png', 180);
  await generateSvgFavicon();
  console.log('\nDone.\n');
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
