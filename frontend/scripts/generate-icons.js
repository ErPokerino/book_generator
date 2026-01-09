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
  { size: 192, name: 'icon-192.png', maskable: false },
  { size: 512, name: 'icon-512.png', maskable: false },
  { size: 192, name: 'icon-192-maskable.png', maskable: true },
  { size: 512, name: 'icon-512-maskable.png', maskable: true },
  { size: 32, name: 'favicon.png', maskable: false },
  { size: 16, name: 'favicon-16.png', maskable: false },
  { size: 180, name: 'apple-touch-icon.png', maskable: false },
];

async function generateIcons() {
  console.log('Generazione icone da app-icon-original.png...\n');
  
  // Prima carica l'immagine e rimuovi lo spazio bianco
  const image = sharp(originalIcon);
  
  // Trim più aggressivo dello spazio bianco
  const processed = await image
    .ensureAlpha() // Assicura canale alpha
    .trim({ 
      threshold: 20, // Soglia più alta per rimuovere più bianco
      background: { r: 255, g: 255, b: 255, alpha: 1 }
    })
    .toBuffer();
  
  // Colore di background blu scuro (coerente con l'header)
  const bgColor = { r: 15, g: 52, b: 96, alpha: 1 }; // #0f3460
  
  for (const { size, name, maskable } of sizes) {
    const outputPath = join(__dirname, `../public/${name}`);
    
    if (maskable) {
      // Per icone maskable: crea un canvas con safe zone del 20%
      const safeZone = 0.2;
      const contentSize = Math.floor(size * (1 - safeZone * 2));
      
      // Crea un canvas con background blu scuro
      const canvas = sharp({
        create: {
          width: size,
          height: size,
          channels: 4,
          background: bgColor
        }
      });
      
      // Ridimensiona l'icona al 80% e posiziona al centro
      const resized = await sharp(processed)
        .resize(contentSize, contentSize, {
          fit: 'contain',
          background: bgColor
        })
        .toBuffer();
      
      // Composizione: canvas + icona centrata
      await canvas
        .composite([{
          input: resized,
          left: Math.floor((size - contentSize) / 2),
          top: Math.floor((size - contentSize) / 2)
        }])
        .png({ quality: 90 })
        .toFile(outputPath);
    } else {
      // Per icone standard: usa background blu scuro
      await sharp(processed)
        .resize(size, size, {
          fit: 'contain',
          background: bgColor
        })
        .flatten({ background: bgColor }) // Rimuove trasparenza e riempie con blu
        .png({ quality: 90 })
        .toFile(outputPath);
    }
    
    console.log(`✓ ${name} (${size}x${size}${maskable ? ', maskable' : ''})`);
  }
  
  console.log('\n✅ Tutte le icone generate con successo!');
}

generateIcons().catch(console.error);
