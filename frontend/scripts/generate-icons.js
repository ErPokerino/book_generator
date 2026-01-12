/**
 * PWA Icon Generator for NarrAI
 * 
 * This script generates all required PWA icons from the logo image.
 * Run with: node scripts/generate-icons.js
 */

import sharp from 'sharp';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { existsSync, mkdirSync } from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const PUBLIC_DIR = join(__dirname, '..', 'public');
const LOGO_PATH = join(PUBLIC_DIR, 'logo-narrai.png');

// Theme color matching PWA manifest
const BACKGROUND_COLOR = '#0f3460';

// Icon sizes to generate
const ICON_SIZES = {
  standard: [192, 512],
  maskable: [192, 512],
  favicon: [16, 32, 180], // 180 is for apple-touch-icon
};

/**
 * Creates a solid color background
 */
async function createBackground(size, color) {
  return sharp({
    create: {
      width: size,
      height: size,
      channels: 4,
      background: color,
    },
  }).png().toBuffer();
}

/**
 * Generate standard icons with TRANSPARENT background
 * These are used for splash screen overlay
 */
async function generateStandardIcons() {
  console.log('Generating standard icons (transparent background)...');
  
  for (const size of ICON_SIZES.standard) {
    try {
      // Resize logo to fit within the icon with transparent background
      const logoSize = Math.round(size * 0.85);
      await sharp(LOGO_PATH)
        .resize(size, size, {
          fit: 'contain',
          background: { r: 0, g: 0, b: 0, alpha: 0 },
        })
        .png()
        .toFile(join(PUBLIC_DIR, `icon-${size}.png`));
      
      console.log(`  ✓ icon-${size}.png`);
    } catch (error) {
      console.error(`  ✗ icon-${size}.png:`, error.message);
    }
  }
}

/**
 * Generate maskable icons (content in safe zone - 80% center)
 * These are used by Android for adaptive icons
 */
async function generateMaskableIcons() {
  console.log('Generating maskable icons...');
  
  for (const size of ICON_SIZES.maskable) {
    try {
      // Create background
      const background = await createBackground(size, BACKGROUND_COLOR);
      
      // For maskable icons, content should be in the center 80%
      // So we make the logo smaller (60% of total size)
      const logoSize = Math.round(size * 0.55);
      const logo = await sharp(LOGO_PATH)
        .resize(logoSize, logoSize, {
          fit: 'inside',
          background: { r: 0, g: 0, b: 0, alpha: 0 },
        })
        .toBuffer();
      
      // Get logo metadata for centering
      const logoMeta = await sharp(logo).metadata();
      const left = Math.round((size - logoMeta.width) / 2);
      const top = Math.round((size - logoMeta.height) / 2);
      
      // Composite logo on background
      await sharp(background)
        .composite([{ input: logo, left, top }])
        .png()
        .toFile(join(PUBLIC_DIR, `icon-${size}-maskable.png`));
      
      console.log(`  ✓ icon-${size}-maskable.png`);
    } catch (error) {
      console.error(`  ✗ icon-${size}-maskable.png:`, error.message);
    }
  }
}

/**
 * Generate favicons
 */
async function generateFavicons() {
  console.log('Generating favicons...');
  
  try {
    // Create small favicons with background
    for (const size of [16, 32]) {
      const background = await createBackground(size, BACKGROUND_COLOR);
      const logoSize = Math.round(size * 0.7);
      const logo = await sharp(LOGO_PATH)
        .resize(logoSize, logoSize, {
          fit: 'inside',
          background: { r: 0, g: 0, b: 0, alpha: 0 },
        })
        .toBuffer();
      
      const logoMeta = await sharp(logo).metadata();
      const left = Math.round((size - logoMeta.width) / 2);
      const top = Math.round((size - logoMeta.height) / 2);
      
      const filename = size === 16 ? 'favicon-16.png' : 'favicon.png';
      await sharp(background)
        .composite([{ input: logo, left, top }])
        .png()
        .toFile(join(PUBLIC_DIR, filename));
      
      console.log(`  ✓ ${filename}`);
    }
    
    // Apple touch icon (180x180)
    const appleSize = 180;
    const appleBackground = await createBackground(appleSize, BACKGROUND_COLOR);
    const appleLogo = await sharp(LOGO_PATH)
      .resize(Math.round(appleSize * 0.7), Math.round(appleSize * 0.7), {
        fit: 'inside',
        background: { r: 0, g: 0, b: 0, alpha: 0 },
      })
      .toBuffer();
    
    const appleLogoMeta = await sharp(appleLogo).metadata();
    const appleLeft = Math.round((appleSize - appleLogoMeta.width) / 2);
    const appleTop = Math.round((appleSize - appleLogoMeta.height) / 2);
    
    await sharp(appleBackground)
      .composite([{ input: appleLogo, left: appleLeft, top: appleTop }])
      .png()
      .toFile(join(PUBLIC_DIR, 'apple-touch-icon.png'));
    
    console.log('  ✓ apple-touch-icon.png');
    
  } catch (error) {
    console.error('  ✗ Favicon generation failed:', error.message);
  }
}

/**
 * Generate SVG favicon
 */
async function generateSvgFavicon() {
  console.log('Generating SVG favicon...');
  
  try {
    // Read the logo and convert to base64 for embedding
    const logoBuffer = await sharp(LOGO_PATH)
      .resize(32, 32, {
        fit: 'inside',
        background: { r: 0, g: 0, b: 0, alpha: 0 },
      })
      .toBuffer();
    
    const logoBase64 = logoBuffer.toString('base64');
    
    // Create a simple SVG with the logo
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" fill="${BACKGROUND_COLOR}" rx="4"/>
  <image href="data:image/png;base64,${logoBase64}" x="4" y="4" width="24" height="24"/>
</svg>`;
    
    const { writeFileSync } = await import('fs');
    writeFileSync(join(PUBLIC_DIR, 'favicon.svg'), svg);
    
    console.log('  ✓ favicon.svg');
  } catch (error) {
    console.error('  ✗ favicon.svg:', error.message);
  }
}

/**
 * Main function
 */
async function main() {
  console.log('\n🎨 NarrAI PWA Icon Generator\n');
  
  // Check if logo exists
  if (!existsSync(LOGO_PATH)) {
    console.error(`❌ Logo not found at: ${LOGO_PATH}`);
    console.log('\nPlease save the NarrAI logo as "logo-narrai.png" in the public folder.');
    process.exit(1);
  }
  
  console.log(`📁 Source: ${LOGO_PATH}`);
  console.log(`📁 Output: ${PUBLIC_DIR}\n`);
  
  await generateStandardIcons();
  await generateMaskableIcons();
  await generateFavicons();
  await generateSvgFavicon();
  
  console.log('\n✅ All icons generated successfully!\n');
  console.log('Remember to rebuild the app to see changes in PWA.');
}

main().catch(console.error);
