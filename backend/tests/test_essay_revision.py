"""Delegated corrections: concurrency, recovery, citations, bounded passes and chapter history."""
from io import BytesIO
import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from app.essay.models import EssayBrief, EssayReview, ChapterPayload
from app.essay.store import EssayStore
from app.essay.main import create_app
from app.essay.generation import dispatch
from app.essay.citations import content_hash
from app.services.durable_worker import DurableWorker
from test_essay_product import plan_data

@pytest.fixture
def store(tmp_path):
    return EssayStore(tmp_path/"revision.sqlite3")

@pytest.fixture
def client(store):
    with TestClient(create_app(store,run_worker=False)) as client:
        yield client

def issue(section_id="C1",severity="important"):
    return {"section_id":section_id,"quote":"","category":"style","severity":severity,
            "explanation":"La formulazione va precisata.","suggestion":"Rendi più esplicita la premessa."}

def ready(store,issues=None):
    s=store.create_session("P1",EssayBrief(topic="Le ragioni del confronto",target_words=1000))
    s.plan=plan_data();s.validated=True
    s.book_chapters=[{"section_id":"C"+str(i+1),"section_index":i,"title":title,
        "content":("Una premessa originale offre una ragione da discutere e qualificare. "*20),
        "summary":"Una premessa.", "unresolved":[],"review_stale":False}
        for i,title in enumerate(["Premesse","Confronto"])]
    s.review={"summary":"Un rapporto concreto.","strengths":[],"issues":issues if issues is not None else [issue()],
              "at":"original-report","partial":False}
    store.save_session(s)
    return store.get_session("P1")

def payload(client,resume=False):
    p=client.get("/api/essays/P1").json()
    return {"expected_version":p["current_version"],"expected_review_at":(p["review"] or {}).get("at",""),
            "expected_hashes":{c["section_id"]:c["hash"] for c in p["book_chapters"]},"resume":resume}

def parsed_prompt(prompt):
    return json.JSONDecoder().raw_decode(prompt)[0]

def fake_pipeline(monkeypatch,*,review_issues=None):
    calls=[]
    async def request(session,phase,prompt,schema=None,**kwargs):
        data=parsed_prompt(prompt)
        calls.append((phase,data))
        if phase=="revision":
            return ChapterPayload(content=data["chapter"]["content"].replace("originale","precisata"),
                summary="Premessa precisata.",unresolved=[])
        return EssayReview(summary="Controllo successivo.",issues=review_issues or [])
    monkeypatch.setattr("app.essay.generation.request",request)
    return calls

@pytest.mark.parametrize("change,status",[
    ({"expected_version":9},409),({"expected_hashes":{"C1":"outdated"}},409),
    ({"expected_review_at":"outdated-report"},409)])
def test_stale_requests_cannot_start_corrections(client,store,change,status):
    ready(store)
    response=client.post("/api/essays/P1/revision",json=payload(client)|change)
    assert response.status_code==status,response.text
    assert store.list_jobs("P1")==[]

@pytest.mark.parametrize("issues",[[],None])
def test_requires_a_report_with_issues(client,store,issues):
    s=ready(store,issues=[])
    if issues is None:
        s.review=None;store.save_session(s)
    assert client.post("/api/essays/P1/revision",json=payload(client)).status_code==422

def test_enqueue_is_idempotent_and_locks_manual_edits(client,store):
    original=ready(store);p=payload(client)
    first=client.post("/api/essays/P1/revision",json=p)
    assert first.status_code==200,first.text
    assert "revision_request" not in first.json()
    assert client.post("/api/essays/P1/revision",json=p).status_code==200
    assert len(store.list_jobs("P1"))==1
    assert client.put("/api/essays/P1/chapters/0",json={"content":"Una modifica.","expected_hash":content_hash(original.book_chapters[0]["content"])}).status_code==409
    assert client.post("/api/essays/P1/jobs/review").status_code==409

