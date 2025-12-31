/**
 * Parsa il testo markdown dell'outline e estrae le sezioni (capitoli).
 * Logica simile a parse_outline_sections in backend/app/agent/writer_generator.py
 */

export interface OutlineSection {
  title: string;
  description: string;
  level: number;
  section_index: number;
}

export function parseOutlineSections(outlineText: string): OutlineSection[] {
  if (!outlineText || !outlineText.trim()) {
    return [];
  }

  const sections: Array<{ title: string; description: string; level: number }> = [];
  const lines = outlineText.split('\n');
  
  let currentSection: { title: string; description: string; level: number } | null = null;
  const currentDescription: string[] = [];
  
  for (const line of lines) {
    const trimmedLine = line.trim();
    if (!trimmedLine) {
      continue;
    }
    
    // Rileva intestazioni Markdown
    if (trimmedLine.startsWith('#')) {
      // Salva la sezione precedente se esiste
      if (currentSection) {
        currentSection.description = currentDescription.join('\n').trim();
        sections.push(currentSection);
      }
      
      // Determina il livello
      let level = 0;
      while (level < trimmedLine.length && trimmedLine[level] === '#') {
        level++;
      }
      
      // Estrae il titolo (rimuove # e spazi)
      const title = trimmedLine.substring(level).trim();
      
      if (!title) {
        // Intestazione vuota, salta
        continue;
      }
      
      // Ignora il titolo principale del documento (livello 1 all'inizio)
      if (level === 1 && sections.length === 0) {
        const titleLower = title.toLowerCase();
        if (titleLower.includes('struttura') || titleLower.includes('indice') || titleLower.includes('outline')) {
          currentSection = null;
          currentDescription.length = 0;
          continue;
        }
      }
      
      // Crea nuova sezione
      currentSection = {
        title,
        description: '',
        level
      };
      currentDescription.length = 0;
    } else if (currentSection) {
      // Aggiungi la riga alla descrizione della sezione corrente
      currentDescription.push(line);
    }
  }
  
  // Aggiungi l'ultima sezione
  if (currentSection) {
    currentSection.description = currentDescription.join('\n').trim();
    sections.push(currentSection);
  }
  
  // Filtra solo le sezioni di livello 2 o 3 (capitoli, non parti)
  // Se ci sono parti (livello 2), prendiamo i capitoli (livello 3)
  // Altrimenti prendiamo le sezioni di livello 2
  const hasParts = sections.some(s => 
    s.level === 2 && (s.title.includes('Parte') || s.title.includes('Part'))
  );
  
  let filteredSections: Array<{ title: string; description: string; level: number }>;
  
  if (hasParts) {
    // Prendi solo i capitoli (livello 3)
    filteredSections = sections.filter(s => s.level === 3);
  } else {
    // Prendi le sezioni di livello 2 (capitoli diretti)
    filteredSections = sections.filter(s => s.level === 2);
  }
  
  // Se dopo il filtro non ci sono sezioni, prova a prendere tutte le sezioni di livello 2 o 3
  if (filteredSections.length === 0) {
    filteredSections = sections.filter(s => s.level === 2 || s.level === 3);
  }
  
  // Se ancora non ci sono sezioni, prova con qualsiasi livello > 1
  if (filteredSections.length === 0) {
    filteredSections = sections.filter(s => s.level > 1);
  }
  
  // Aggiungi section_index sequenziale
  return filteredSections.map((section, index) => ({
    ...section,
    section_index: index,
  }));
}

