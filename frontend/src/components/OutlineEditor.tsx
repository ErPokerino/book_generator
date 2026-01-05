import { useState, useEffect } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { parseOutlineSections, OutlineSection } from '../utils/parseOutline';
import { updateOutline } from '../api/client';
import { useToast } from '../hooks/useToast';
import './OutlineEditor.css';

interface OutlineEditorProps {
  sessionId: string;
  outlineText: string;
  onOutlineUpdated?: (updatedOutline: string) => void;
  onCancel?: () => void;
}

export default function OutlineEditor({
  sessionId,
  outlineText,
  onOutlineUpdated,
  onCancel,
}: OutlineEditorProps) {
  const toast = useToast();
  const [sections, setSections] = useState<OutlineSection[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Parsa l'outline quando cambia il testo
  useEffect(() => {
    if (outlineText) {
      const parsed = parseOutlineSections(outlineText);
      setSections(parsed);
      setHasChanges(false);
    }
  }, [outlineText]);

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      setSections((items) => {
        const oldIndex = items.findIndex((item) => item.section_index === active.id);
        const newIndex = items.findIndex((item) => item.section_index === over.id);
        const newItems = arrayMove(items, oldIndex, newIndex);
        // Aggiorna gli indici sequenziali
        return newItems.map((item, index) => ({
          ...item,
          section_index: index,
        }));
      });
      setHasChanges(true);
    }
  };

  const handleTitleChange = (index: number, newTitle: string) => {
    setSections((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], title: newTitle };
      return updated;
    });
    setHasChanges(true);
  };

  const handleDescriptionChange = (index: number, newDescription: string) => {
    setSections((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], description: newDescription };
      return updated;
    });
    setHasChanges(true);
  };

  const handleSave = async () => {
    // Valida
    if (sections.length === 0) {
      toast.error('Deve esserci almeno un capitolo');
      return;
    }

    for (let i = 0; i < sections.length; i++) {
      if (!sections[i].title || !sections[i].title.trim()) {
        toast.error(`Il capitolo ${i + 1} deve avere un titolo`);
        return;
      }
    }

    setIsSaving(true);

    try {
      const response = await updateOutline(sessionId, sections);
      setHasChanges(false);
      if (onOutlineUpdated) {
        onOutlineUpdated(response.outline_text);
      }
      toast.success('Struttura salvata con successo!');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Errore nel salvataggio');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    // Reset alle sezioni originali
    const parsed = parseOutlineSections(outlineText);
    setSections(parsed);
    setHasChanges(false);
    if (onCancel) {
      onCancel();
    }
  };

  return (
    <div className="outline-editor">
      <div className="outline-editor-header">
        <h3>Modifica Struttura</h3>
        <p className="editor-hint">
          Modifica titoli e descrizioni dei capitoli. Trascina per riordinarli.
        </p>
      </div>


      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={sections.map((s) => s.section_index)}
          strategy={verticalListSortingStrategy}
        >
          <div className="outline-sections-list">
            {sections.map((section, index) => (
              <SortableSectionItem
                key={section.section_index}
                section={section}
                index={index}
                onTitleChange={(newTitle) => handleTitleChange(index, newTitle)}
                onDescriptionChange={(newDesc) => handleDescriptionChange(index, newDesc)}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>

      <div className="outline-editor-footer">
        <div className="editor-status">
          {hasChanges && <span className="unsaved-indicator">Modifiche non salvate</span>}
        </div>
        <div className="editor-actions">
          {onCancel && (
            <button
              type="button"
              onClick={handleCancel}
              className="btn-cancel"
              disabled={isSaving}
            >
              Annulla
            </button>
          )}
          <button
            type="button"
            onClick={handleSave}
            className="btn-save"
            disabled={isSaving || !hasChanges}
          >
            {isSaving ? 'Salvataggio...' : 'Salva modifiche'}
          </button>
        </div>
      </div>
    </div>
  );
}

interface SortableSectionItemProps {
  section: OutlineSection;
  index: number;
  onTitleChange: (newTitle: string) => void;
  onDescriptionChange: (newDescription: string) => void;
}

function SortableSectionItem({
  section,
  index,
  onTitleChange,
  onDescriptionChange,
}: SortableSectionItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: section.section_index });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`outline-section-item ${isDragging ? 'dragging' : ''}`}
    >
      <div className="section-header">
        <div className="drag-handle" {...attributes} {...listeners}>
          <span className="drag-icon">⋮⋮</span>
        </div>
        <div className="section-number">Capitolo {index + 1}</div>
        <div className="section-spacer" />
      </div>

      <div className="section-content">
        <input
          type="text"
          className="section-title-input"
          value={section.title}
          onChange={(e) => onTitleChange(e.target.value)}
          placeholder="Titolo del capitolo"
        />
        <textarea
          className="section-description-input"
          value={section.description}
          onChange={(e) => onDescriptionChange(e.target.value)}
          placeholder="Descrizione del capitolo (opzionale)"
          rows={3}
        />
      </div>
    </div>
  );
}

