import sharp from 'sharp';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Cerca l'icona originale in vari formati
const { existsSync } = await import('fs');
const possiblePaths = [
  join(__dirname, '../public/app-icon-original.png'),
  join(__dirname, '../public/app-icon-original.jpeg'),
  join(__dirname, '../public/app-icon-original.jpg'),
];

let originalIcon = null;
for (const path of possiblePaths) {
  if (existsSync(path)) {
    originalIcon = path;
    break;
  }
}

if (!originalIcon) {
  console.error('❌ Nessuna icona originale trovata! Cerca app-icon-original.png, .jpeg o .jpg in public/');
  process.exit(1);
}

const sizes = [
  { size: 192, name: 'icon-192.png' },
  { size: 512, name: 'icon-512.png' },
  { size: 32, name: 'favicon.png' },
  { size: 180, name: 'apple-touch-icon.png' },
];

async function generateIcons() {
  console.log('Generazione icone da app-icon-original.png...\n');
  
  // Prima carica l'immagine e rimuovi lo spazio bianco
  const image = sharp(originalIcon);
  
  // Trim dello spazio bianco (rimuove padding bianco/trasparente)
  const trimmed = await image
    .trim({ threshold: 10 }) // Rimuove bordi con differenza < 10
    .toBuffer();
  
  for (const { size, name } of sizes) {
    const outputPath = join(__dirname, `../public/${name}`);
    
    await sharp(trimmed)
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
