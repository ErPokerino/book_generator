import sharp from 'sharp';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const originalIcon = join(__dirname, '../public/app-icon-original.png');

const sizes = [
  { size: 192, name: 'icon-192.png' },
  { size: 512, name: 'icon-512.png' },
  { size: 32, name: 'favicon.png' },
  { size: 180, name: 'apple-touch-icon.png' },
];

async function generateIcons() {
  console.log('Generazione icone da app-icon-original.png...\n');
  
  for (const { size, name } of sizes) {
    const outputPath = join(__dirname, `../public/${name}`);
    
    await sharp(originalIcon)
      .resize(size, size, {
        fit: 'cover',
        position: 'center'
      })
      .png({ quality: 90 })
      .toFile(outputPath);
    
    console.log(`✓ ${name} (${size}x${size})`);
  }
  
  console.log('\n✅ Tutte le icone generate con successo!');
}

generateIcons().catch(console.error);
