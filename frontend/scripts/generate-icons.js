/**
 * PWA Icon Generator for NarrAI
 * Source: public/logo-mark.png (cream quill on cinnabar)
 */

import sharp from 'sharp';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { existsSync, writeFileSync } from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const PUBLIC_DIR = join(__dirname, '..', 'public');
const LOGO_PATH = join(PUBLIC_DIR, 'logo-mark.png');
const BACKGROUND_COLOR = '#B42318';

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
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="${BACKGROUND_COLOR}"/>
  <path fill="#F4F0EA" d="M20.6 5.2c-2.2 2-7.4 9.1-11.6 16.4-.7 1.2-1.2 2.2-1.5 3l2.6.9c.4-.9 1.1-2.2 2.1-3.8 3.8-6.4 8.4-12.2 10.8-14.4-1-.9-1.7-1.6-2.4-2.1zM8.4 25.2l-2.8 2.2 3.4-1.1c-.2-.4-.4-.7-.6-1.1z"/>
</svg>`;
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