@pytest.mark.asyncio
async def test_applies_all_targeted_issues_rechecks_and_preserves_versions(client,store,monkeypatch):
    original=ready(store,issues=[issue("C1","blocking"),issue("C1","suggestion")])
    calls=fake_pipeline(monkeypatch)
    assert client.post("/api/essays/P1/revision",json=payload(client)).status_code==200
    await DurableWorker(store,handler=dispatch).run_once()
    final=store.get_session("P1")
    assert [phase for phase,_ in calls]==["revision","review"]
    assert len(calls[0][1]["issues"])==2
    assert "precisata" in final.book_chapters[0]["content"]
    assert final.book_chapters[1]["content"]==original.book_chapters[1]["content"]
    assert final.validated and final.plan==original.plan
    assert final.review["issues"]==[] and not final.review["partial"]
    assert not final.book_chapters[0]["review_stale"]
    assert final.revision_progress["status"]=="completed"
    assert final.revision_progress["updated_sections"]==1
    assert final.revision_progress["remaining_issues"]==0
    assert any(v["content"]==original.book_chapters[0]["content"] for v in store.chapter_revisions("P1",0))
    assert final.review["manuscript_hashes"]["C1"]==content_hash(final.book_chapters[0]["content"])

@pytest.mark.asyncio
async def test_global_issues_are_applied_to_all_chapters(client,store,monkeypatch):
    ready(store,issues=[issue("")])
    calls=fake_pipeline(monkeypatch)
    client.post("/api/essays/P1/revision",json=payload(client))
    await DurableWorker(store,handler=dispatch).run_once()
    edits=[data for phase,data in calls if phase=="revision"]
    assert [data["chapter"]["section_id"] for data in edits]==["C1","C2"]
    assert "precisata" in edits[1]["other_chapters"][0]["opening"]
    assert store.get_session("P1").revision_progress["updated_sections"]==2

@pytest.mark.asyncio
async def test_two_automatic_passes_then_reports_remaining_issues(client,store,monkeypatch):
    ready(store)
    calls=[]
    async def request(session,phase,prompt,schema=None,**kwargs):
        data=parsed_prompt(prompt);calls.append(phase)
        if phase=="revision":
            return ChapterPayload(content=data["chapter"]["content"]+" Una precisazione aggiuntiva.",
                                  summary="Precisato.",unresolved=["Occorre un materiale ulteriore."])
        return EssayReview(summary="Resta un limite.",issues=[issue()])
    monkeypatch.setattr("app.essay.generation.request",request)
    client.post("/api/essays/P1/revision",json=payload(client))
    await DurableWorker(store,handler=dispatch).run_once()
    final=store.get_session("P1")
    assert calls==["revision","review","revision","review"]
    assert final.revision_progress["status"]=="completed"
    assert final.revision_progress["pass_number"]==2
    assert final.revision_progress["remaining_issues"]==1
    assert len(final.review["issues"])==1
    assert final.book_chapters[0]["unresolved"]

@pytest.mark.asyncio
async def test_no_changes_does_not_buy_an_unnecessary_second_pass(client,store,monkeypatch):
    ready(store);calls=[]
    async def request(session,phase,prompt,schema=None,**kwargs):
        data=parsed_prompt(prompt);calls.append(phase)
        if phase=="revision":
            return ChapterPayload(content=data["chapter"]["content"],summary="Già adeguato.",unresolved=["Servono nuove fonti."])
        return EssayReview(summary="Serve una fonte.",issues=[issue()])
    monkeypatch.setattr("app.essay.generation.request",request)
    client.post("/api/essays/P1/revision",json=payload(client))
    await DurableWorker(store,handler=dispatch).run_once()
    assert calls==["revision","review"]
    assert store.get_session("P1").revision_progress["remaining_issues"]==1
    assert store.get_session("P1").book_chapters[0]["unresolved"]==["Servono nuove fonti."]

@pytest.mark.asyncio
async def test_resume_after_failure_skips_saved_chapters_and_survives_store_restart(client,store,monkeypatch):
    ready(store,issues=[issue("")]);calls=[];fail=[True]
    async def request(session,phase,prompt,schema=None,**kwargs):
        data=parsed_prompt(prompt)
        if phase=="revision":
            sid=data["chapter"]["section_id"];calls.append(sid)
            if sid=="C2" and fail[0]:
                fail[0]=False;raise RuntimeError("Interruzione di rete")
            return ChapterPayload(content=data["chapter"]["content"].replace("originale","precisata"),summary="Precisata.",unresolved=[])
        return EssayReview(summary="Verifica completata.",issues=[])
    monkeypatch.setattr("app.essay.generation.request",request)
    client.post("/api/essays/P1/revision",json=payload(client))
    await DurableWorker(store,handler=dispatch).run_once()
    assert client.get("/api/essays/P1").json()["can_resume_revision"]
    assert store.get_session("P1").revision_progress["status"]=="failed"
    restarted=EssayStore(store.db_path)
    with TestClient(create_app(restarted,run_worker=False)) as resumed:
        assert resumed.post("/api/essays/P1/revision",json=payload(resumed,True)).status_code==200
        await DurableWorker(restarted,handler=dispatch).run_once()
    assert calls==["C1","C2","C2"]
    assert restarted.get_session("P1").revision_progress["status"]=="completed"
    assert restarted.get_session("P1").revision_progress["updated_sections"]==2

