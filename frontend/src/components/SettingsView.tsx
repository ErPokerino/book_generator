import PageHeader from './ui/PageHeader';
import { useNotebookSound } from '../hooks/useNotebookSound';
import { Volume2 } from 'lucide-react';

export default function SettingsView() {
  const sound = useNotebookSound();
  return <div className="page-shell settings-view">
    <PageHeader title="Impostazioni" description="Rendi questo spazio un po’ più tuo." />
    <section className="notebook-panel">
      <h2><Volume2 size={21} /> Suoni di scrittura</h2>
      <p>Un piccolo suono di carta e matita accompagna la scrittura e le azioni. Con il mouse, un fruscio più lieve segue le tre scelte di creazione dopo la prima interazione. La preferenza resta salvata su questo dispositivo.</p>
      <label className="settings-switch"><input type="checkbox" data-sound-toggle checked={sound.enabled} onChange={sound.toggle} /> Attiva i suoni</label>
    </section>
    <p className="settings-footnote">Le animazioni rispettano la preferenza di movimento ridotto del dispositivo.</p>
  </div>;
}
