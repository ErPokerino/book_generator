"""Behavioral tests for isolated essays, genuine evidence and durable recovery."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile
import copy
import pytest
from fastapi.testclient import TestClient

from app.essay.models import EssayBrief, EssayPlan, EssayReview, ChapterPayload, EvidenceSet, QuestionSet
from app.essay.store import EssayStore
from app.essay.main import create_app
from app.essay.citations import content_hash, validate_citations, rendered_manuscript
from app.essay.generation import dispatch, validate_plan, validate_review, grounded_search_results
from app.essay.sources import source_from_text, decode_document, validate_public_url
from app.essay.prompts import instructions
from app.essay.exports import export_book
from app.services.durable_worker import DurableWorker
from app.persistence.sqlite_store import ConcurrentUpdateError, job_lease

def plan_data():
    return {"title":"Le ragioni del confronto","subtitle":"Un saggio di prova","direction":"Il confronto chiarisce i presupposti.",
        "method":"Analisi concettuale", "definitions":["Argomento: una ragione a sostegno di una conclusione."],
        "claims":[{"id":"A1","text":"Le premesse devono essere esplicite.","kind":"normative","reason":"Consentono un confronto.",
                   "evidence_ids":[],"objection":"Esplicitare ogni premessa è difficile.","response":"Selezionare le premesse rilevanti.","gap":""}],
        "sections":[{"id":"C1","title":"Premesse","purpose":"Definire","description":"Distinguere ragioni e conclusioni.","claim_ids":["A1"],"word_target":500},
                    {"id":"C2","title":"Confronto","purpose":"Discutere","description":"Confrontare obiezioni e risposte.","claim_ids":["A1"],"word_target":500}],
        "limits":["Non viene descritto un esperimento empirico."]}

@pytest.fixture
def store(tmp_path):
    return EssayStore(tmp_path/"saggia.sqlite3")

@pytest.fixture
def client(store):
    with TestClient(create_app(store,run_worker=False)) as client:
        yield client

def create(client,**changes):
    response=client.post("/api/essays",json={"topic":"Le ragioni del confronto","target_words":1000,**changes})
    assert response.status_code==201,response.text
    return response.json()

def ready(store,**changes):
    session=store.create_session("P1",EssayBrief(topic="Le ragioni del confronto",target_words=1000,**changes))
    session.plan=plan_data()
    session.validated=True
    store.save_session(session)
    return session

def add_evidence(session,*,sid="S1",eid="E1",author="Rossi",published="2020",title="Le premesse"):
    text="Una premessa è una proposizione utilizzata per sostenere una conclusione."
    source=source_from_text(title,text,author=author,published=published,kind="document")
    source.update(id=sid,status="analyzed")
    source["evidence"]=[{"id":eid,"source_id":sid,"quote":text,"locator":"Caratteri 1–70","start":0,"end":len(text),
                         "stance":"context","explanation":"Definizione, non una dimostrazione empirica.","reviewed":True}]
    session.sources.append(source)

@pytest.mark.parametrize("profile",["argumentative","popular","academic"])
@pytest.mark.parametrize("role",["challenge","support","explore"])
def test_nine_choices_are_independent_and_survive_restart(client,store,profile,role):
    project=create(client,profile=profile,ai_role=role)
    loaded=EssayStore(store.db_path).get_session(project["session_id"])
    assert loaded.form_data.profile==profile
    assert loaded.form_data.ai_role==role
    assert "pubblico è adulto" in instructions(loaded.form_data)
    assert "plot" not in project["form_data"]

def test_rejects_legacy_and_unavailable_models(client):
    assert client.post("/api/essays",json={"topic":"Test valido","plot":"Trama"}).status_code==422
    assert client.post("/api/essays",json={"topic":"Test valido","llm_model":"unknown"}).status_code==422
    assert client.post("/api/essays",json={"topic":"Test valido","model_overrides":{"manga":"gemini-3.8-flash"}}).status_code==422

def test_archive_does_not_import_narrative_json(tmp_path,monkeypatch):
    monkeypatch.setenv("NARRAI_DB_PATH",str(tmp_path/"narrai.sqlite3"))
    (tmp_path/".sessions.json").write_text('{"damaged":"do not import"}')
    store=EssayStore(tmp_path/"essay.sqlite3")
    assert store.get_all_sessions()=={}
    assert not (tmp_path/"narrai.sqlite3").exists()
    with store.connection() as db:
        assert db.execute("SELECT value FROM metadata WHERE key='product_id'").fetchone()[0]=="saggia"

def test_archive_rejects_existing_other_product(tmp_path):
    from app.persistence.sqlite_store import SQLiteSessionStore
    from app.models import SubmissionRequest
    original=SQLiteSessionStore(tmp_path/"original.sqlite3")
    original.create_session("romanzo",SubmissionRequest(llm_model="gemini-3.8-flash",plot="Una storia"),[])
    with pytest.raises(ValueError,match="senza identità"):
        EssayStore(tmp_path/"original.sqlite3")
    assert original.get_session("romanzo").form_data.plot=="Una storia"

def test_edit_conflict_preserves_first_changes(client):
    project=create(client)
    sid=project["session_id"]
    first=project["form_data"]|{"thesis":"Prima posizione"}
    assert client.put("/api/essays/"+sid+"/brief",json={"brief":first,"expected_version":1}).status_code==200
    second=project["form_data"]|{"thesis":"Seconda posizione"}
    assert client.put("/api/essays/"+sid+"/brief",json={"brief":second,"expected_version":1}).status_code==409
    assert client.get("/api/essays/"+sid).json()["form_data"]["thesis"]=="Prima posizione"

def test_approval_is_tied_to_read_version_and_required_for_writing(client):
    p=create(client)
    sid=p["session_id"]
    assert client.post("/api/essays/"+sid+"/jobs/book").status_code==422
    p=client.put("/api/essays/"+sid+"/plan",json={"plan":plan_data(),"expected_version":1}).json()
    assert client.post("/api/essays/"+sid+"/approve",json={"expected_version":1}).status_code==409
    assert client.post("/api/essays/"+sid+"/approve",json={"expected_version":p["current_version"]}).status_code==200
    assert client.post("/api/essays/"+sid+"/jobs/book").status_code==200

def test_active_job_prevents_edits_and_delete(client):
    p=create(client);sid=p["session_id"]
    assert client.post("/api/essays/"+sid+"/jobs/questions").status_code==200
    assert client.put("/api/essays/"+sid+"/brief",json={"brief":p["form_data"],"expected_version":1}).status_code==409
    assert client.delete("/api/essays/"+sid).status_code==409

def test_material_and_literal_evidence_round_trip(client):
    p=create(client);sid=p["session_id"]
    text="L'autore dichiara un'esperienza personale senza attribuirla a uno studio."
    p=client.post("/api/essays/"+sid+"/sources",json={"title":"Appunti","text":text,"kind":"author_notes"}).json()
    source=p["sources"][0]
    base="/api/essays/"+sid+"/sources/"+source["id"]
    assert "text" not in source
    assert client.get(base).json()["text"]==text
    assert client.post(base+"/evidence",json={"quote":"Un passaggio completamente inventato."}).status_code==422
    p=client.post(base+"/evidence",json={"quote":text,"stance":"context","explanation":"Esperienza dichiarata."}).json()
    assert p["sources"][0]["evidence"][0]["reviewed"]
    assert not p["validated"]

def test_document_upload_and_scanned_pdf_detection(client):
    p=create(client);sid=p["session_id"]
    raw="Documento con una definizione utile al saggio.".encode()
    assert client.post("/api/essays/"+sid+"/upload",files={"file":("appunti.md",raw)}).status_code==200
    from reportlab.pdfgen import canvas
    buffer=BytesIO();pdf=canvas.Canvas(buffer);pdf.showPage();pdf.save()
    with pytest.raises(ValueError,match="OCR"):
        decode_document(buffer.getvalue(),"scan.pdf")
    with pytest.raises(ValueError,match="Formato"):
        decode_document(b"123456","image.png")

@pytest.mark.asyncio
@pytest.mark.parametrize("url",["http://127.0.0.1/test","http://localhost/test","file:///etc/passwd","https://user:pass@example.com"])
async def test_private_or_credentialed_urls_rejected(url):
    with pytest.raises(ValueError):
        await validate_public_url(url)

def test_unknown_citation_rejected_and_same_source_has_one_bibliographic_entry(store):
    session=ready(store)
    add_evidence(session)
    with pytest.raises(ValueError):
        validate_citations("Testo [@unknown]",session.sources)
    session.book_chapters=[{"section_id":"C1","section_index":0,"title":"Premesse",
        "content":"Una definizione [@E1]. Ancora la stessa fonte [@E1].","unresolved":[]}]
    chapters,bibliography=rendered_manuscript(session)
    assert chapters[0]["display_content"].count("[1]")==2
    assert len(bibliography)==1

def test_author_date_disambiguation_and_reorder(store):
    session=ready(store,citation_style="author_date")
    add_evidence(session)
    add_evidence(session,sid="S2",eid="E2",title="Altra opera")
    session.book_chapters=[{"section_id":"C1","section_index":0,"title":"Premesse","content":"Primo [@E2]. Secondo [@E1].","unresolved":[]}]
    chapters,bibliography=rendered_manuscript(session)
    assert "Rossi, 2020a" in chapters[0]["display_content"]
    assert "Rossi, 2020b" in chapters[0]["display_content"]
    assert [s["id"] for s in bibliography]==["S2","S1"]

def test_chapter_revision_conflict_and_invalidation(store):
    session=ready(store)
    session.book_chapters=[{"section_id":"C1","section_index":0,"title":"Premesse","content":"Versione originale.","unresolved":[]}]
    session.review={"summary":"Controllo precedente"}
    store.save_session(session)
    oldhash=content_hash("Versione originale.")
    store.edit_chapter("P1",0,"Versione aggiornata.",oldhash)
    with pytest.raises(ConcurrentUpdateError):
        store.edit_chapter("P1",0,"Tentativo concorrente.",oldhash)
    assert len(store.chapter_revisions("P1",0))==2
    assert store.get_session("P1").review is None
    assert store.get_session("P1").book_chapters[0]["content"]=="Versione aggiornata."

@pytest.mark.parametrize("format",["pdf","epub","docx"])
@pytest.mark.parametrize("style",["numeric","author_date"])
def test_exports_have_real_citations_and_bibliography(store,format,style):
    session=ready(store,citation_style=style)
    add_evidence(session)
    session.book_chapters=[{"section_id":"C1","section_index":0,"title":"Premesse",
        "content":"La definizione orienta il confronto [@E1].\n\nUna conclusione è distinta dalla premessa.","unresolved":[]}]
    data,media=export_book(session,format)
    assert len(data)>800
    if format=="pdf":
        from pypdf import PdfReader
        text="\n".join(p.extract_text() or "" for p in PdfReader(BytesIO(data)).pages)
    elif format=="docx":
        from docx import Document
        text="\n".join(p.text for p in Document(BytesIO(data)).paragraphs)
    else:
        with ZipFile(BytesIO(data)) as archive:
            text="\n".join(archive.read(n).decode() for n in archive.namelist() if n.endswith(".xhtml"))
    assert "Bibliografia" in text
    assert "Rossi" in text
    assert "[@E1]" not in text
    assert ("[1]" if style=="numeric" else "Rossi, 2020") in text

def test_plan_and_review_do_not_accept_invented_references(store):
    session=ready(store,profile="academic")
    data=plan_data();data["method"]=""
    with pytest.raises(ValueError,match="metodo"):
        validate_plan(EssayPlan(**data),session)
    data=plan_data();data["claims"][0]["evidence_ids"]=["fake"]
    with pytest.raises(ValueError,match="evidenza"):
        validate_plan(EssayPlan(**data),session)
    review=EssayReview(summary="Problema",issues=[{"section_id":"C1","quote":"Frase inventata.","category":"logic","severity":"important","explanation":"Errore","suggestion":"Correggi"}])
    with pytest.raises(ValueError,match="passaggio"):
        validate_review(review,[{"section_id":"C1","content":"Testo effettivo."}])

@pytest.mark.asyncio
async def test_pipeline_and_resume_do_not_regenerate_saved_chapters(store,monkeypatch):
    import app.essay.generation as generation
    session=ready(store,revision_mode="writing")
    original="Testo già salvato che deve restare identico."
    session.book_chapters=[{"section_id":"C1","section_index":0,"title":"Premesse","content":original,"summary":"Premesse.","unresolved":[],"review_stale":False}]
    store.save_session(session)
    requests=[]
    async def fake(session,phase,prompt,schema=None,**kwargs):
        requests.append(phase)
        return ChapterPayload(content=("Una ragione richiede una premessa esplicita e una conclusione distinta. "*30),
                              unresolved=[],summary="Il confronto rende esplicite le premesse.")
    monkeypatch.setattr(generation,"request",fake)
    store.enqueue("P1","book")
    await DurableWorker(store,handler=dispatch).run_once()
    result=store.get_session("P1")
    assert result.writing_progress["status"]=="completed"
    assert result.book_chapters[0]["content"]==original
    assert requests==["chapters"]
    assert store.list_jobs("P1")[0]["status"]=="completed"

@pytest.mark.asyncio
async def test_part_checkpoint_survives_failure_and_pause(store,monkeypatch):
    import app.essay.generation as generation
    session=ready(store,revision_mode="writing")
    session.plan["sections"][0]["word_target"]=2000
    store.save_session(session)
    calls=0
    async def failing(session,phase,prompt,schema=None,**kwargs):
        nonlocal calls
        calls+=1
        if calls==2: raise RuntimeError("Rete interrotta")
        return ChapterPayload(content=("La prima parte contiene ragioni e premesse distinguibili. "*70),unresolved=[],summary="Prima parte.")
    monkeypatch.setattr(generation,"request",failing)
    store.enqueue("P1","book")
    await DurableWorker(store,handler=dispatch).run_once()
    result=store.get_session("P1")
    assert result.writing_progress["status"]=="paused"
    assert len(result.part_checkpoint["parts"])==1
    first=result.part_checkpoint["parts"][0]["content"]
    async def working(session,phase,prompt,schema=None,**kwargs):
        if '"part": 2' in prompt:
            store.mutate("P1",lambda s:setattr(s,"pause_requested",True),allow_active=True)
        return ChapterPayload(content=("La seconda parte sviluppa il confronto delle ragioni. "*70),unresolved=[],summary="Seguito.")
    monkeypatch.setattr(generation,"request",working)
    store.enqueue("P1","book")
    await DurableWorker(store,handler=dispatch).run_once()
    result=store.get_session("P1")
    assert len(result.book_chapters)==1
    assert result.book_chapters[0]["content"].startswith(first)
    assert result.writing_progress["status"]=="paused"
    assert result.part_checkpoint is None

@pytest.mark.asyncio
async def test_missing_key_is_a_persisted_failure(store,monkeypatch):
    ready(store)
    monkeypatch.delenv("GOOGLE_API_KEY",raising=False)
    store.enqueue("P1","questions")
    await DurableWorker(store,handler=dispatch).run_once()
    result=store.get_session("P1")
    assert result.questions_progress["status"]=="failed"
    assert "GOOGLE_API_KEY" in result.questions_progress["error"]

def test_search_extracts_only_provider_grounded_urls():
    response=SimpleNamespace(candidates=[SimpleNamespace(grounding_metadata=SimpleNamespace(
        grounding_chunks=[SimpleNamespace(web=SimpleNamespace(uri="https://example.com/paper",title="Paper")),
                          SimpleNamespace(web=SimpleNamespace(uri="https://example.com/paper",title="Duplicate"))],
        web_search_queries=["query"],search_entry_point=None))])
    records,queries,suggestions=grounded_search_results(response)
    assert len(records)==1
    assert queries==["query"]

def test_duplicate_id_cannot_replace_existing_project(store):
    store.create_session("same",EssayBrief(topic="Prima opera"))
    with pytest.raises(ConcurrentUpdateError):
        store.create_session("same",EssayBrief(topic="Seconda opera"))
    assert store.get_session("same").form_data.topic=="Prima opera"

def test_source_metadata_version_and_active_search_are_atomic(client,store):
    project=create(client)
    sid=project["session_id"]
    project=client.post(f"/api/essays/{sid}/sources",json={"title":"Fonte da completare","text":"Una premessa esplicita aiuta a capire le ragioni di una conclusione."}).json()
    source=project["sources"][0]
    updated=client.put(f"/api/essays/{sid}/sources/{source['id']}",json={"title":"Titolo definitivo","author":"Autore verificato","published":"2025","expected_version":1})
    assert updated.status_code==200
    assert updated.json()["current_version"]>project["current_version"]
    assert updated.json()["sources"][0]["author"]=="Autore verificato"
    assert client.put(f"/api/essays/{sid}/sources/{source['id']}",json={"title":"Vecchia modifica","expected_version":1}).status_code==409
    first=client.post(f"/api/essays/{sid}/research",json={"query":"prima ricerca"}).json()
    assert first["active"]
    assert client.post(f"/api/essays/{sid}/research",json={"query":"seconda ricerca"}).status_code==409
    assert store.get_session(sid).research_request["query"]=="prima ricerca"

def test_concurrent_identical_jobs_only_enqueue_once(store):
    from concurrent.futures import ThreadPoolExecutor
    ready(store)
    with ThreadPoolExecutor(max_workers=5) as threads:
        results=list(threads.map(lambda _:store.enqueue("P1","book"),range(5)))
    assert sum(created for created,_ in results)==1
    assert len(store.list_jobs("P1"))==1

def test_late_assigned_evidence_is_never_dropped_from_context(store):
    from app.essay.prompts import source_context
    session=ready(store)
    for index in range(125):
        add_evidence(session,sid=f"S{index}",eid=f"E{index}")
    context=source_context(session,limit=10,priority_ids=["E124"])
    assert context[0]["evidence_id"]=="E124"
    assert len(context)==10

@pytest.mark.asyncio
async def test_research_resumes_discovery_checkpoint_without_search_purchase(store,monkeypatch):
    from app.essay.generation import research
    session=ready(store)
    source=source_from_text("Titolo","Un documento rilevante che può essere acquisito per la ricerca.",url="https://example.org/source",kind="web")
    source.update(status="proposed",text="",evidence=[])
    session.sources=[source]
    session.research_request={"query":"ricerca già pagata","discovered":True}
    store.save_session(session)
    async def fake_acquire(url,title):
        return {"url":url,"title":title,"text":"Una premessa esplicita è utile a comprendere la conclusione."}
    calls=[]
    async def fake_request(session,phase,*args,**kwargs):
        calls.append(phase)
        assert phase=="evidence"
        return EvidenceSet(excerpts=[])
    monkeypatch.setattr("app.essay.generation.acquire_url",fake_acquire)
    monkeypatch.setattr("app.essay.generation.request",fake_request)
    await research(store,store.get_session("P1"))
    assert calls==["evidence"]
    assert store.get_session("P1").sources[0]["status"]=="analyzed"

def test_exact_target_allocation_and_incompatible_index(store):
    session=ready(store)
    payload=plan_data()
    payload["sections"][0]["word_target"]=200
    payload["sections"][1]["word_target"]=8000
    result=validate_plan(EssayPlan(**payload),session)
    assert sum(s.word_target for s in result.sections)==1000
    payload["sections"] += [payload["sections"][0]|{"id":f"C{i}"} for i in range(3,9)]
    with pytest.raises(ValueError,match="numero di capitoli"):
        validate_plan(EssayPlan(**payload),session)

def test_provider_schema_omits_unsupported_keywords_but_local_validation_remains_strict():
    import json
    schema=json.dumps(QuestionSet.model_json_schema())
    assert "additionalProperties" not in schema
    with pytest.raises(ValueError):
        QuestionSet(questions=[{"id":"Q1","text":"Domanda","unexpected":"field"}])

def test_retry_failed_web_source_preserves_source_identity_and_updates_snapshot(client,store,monkeypatch):
    project=create(client)
    sid=project["session_id"]
    session=store.get_session(sid)
    source=source_from_text("Test","Un testo preliminare per un documento pubblico.",url="https://example.org/paper",kind="web")
    source.update(status="failed",text="",error="Timeout")
    session.sources=[source]
    store.save_session(session)
    async def acquire(url,title):
        return {"url":url,"title":title,"text":"Il documento realmente acquisito contiene un passaggio utile."}
    monkeypatch.setattr("app.essay.main.acquire_url",acquire)
    response=client.post(f"/api/essays/{sid}/sources/{source['id']}/retry")
    assert response.status_code==200
    assert response.json()["sources"][0]["id"]==source["id"]
    assert response.json()["sources"][0]["status"]=="acquired"
    assert store.get_session(sid).sources[0]["text"].startswith("Il documento realmente")

@pytest.mark.asyncio
async def test_malformed_chapter_reference_is_repaired_once_without_accepting_unknown_ids(store,monkeypatch):
    from app.essay.generation import checked_chapter
    session=ready(store)
    add_evidence(session)
    outputs=[ChapterPayload(content="Una premessa esplicita chiarisce il confronto. [@E1, @E1] "+"Parole di sviluppo. "*30,summary="Premesse."),
             ChapterPayload(content="Una premessa esplicita chiarisce il confronto. [@E1] "+"Parole di sviluppo. "*30,summary="Premesse.")]
    prompts=[]
    async def fake_request(session,phase,prompt,schema):
        prompts.append(prompt)
        return outputs.pop(0)
    monkeypatch.setattr("app.essay.generation.request",fake_request)
    result=await checked_chapter(session,"chapters","Sviluppa una premessa",target_words=200)
    assert validate_citations(result.content,session.sources)==["E1"]
    assert len(prompts)==2
    assert "due marcatori separati" in prompts[1]

@pytest.mark.asyncio
async def test_repeated_bad_reference_stops_after_one_correction(store,monkeypatch):
    from app.essay.generation import checked_chapter
    session=ready(store)
    calls=[]
    async def bad(*args,**kwargs):
        calls.append(1)
        return ChapterPayload(content="Non è una fonte registrata. [@inventata] "+"Testo sviluppato. "*30,summary="Sintesi.")
    monkeypatch.setattr("app.essay.generation.request",bad)
    with pytest.raises(ValueError,match="senza un estratto"):
        await checked_chapter(session,"chapters","Prompt")
    assert len(calls)==2

def test_plan_change_archives_incomplete_parts_and_syncs_existing_chapter_titles(client,store):
    session=ready(store)
    session.part_checkpoint={"section_id":"C2","parts":[{"content":"Vecchia direzione","summary":"Vecchio","unresolved":[]}]}
    session.book_chapters=[{"section_id":"C1","section_index":0,"title":"Premesse","content":"Testo salvato.","summary":"","unresolved":[]}]
    store.save_session(session)
    payload=plan_data()
    payload["sections"][0]["title"]="Titolo aggiornato"
    response=client.put("/api/essays/P1/plan",json={"plan":payload,"expected_version":1})
    assert response.status_code==200
    assert response.json()["book_chapters"][0]["title"]=="Titolo aggiornato"
    session=store.get_session("P1")
    assert session.part_checkpoint is None
    assert session.checkpoint_history[0]["checkpoint"]["parts"][0]["content"]=="Vecchia direzione"
    assert session.book_chapters[0]["content"]=="Testo salvato."

def test_html_metadata_uses_original_header_fields():
    from app.essay.sources import TextHTML
    parser=TextHTML()
    parser.feed('<html><head><title>Titolo reale</title><meta name="citation_author" content="Autore Uno"><meta name="citation_author" content="Autore Due"><meta name="citation_publication_date" content="2025/04/02"></head><body><p>Testo originale.</p><script>istruzioni malevole</script></body></html>')
    assert parser.authors==["Autore Uno","Autore Due"]
    assert parser.published=="2025/04/02"
    assert parser.title==["Titolo reale"]
    assert parser.text()=="Testo originale."

@pytest.mark.asyncio
async def test_cover_export_in_all_formats_and_very_long_titles(store):
    from app.essay.cover import make_cover
    from PIL import Image
    session=ready(store)
    session.form_data.title="Un titolo molto lungo e importante " * 8
    session.form_data.subtitle="Un sottotitolo che chiarisce la prospettiva e il perimetro del saggio. " * 7
    session.form_data.author_name="Autore con nome lungo " * 8
    session.book_chapters=[{"section_id":"C1","section_index":0,"title":"Premesse","content":"Argomenti testuali per verificare la copertina.","summary":"","unresolved":[]}]
    store.save_session(session)
    await make_cover(store,store.get_session("P1"))
    session=store.get_session("P1")
    image=Image.open(session.cover_image_path)
    assert image.size==(1000,1500)
    for format in ("pdf","epub","docx"):
        data,media=export_book(session,format)
        assert len(data)>2000
        if format=="pdf":
            from pypdf import PdfReader
            assert len(PdfReader(BytesIO(data)).pages)>=4
        if format=="docx":
            from docx import Document
            assert len(Document(BytesIO(data)).inline_shapes)==1
        if format=="epub":
            with ZipFile(BytesIO(data)) as archive:
                assert any(name.endswith("cover.png") for name in archive.namelist())

def test_production_frontend_does_not_turn_unknown_api_paths_into_html(client):
    assert client.get("/api/does-not-exist").status_code==404

def test_profile_defaults_apply_at_api_and_preserve_author_choices(client):
    academic=create(client,profile="academic",ai_role="explore")
    assert academic["form_data"]["language_register"]=="academic"
    assert academic["form_data"]["citation_style"]=="author_date"
    assert academic["form_data"]["purpose"]=="analizzare"
    popular=create(client,profile="popular",language_register="essayistic")
    assert popular["form_data"]["purpose"]=="divulgare"
    assert popular["form_data"]["language_register"]=="essayistic"

@pytest.mark.asyncio
async def test_free_typographic_cover_still_works_after_ai_budget_reached(store,monkeypatch):
    session=ready(store,budget_eur=.01)
    monkeypatch.setattr("app.essay.generation.usage_summary",lambda *args:{"converted_cost_eur":.1})
    store.enqueue("P1","cover")
    assert await DurableWorker(store,handler=dispatch).run_once()
    session=store.get_session("P1")
    assert session.cover_progress["status"]=="completed"
    assert Path(session.cover_image_path).exists()


def test_library_metrics_use_the_same_ledger_as_the_studio(store, client, monkeypatch):
    session=ready(store)
    session.book_chapters=[{"section_id":"C1","section_index":0,"title":"Premesse","content":"parola " * 501,"unresolved":[]}]
    store.save_session(session)
    monkeypatch.setattr("app.essay.main.usage_summary",lambda *args:{
        "converted_cost_eur":.302,"coverage_complete":True,"calls":23,"events":[{"tool_cost_unknown":True}]})
    row=client.get("/api/essays").json()[0]
    assert row["estimated_pages"]==3
    assert row["generation_cost_eur"]==.302
    assert row["cost_coverage_complete"] is False
    assert row["generation_calls"]==23
    assert row["active"] is False
    detail=client.get("/api/essays/P1").json()
    assert detail["estimated_pages"]==row["estimated_pages"]
    assert detail["usage"]["converted_cost_eur"]==row["generation_cost_eur"]


def test_library_does_not_invent_a_price_or_pages_before_generation(client):
    create(client)
    row=client.get("/api/essays").json()[0]
    assert row["estimated_pages"]==0
    assert row["generation_cost_eur"] is None
    assert row["generation_calls"]==0


def test_library_delete_removes_only_the_selected_book(client):
    first=create(client)
    second=create(client,topic="Un altro libro da conservare")
    assert client.delete("/api/essays/"+first["session_id"]).status_code==204
    assert client.get("/api/essays/"+first["session_id"]).status_code==404
    assert [s["id"] for s in client.get("/api/essays").json()]==[second["session_id"]]


def test_pdf_has_navigable_contents_body_folios_and_semantic_markdown(store):
    from pypdf import PdfReader
    session=ready(store,author_name="Autore di prova")
    session.book_chapters=[
        {"section_id":"C1","section_index":0,"title":"Ragioni e obiezioni",
         "content":"## Una distinzione necessaria\n\nUn termine **essenziale** e una prospettiva *prudente*.\n\n"
          "- Prima ragione\n- Seconda ragione\n\n> Una citazione distinta dal testo.\n\n"
          "| Idea | Riscontro |\n| --- | --- |\n| Premessa | Fonte attendibile |\n\n"
          +("\n\n"+"Il confronto delle ragioni esplicita presupposti, obiezioni e limiti. "*35)*7,
         "unresolved":[]},
        {"section_id":"C2","section_index":1,"title":"Le conclusioni","content":"Un esito leggibile e verificabile.","unresolved":[]},
    ]
    data,_=export_book(session,"pdf")
    reader=PdfReader(BytesIO(data))
    assert abs(float(reader.pages[0].mediabox.width)-419.53)<1
    pages=[p.extract_text() or "" for p in reader.pages]
    assert "Indice" in pages[1]
    assert "Ragioni e obiezioni" in pages[1] and "Le conclusioni" in pages[1]
    assert len(reader.outline)==2
    assert any(a.get_object().get("/Subtype")=="/Link" for a in reader.pages[1].get("/Annots",[]))
    assert "CAPITOLO 01" in pages[2] and pages[2].rstrip().endswith("1")
    text="\n".join(pages)
    for phrase in ("essenziale","prudente","Prima ragione","Seconda ragione","Fonte attendibile","Una citazione distinta"):
        assert phrase in text
    assert "| ---" not in text and "**essenziale**" not in text
    assert session.plan["title"] in pages[3]  # even continuation page carries the book title
    assert "Ragioni e obiezioni" in pages[4]  # odd continuation page carries the chapter title


def test_pdf_cache_is_invalidated_by_manuscript_edits(store,monkeypatch):
    import app.essay.pdf_layout as layout
    session=ready(store)
    session.book_chapters=[{"section_id":"C1","section_index":0,"title":"Premesse","content":"Testo originale.","unresolved":[]}]
    layout._cached_pdf.cache_clear()
    render=layout._render_pdf
    calls=[]
    def counted(*args,**kwargs):
        calls.append(1)
        return render(*args,**kwargs)
    monkeypatch.setattr(layout,"_render_pdf",counted)
    first,_=export_book(session,"pdf")
    second,_=export_book(session,"pdf")
    assert first==second and len(calls)==1
    session.book_chapters[0]["content"]+="\n\nUn nuovo argomento."
    third,_=export_book(session,"pdf")
    assert third!=first and len(calls)==2


def test_pdf_splits_long_tables_preserves_nested_lists_and_entities(store):
    from pypdf import PdfReader
    session=ready(store)
    session.book_chapters=[{"section_id":"C1","section_index":0,"title":"Metodo",
        "content":"Un simbolo &copy; e un nome&nbsp;composto.\n\n"
         "- Ragione principale\n    - Una ragione subordinata\n\n"
         "| Dato | Interpretazione |\n| --- | --- |\n| A | "+("Argomento verificabile. "*300)+" |\n\nTesto finale preservato.",
        "unresolved":[]}]
    data,_=export_book(session,"pdf")
    text="\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages)
    assert "Testo finale preservato." in text
    assert "Una ragione subordinata" in text
    import re
    assert len(re.findall(r"\bArgomento\b",text))==300
    assert text.count("verificabile.")==300
    assert "©" in text