@pytest.mark.asyncio
async def test_failed_verification_resumes_saved_review_groups(client,store,monkeypatch):
    s=ready(store,issues=[issue("")])
    for chapter in s.book_chapters:
        chapter["content"]="Una ragione da qualificare. "*5000
    store.save_session(s)
    calls=[];fail=[True]
    async def request(session,phase,prompt,schema=None,**kwargs):
        data=parsed_prompt(prompt)
        if phase=="revision":
            return ChapterPayload(content=data["chapter"]["content"],summary="Conservato.",unresolved=[])
        sid=data["chapters"][0]["section_id"];calls.append(sid)
        if sid=="C2" and fail[0]:
            fail[0]=False;raise RuntimeError("Verifica interrotta")
        return EssayReview(summary="Gruppo verificato.",issues=[])
    monkeypatch.setattr("app.essay.generation.request",request)
    client.post("/api/essays/P1/revision",json=payload(client))
    await DurableWorker(store,handler=dispatch).run_once()
    assert len(store.get_session("P1").revision_request["review_groups"])==1
    client.post("/api/essays/P1/revision",json=payload(client,True))
    await DurableWorker(store,handler=dispatch).run_once()
    assert calls==["C1","C2","C2"]
    assert store.get_session("P1").revision_progress["status"]=="completed"

@pytest.mark.asyncio
@pytest.mark.parametrize("bad_content",["Una citazione inventata [@MISSING]. "*25,"Un testo troppo corto. "*5])
async def test_rejects_invalid_references_and_radical_truncation_without_overwriting(client,store,monkeypatch,bad_content):
    original=ready(store);calls=[]
    async def request(session,phase,prompt,schema=None,**kwargs):
        calls.append(phase)
        return ChapterPayload(content=bad_content,summary="Errato.",unresolved=[])
    monkeypatch.setattr("app.essay.generation.request",request)
    client.post("/api/essays/P1/revision",json=payload(client))
    await DurableWorker(store,handler=dispatch).run_once()
    final=store.get_session("P1")
    assert calls==["revision","revision"]
    assert final.book_chapters==original.book_chapters
    assert final.revision_progress["status"]=="failed"

@pytest.mark.asyncio
async def test_cancel_after_atomic_chapter_save_resumes_without_repurchasing(client,store,monkeypatch):
    ready(store,issues=[issue("")]);calls=fake_pipeline(monkeypatch)
    save=store.save_session;cancel=[True]
    def interrupted(session):
        result=save(session)
        checkpoint=session.revision_request
        if cancel[0] and checkpoint and checkpoint.get("completed_ids")==["C1"]:
            cancel[0]=False;raise asyncio.CancelledError()
        return result
    monkeypatch.setattr(store,"save_session",interrupted)
    client.post("/api/essays/P1/revision",json=payload(client))
    await DurableWorker(store,handler=dispatch).run_once()
    assert store.list_jobs("P1")[0]["status"]=="pending"
    await DurableWorker(store,handler=dispatch).run_once()
    assert [data["chapter"]["section_id"] for phase,data in calls if phase=="revision"]==["C1","C2"]
    assert store.get_session("P1").revision_progress["status"]=="completed"

