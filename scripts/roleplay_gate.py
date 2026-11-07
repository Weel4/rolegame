#!/usr/bin/env python3
"""Fail-closed source intake and output verifier. Requires Anthropic API access."""
import argparse, hashlib, json, os, pathlib, sys, urllib.request
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".roleplay-private"

class Blocked(Exception): pass

def intake(root=ROOT):
    manifest = yaml.safe_load((root/"manifest.yaml").read_text(encoding="utf-8"))
    if manifest.get("version") != 1: raise Blocked("Unsupported manifest")
    files = manifest.get("required_files")
    if not files: raise Blocked("Manifest contains no sources")
    result, seen = [], set()
    for item in files:
        name = item["path"]
        path = root/name
        if name in seen or path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise Blocked("Missing/unsafe/duplicate file: "+name)
        seen.add(name)
        data = path.read_bytes()
        content = data.decode("utf-8")
        mode = item.get("transform", "plain")
        if mode == "reversed_characters": content = content[::-1]
        elif mode != "plain": raise Blocked("Unknown transform: "+name)
        canary = item.get("canary")
        if canary and canary not in content: raise Blocked("Canary missing: "+name)
        result.append({"path":name, "sha256":hashlib.sha256(data).hexdigest(),
                       "text":content, "lines":content.splitlines(), "canary":canary})
    if sum(len(x["text"]) for x in result) > manifest.get("max_material_chars",300000):
        raise Blocked("Materials too long: refusing silent truncation")
    return result

def verify_quote(record, source):
    first,last,quote=record.get("line_start"),record.get("line_end"),record.get("quote")
    if type(first)!=int or type(last)!=int or not 1<=first<=last<=len(source["lines"]) or last-first>24:
        raise Blocked("Invalid lines: "+source["path"])
    if not isinstance(quote,str) or len(quote.strip())<8 or quote not in "\n".join(source["lines"][first-1:last]):
        raise Blocked("Invalid excerpt: "+source["path"])

def validate(reply, sources):
    lookup={s["path"]:s for s in sources}
    scene=reply.get("scene")
    if not isinstance(scene,str) or not scene.strip(): raise Blocked("Scene missing")
    receipts=reply.get("source_receipts")
    if not isinstance(receipts,list) or len(receipts)!=len(sources): raise Blocked("Missing receipts")
    seen=set()
    for receipt in receipts:
        name=receipt.get("path")
        if name not in lookup or name in seen: raise Blocked("Unknown/duplicate receipt")
        source=lookup[name]
        if receipt.get("sha256")!=source["sha256"] or receipt.get("canary")!=source["canary"]:
            raise Blocked("SHA/canary mismatch: "+name)
        verify_quote(receipt,source)
        seen.add(name)
    claims=reply.get("fact_citations")
    if not isinstance(claims,list) or not claims: raise Blocked("Missing fact citations")
    for claim in claims:
        if not claim.get("fact") or claim.get("path") not in lookup: raise Blocked("Invalid claim")
        verify_quote(claim,lookup[claim["path"]])
    if any(s["canary"] and s["canary"] in scene for s in sources):
        raise Blocked("Canary leaked into story")
    return scene

def invoke(prompt, sources, model, history):
    key=os.environ.get("ANTHROPIC_API_KEY")
    if not key: raise Blocked("ANTHROPIC_API_KEY missing")
    material="\n\n".join("FILE "+s["path"]+" SHA256 "+s["sha256"]+"\n"+
        "\n".join(f"{n}: {line}" for n,line in enumerate(s["lines"],1)) for s in sources)
    instructions=("Write Finnish roleplay using the supplied source pack. Return ONLY JSON with "
      "scene (string), source_receipts (one per source, with path, sha256, line_start, "
      "line_end, quote, canary if specified), and fact_citations (array of objects: "
      "fact, path, line_start, line_end, quote). Every preexisting continuity fact "
      "must have a source citation. Quote real source lines. Never disclose hidden "
      "truth, receipts, or canaries in scene.")
    messages=[{"role":"user","content":"SOURCE PACK:\n"+material},
              {"role":"assistant","content":"I will use the source pack."},
              *history,{"role":"user","content":prompt}]
    payload=json.dumps({"model":model,"max_tokens":6000,"system":instructions,"messages":messages}).encode()
    req=urllib.request.Request("https://api.anthropic.com/v1/messages",data=payload,
      headers={"x-api-key":key,"anthropic-version":"2023-06-01",
               "content-type":"application/json"},method="POST")
    with urllib.request.urlopen(req,timeout=120) as response: data=json.load(response)
    text="".join(block.get("text","") for block in data.get("content",[]) if block.get("type")=="text")
    return json.loads(text)

def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest="action",required=True)
    sub.add_parser("verify-materials")
    run=sub.add_parser("run")
    run.add_argument("--prompt",required=True)
    run.add_argument("--model",default=os.environ.get("ANTHROPIC_MODEL"))
    args=parser.parse_args()
    try:
        sources=intake()
        if args.action=="verify-materials":
            print(f"PASS: {len(sources)} required files loaded and verified")
            return 0
        if not args.model: raise Blocked("Model identifier missing")
        PRIVATE.mkdir(mode=0o700,exist_ok=True)
        log={"files":[{"path":s["path"],"sha256":s["sha256"],"total_lines":len(s["lines"]),
           "headings":[line for line in s["lines"] if line.startswith("#")][:50],
           "excerpt":s["text"][:180]} for s in sources]}
        (PRIVATE/"read_log.json").write_text(json.dumps(log,ensure_ascii=False,indent=2))
        store=PRIVATE/"history.json"
        history=json.loads(store.read_text()) if store.exists() else []
        reply=invoke(args.prompt,sources,args.model,history)
        for s in sources:
            if hashlib.sha256((ROOT/s["path"]).read_bytes()).hexdigest()!=s["sha256"]:
                raise Blocked("Source changed during request")
        scene=validate(reply,sources)
        (PRIVATE/"last_audit.json").write_text(json.dumps({
          "source_receipts":reply["source_receipts"],
          "fact_citations":reply["fact_citations"]},ensure_ascii=False,indent=2))
        history += [{"role":"user","content":args.prompt},{"role":"assistant","content":scene}]
        store.write_text(json.dumps(history,ensure_ascii=False,indent=2))
        print(scene)
        return 0
    except (Blocked,OSError,ValueError,KeyError,yaml.YAMLError) as exc:
        print("GATE BLOCKED: "+str(exc),file=sys.stderr)
        return 1

if __name__=="__main__": sys.exit(main())
