import sharp from 'sharp';
import {fileURLToPath} from 'url';
import {dirname,join} from 'path';
import {copyFileSync} from 'fs';
const dir=join(dirname(fileURLToPath(import.meta.url)),'..','public');
for(const [name,size,padding] of [
 ['icon-192.png',192,0],['icon-512.png',512,0],['icon-192-maskable.png',192,.2],
 ['icon-512-maskable.png',512,.2],['favicon.png',32,0],['favicon-16.png',16,0],['apple-touch-icon.png',180,0],
]){
 const inner=Math.round(size*(1-padding));
 const logo=await sharp(join(dir,'saggia-mark.svg')).resize(inner,inner).png().toBuffer();
 await sharp({create:{width:size,height:size,channels:4,background:'#163b39'}})
  .composite([{input:logo,left:Math.round((size-inner)/2),top:Math.round((size-inner)/2)}]).png().toFile(join(dir,name));
 console.log(name);
}
copyFileSync(join(dir,'saggia-mark.svg'),join(dir,'favicon.svg'));