@pytest.mark.asyncio
async def test_manual_changes_invalidate_recovery_and_finished_receipt_is_not_reapplied(client,store,monkeypatch):
    ready(store);calls=fake_pipeline(monkeypatch)
    client.post("/api/essays/P1/revision",json=payload(client))
    await DurableWorker(store,handler=dispatch).run_once()
    count=len(calls)
    # A worker may recover after the final commit but before acknowledging the durable job.
    store.enqueue("P1","revision")
    await DurableWorker(store,handler=dispatch).run_once()
    assert len(calls)==count
    assert store.get_session("P1").revision_progress["updated_sections"]==1
    assert not client.get("/api/essays/P1").json()["can_resume_revision"]
    s=store.get_session("P1")
    response=client.put("/api/essays/P1/chapters/0",json={"content":s.book_chapters[0]["content"]+" Una modifica manuale.",
        "expected_hash":content_hash(s.book_chapters[0]["content"])})
    assert response.status_code==200
    assert response.json()["revision_progress"] is None
    assert store.get_session("P1").revision_request is None
    assert client.post("/api/essays/P1/revision",json=payload(client,True)).status_code==422


@pytest.mark.asyncio
async def test_cost_budget_stops_before_another_chapter_and_keeps_recovery_receipt(client,store,monkeypatch):
    from app.essay import generation
    ready(store,issues=[issue("")])
    calls=fake_pipeline(monkeypatch)
    check=generation.assert_budget
    def budget(store_,session):
        if len(calls)>=1:
            raise ValueError("Il limite di spesa impostato è stato raggiunto.")
        return check(store_,session)
    monkeypatch.setattr(generation,"assert_budget",budget)
    client.post("/api/essays/P1/revision",json=payload(client))
    await DurableWorker(store,handler=dispatch).run_once()
    s=store.get_session("P1")
    assert s.revision_progress["status"]=="failed"
    assert s.revision_request["completed_ids"]==["C1"]
    assert "precisata" in s.book_chapters[0]["content"]
    assert "originale" in s.book_chapters[1]["content"]
    assert len(calls)==1
    assert client.get("/api/essays/P1").json()["can_resume_revision"]

@pytest.mark.asyncio
async def test_registered_references_and_bibliography_survive_ai_corrections(client,store,monkeypatch):
    from test_essay_product import add_evidence
    from app.essay.citations import rendered_manuscript
    s=ready(store)
    add_evidence(s)
    s.book_chapters[0]["content"]+=" Una definizione documentata [@E1]."
    store.save_session(s)
    calls=fake_pipeline(monkeypatch)
    client.post("/api/essays/P1/revision",json=payload(client))
    await DurableWorker(store,handler=dispatch).run_once()
    s=store.get_session("P1")
    assert "[@E1]" in s.book_chapters[0]["content"]
    assert calls[0][1]["evidence"][0]["evidence_id"]=="E1"
    _,bibliography=rendered_manuscript(s)
    assert len(bibliography)==1
    assert s.review["checks"]["issues"]==[]


@pytest.mark.asyncio
async def test_increasing_budget_preserves_correction_checkpoint_and_approval(client,store,monkeypatch):
    from app.essay import generation
    ready(store,issues=[issue("")])
    calls=fake_pipeline(monkeypatch)
    def budget(store_,session):
        if len(calls)>=1 and (session.form_data.budget_eur or 0)<2:
            raise ValueError("Limite raggiunto.")
    monkeypatch.setattr(generation,"assert_budget",budget)
    client.post("/api/essays/P1/revision",json=payload(client))
    await DurableWorker(store,handler=dispatch).run_once()
    p=client.get("/api/essays/P1").json()
    response=client.put("/api/essays/P1/brief",json={"expected_version":p["current_version"],"brief":p["form_data"]|{"budget_eur":2}})
    assert response.status_code==200,response.text
    assert response.json()["can_resume_revision"] and response.json()["validated"]
    assert store.get_session("P1").revision_request["completed_ids"]==["C1"]
    client.post("/api/essays/P1/revision",json=payload(client,True))
    await DurableWorker(store,handler=dispatch).run_once()
    assert [data["chapter"]["section_id"] for phase,data in calls if phase=="revision"]==["C1","C2"]
    assert store.get_session("P1").revision_progress["status"]=="completed"


def test_author_metadata_does_not_invalidate_correction_recovery(client,store):
    s=ready(store)
    s.revision_request={"source_version":s.current_version,"hashes":{c["section_id"]:content_hash(c["content"]) for c in s.book_chapters},"stage":"writing"}
    s.revision_progress={"status":"failed","error":"Rete interrotta."}
    store.save_session(s)
    response=client.put("/api/essays/P1/publication",json={"author_name":"Ada Rossi","expected_version":1})
    assert response.status_code==200,response.text
    assert response.json()["can_resume_revision"]
    assert store.get_session("P1").revision_request["source_version"]==2
