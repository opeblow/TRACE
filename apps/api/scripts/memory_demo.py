"""Live Walrus Memory evidence run (PRD §9 learning-loop test, §19 acceptance).

CONTROLLED TEST SCENARIO: the operator acts as the user and enters labels and
feedback about a real, public Mainnet wallet. Chain data is real (Tatum Sui
gRPC); memory writes are real (Walrus Memory Mainnet relayer). Nothing is
fabricated, and only jobs that Walrus reports as completed are counted.

Usage (from apps/api, with Tatum and Walrus credentials in .env):
    python scripts/memory_demo.py [--wallet 0x...] [--workspace KEY]

Writes docs/evidence/walrus-memory-evidence.json and docs/evidence/LEARNING_LOOP.md.
The workspace key is printed once to the console (paste it into the Memory
Centre to view these memories) and is never written to the evidence files.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
REPO = API_DIR.parents[1]
sys.path.insert(0, str(API_DIR))
os.chdir(API_DIR)
os.environ.setdefault("TRACE_ENV", "development")
os.environ["ANALYSIS_RATE_LIMIT"] = "200"  # one operator run makes ~15 calls in under a minute

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.memory import namespace_ref, workspace_namespace  # noqa: E402

DEFAULT_WALLET = "0x7d3fe51822d20ea780d061e17bcb7204a645ceef278b562db1ddfe5b35f9cf72"
EVIDENCE_DIR = REPO / "docs" / "evidence"
TARGET_WRITES = 12


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def short(value: str) -> str:
    return f"{value[:8]}…{value[-6:]}"


def analyze(client: TestClient, wallet: str, workspace: str) -> dict:
    response = client.post("/api/v1/wallets/analyze", json={"address": wallet}, headers={"X-Trace-Workspace": workspace})
    response.raise_for_status()
    return response.json()


def plan_memories(result: dict, wallet: str) -> list[dict]:
    """Derive meaningful memories from the real findings of the first analysis."""
    findings = result["analysis"]["anomalies"]
    if not findings:
        raise SystemExit("The wallet produced no findings; choose a wallet with an established baseline and outliers.")
    counts: dict[str, list[dict]] = {}
    for finding in findings:
        if finding.get("counterparty"):
            counts.setdefault(finding["counterparty"], []).append(finding)
    ranked = sorted(counts.items(), key=lambda kv: -len(kv[1]))
    plan: list[dict] = []
    names = ["Exchange deposit (recurring transfers)", "Known counterparty: OTC desk", "Known counterparty: friend"]
    labelled = set()
    for (counterparty, related), name in zip(ranked, names):
        plan.append({"path": "/api/v1/memories", "body": {"memory_type": "counterparty_label", "wallet": wallet, "subject": counterparty, "value": name, "consent": True},
                     "why": f"Label for counterparty in {len(related)} finding(s)"})
        labelled.add(counterparty)
    for finding in findings:
        if len(plan) >= TARGET_WRITES - 1:
            break
        expected = finding.get("counterparty") in labelled
        label = "expected" if expected else "needs_review"
        reason = "Recurring transfer to my labelled counterparty" if expected else "Unfamiliar movement; check before the next transfer"
        plan.append({"path": f"/api/v1/alerts/{finding['transaction_digest']}/feedback", "body": {"wallet": wallet, "label": label, "reason": reason, "consent": True},
                     "why": f"Feedback on {finding['severity']} finding {finding['transaction_digest'][:10]}…"})
    total_out = sum(float(f["amount_sui"]) for f in findings if f.get("direction") == "out")
    summary = (f"First review: {len(findings)} unusual SUI movements in the latest 50 transactions, "
               f"about {total_out:,.0f} SUI out in total. Largest destination labelled as my exchange deposit; review the rest.")
    plan.append({"path": "/api/v1/memories", "body": {"memory_type": "investigation_summary", "wallet": wallet, "value": summary[:280], "consent": True},
                 "why": "Investigation summary from the first analysis"})
    return plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wallet", default=DEFAULT_WALLET)
    parser.add_argument("--workspace", default=None, help="Reuse a browser workspace key so the memories appear in that browser's Memory Centre")
    args = parser.parse_args()
    wallet = args.wallet.lower()
    workspace = args.workspace or ("demo_" + secrets.token_urlsafe(24))
    ns_ref = namespace_ref(workspace_namespace(workspace))
    print(f"Controlled test scenario · wallet {short(wallet)} · workspace ref {ns_ref}")
    print(f"Workspace key (paste into Memory Centre to view; not saved to evidence): {workspace}\n")

    # Session 1: stateless baseline
    session1 = TestClient(app)
    first = analyze(session1, wallet, workspace)
    print(f"Session 1: memory={first['memory']['status']} findings={first['analysis']['anomaly_count']}")
    plan = plan_memories(first, wallet)

    writes = []
    for item in plan:
        started = time.time()
        response = session1.post(item["path"], json=item["body"], headers={"X-Trace-Workspace": workspace, "Idempotency-Key": "demo-" + secrets.token_hex(8)})
        record = {"memory_type": item["body"].get("memory_type", "alert_feedback"), "purpose": item["why"], "submitted_at": now(), "http_status": response.status_code}
        if response.status_code == 202:
            record["job_id"] = response.json()["job_id"]
            record["status"] = "pending"
        else:
            record["status"] = "rejected"
            record["error"] = response.json().get("detail")
        record["_started"] = started
        writes.append(record)
        print(f"  submitted {record['memory_type']:<22} -> {record['status']}")

    deadline = time.time() + 300
    while time.time() < deadline and any(w["status"] == "pending" for w in writes):
        time.sleep(4)
        for w in writes:
            if w["status"] != "pending":
                continue
            r = session1.get(f"/api/v1/memories/jobs/{w['job_id']}", headers={"X-Trace-Workspace": workspace})
            if r.status_code == 200 and r.json()["status"] != "pending":
                body = r.json()
                w.update(status=body["status"], blob_id=body.get("blob_id"), completed_at=now(), seconds_to_complete=round(time.time() - w["_started"], 1))
                print(f"  job {w['job_id'][:8]} {body['status']:<9} blob {body.get('blob_id') or '-'}")
    for w in writes:
        w.pop("_started", None)
    succeeded = [w for w in writes if w["status"] == "succeeded"]
    print(f"\nCompleted Mainnet memory writes: {len(succeeded)} / {len(writes)} attempted")

    # Session 2: brand-new API client; the only shared state is Walrus Memory itself.
    session2 = TestClient(app)
    second = analyze(session2, wallet, workspace)
    memory = second["memory"]
    print(f"Session 2: memory={memory['status']} recalled={memory['recalled_count']} changed_result={memory['changed_result']} effects={len(memory['effects'])}")

    # Isolation: a different workspace must recall nothing.
    other = analyze(TestClient(app), wallet, "iso_" + secrets.token_urlsafe(24))
    print(f"Isolation check (other workspace): recalled={other['memory']['recalled_count']}")

    before = {f["transaction_digest"]: f["severity"] for f in memory["stateless"]["anomalies"]}
    after = {f["transaction_digest"]: f for f in second["analysis"]["anomalies"]}
    comparison = [{
        "transaction_digest": d,
        "amount_sui": after[d]["amount_sui"],
        "counterparty": after[d].get("counterparty"),
        "severity_without_memory": before[d],
        "severity_with_memory": after[d]["severity"],
        "state_with_memory": after[d].get("state"),
        "memory_ids": [c["memory_id"] for c in after[d].get("memory_context", [])],
        "explanation": [c["summary"] for c in after[d].get("memory_context", [])],
    } for d in before if d in after]

    evidence = {
        "scenario": "CONTROLLED TEST SCENARIO: operator-entered labels and feedback about a real public Mainnet wallet. Chain data and memory writes are real.",
        "generated_at": now(),
        "network": second["snapshot"]["network"],
        "checkpoint_height": second["snapshot"]["checkpoint_height"],
        "wallet": wallet,
        "workspace_namespace_ref": ns_ref,
        "walrus_relayer": "https://relayer.memory.walrus.xyz",
        "writes_attempted": len(writes),
        "writes_completed": len(succeeded),
        "writes": writes,
        "session_1": {"memory_status": first["memory"]["status"], "findings": first["analysis"]["anomaly_count"]},
        "session_2": {"memory_status": memory["status"], "recalled": memory["recalled_count"], "changed_result": memory["changed_result"], "effects": memory["effects"]},
        "isolation_other_workspace_recalled": other["memory"]["recalled_count"],
        "before_after": comparison,
        "acceptance": {
            "at_least_10_completed_mainnet_writes": len(succeeded) >= 10,
            "later_session_recalled_memory": memory["recalled_count"] > 0,
            "memory_changed_user_visible_result": memory["changed_result"],
            "stateless_output_shown_for_comparison": bool(memory["stateless"]["anomalies"]),
            "other_workspace_isolated": other["memory"]["recalled_count"] == 0,
        },
    }
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "walrus-memory-evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    rows = "\n".join(
        f"| [`{c['transaction_digest'][:10]}…`](https://suiscan.xyz/mainnet/tx/{c['transaction_digest']}) | {c['amount_sui']} | "
        f"{short(c['counterparty']) if c['counterparty'] else '—'} | {c['severity_without_memory']} | **{c['severity_with_memory']}** | {c['state_with_memory'] or 'open'} |"
        for c in comparison)
    write_rows = "\n".join(
        f"| {w['memory_type']} | {w['purpose']} | {w['status']} | {w.get('seconds_to_complete', '—')} | "
        + (f"[`{w['blob_id'][:12]}…`](https://walruscan.com/mainnet/blob/{w['blob_id']})" if w.get("blob_id") else "—") + " |"
        for w in writes)
    checks = "\n".join(f"- [{'x' if ok else ' '}] {name.replace('_', ' ')}" for name, ok in evidence["acceptance"].items())
    md = f"""# Learning-loop evidence (Walrus Memory, Mainnet)

