"""Opt-in live smoke on a throwaway small local project. Calls the configured Gemini API."""
import argparse,json,time
from pathlib import Path
import httpx
parser=argparse.ArgumentParser()
parser.add_argument("--project",required=True)
parser.add_argument("--base-url",default="http://127.0.0.1:8001/api")
parser.add_argument("--output",default="backend/data/saggistica/qa")
args=parser.parse_args()
api=httpx.Client(base_url=args.base_url+"/",timeout=60)
path="essays/"+args.project
def get():
    response=api.get(path);response.raise_for_status();return response.json()
def send(endpoint,value=None):
    response=api.post(path+"/"+endpoint,json=value or {});response.raise_for_status();return response.json()
def wait(field):
    deadline=time.monotonic()+480
    while time.monotonic()<deadline:
        project=get()
        progress=project.get(field) or {}
        if not project["active"]:
            if progress.get("status")!="completed":
                raise RuntimeError(json.dumps(progress,ensure_ascii=False))
            print(field+": completed",flush=True)
            return project
        time.sleep(2)
    raise TimeoutError(field)
project=get()
if project["active"]:
    project=wait("memory_progress")
if project["form_data"]["target_words"]>1500:
    raise ValueError("Use a small test project, no more than 1500 words.")
if not project["plan"]:
    send("answers",{"answers":{q["id"]:"L'obiettivo è un confronto trasparente. Il saggio propone criteri normativi e dichiara i limiti delle evidenze, senza presentare risultati empirici." for q in project["generated_questions"]}})
    send("jobs/draft")
    project=wait("draft_progress")
    assert sum(s["word_target"] for s in project["plan"]["sections"])==project["form_data"]["target_words"]
    print("Plan: "+str(len(project["plan"]["sections"]))+" sections",flush=True)
if not project["validated"]:
    project=send("approve",{"expected_version":project["current_version"]})
if not project["writing_progress"] or project["writing_progress"]["status"]!="completed":
    send("jobs/book")
    project=wait("writing_progress")
assert len(project["book_chapters"])==len(project["plan"]["sections"])
assert not project["reference_checks"]["issues"]
send("jobs/review")
project=wait("review_progress")
send("jobs/cover")
project=wait("cover_progress")
out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
for format in ("pdf","epub","docx"):
    response=api.get(path+"/export/"+format);response.raise_for_status()
    (out/("biblioteche."+format)).write_bytes(response.content)
    print("Export "+format+": "+str(len(response.content))+" bytes",flush=True)
(out/"live-result.json").write_text(json.dumps({
 "id":args.project,"chapters":len(project["book_chapters"]),"words":project["words"],
 "sources":len(project["sources"]),"citations":project["reference_checks"]["citations"],
 "evidence":project["reference_checks"]["evidence"],"review_issues":len(project["review"]["issues"]),
 "usage":project["usage"]},ensure_ascii=False,indent=2),encoding="utf-8")
print("Verified "+str(project["words"])+" words, "+str(project["reference_checks"]["citations"])+" citations.",flush=True)