> **Controlled test scenario.** The operator acted as the user and entered labels and feedback about a real, public Mainnet wallet.
> Chain data (Tatum Sui gRPC) and memory writes (Walrus Memory relayer) are real. Only jobs Walrus reported as completed are counted.
> Regenerate with `python apps/api/scripts/memory_demo.py`.

Generated {evidence['generated_at']} · Sui {evidence['network']} checkpoint {evidence['checkpoint_height']} · wallet [`{short(wallet)}`](https://suiscan.xyz/mainnet/account/{wallet}) · workspace ref `{ns_ref}`

## PRD acceptance checks

{checks}

## Memory writes ({len(succeeded)} completed of {len(writes)} attempted)

| Type | Purpose | Status | Seconds to complete | Walrus blob |
|---|---|---|---|---|
{write_rows}

## Same wallet, new session: without memory vs. with recalled memory

Session 1 (no memories): **{first['memory']['status']}**, {first['analysis']['anomaly_count']} findings.
Session 2 (fresh API client): memory **{memory['status']}**, {memory['recalled_count']} recalled, result changed: **{memory['changed_result']}**.
A different workspace analysing the same wallet recalled **{other['memory']['recalled_count']}** memories.

| Transaction | SUI | Counterparty | Without memory | With memory | Review state |
|---|---|---|---|---|---|
{rows}

Every changed row cites the Walrus blob IDs that caused it (see `walrus-memory-evidence.json`). Labels and feedback are user assertions:
TRACE lowers priority but never hides a finding or treats memory as proof of safety.
"""
    (EVIDENCE_DIR / "LEARNING_LOOP.md").write_text(md, encoding="utf-8")
    print(f"\nEvidence written to {EVIDENCE_DIR.relative_to(REPO)}")
    print(json.dumps(evidence["acceptance"], indent=2))
    return 0 if all(evidence["acceptance"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
