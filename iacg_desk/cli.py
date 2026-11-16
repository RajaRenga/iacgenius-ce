"""iacg desk CLI: python -m iacg_desk <cmd>."""
from __future__ import annotations

import argparse
import json
import sys

from . import (board, build_sheet, capability, deliver, gates, knowledge, ledger, onboard, pickup,
               repair, resolver, schema_okf, validate, versions, workspace)
from .store import Store


def _pair(text: str) -> tuple[str, str]:
    key, sep, value = text.partition("=")
    if not sep or not key:
        raise ValueError(f"expected key=value, got {text!r}")
    return key, value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="iacg_desk", description="IaC Genius CE desk: deterministic mission state, "
                                     "evidence, gates and delivery. Never applies infrastructure.")
    parser.add_argument("--home", help="data dir (default: env IACG_HOME or ./iacg-data)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("create", help="create a mission and its decision ledger")
    p.add_argument("title")
    p.add_argument("--provider", default="aws", choices=["aws", "azure", "gcp"])
    p.add_argument("--iac-tool", default="terraform", choices=["terraform", "opentofu"])
    p.add_argument("--build-tier", default="minimal", choices=["minimal", "standard", "enterprise"])
    p.add_argument("--tree", help="mission tree (generated Terraform lives here)")
    p.add_argument("--requirement", help="the user's plain-language request (STATED)")
    p.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="STATED ledger row")
    p.add_argument("--default", action="append", default=[], metavar="KEY=VALUE", help="SOURCE ledger row")
    p.add_argument("--source", help="resolving source for --default rows (e.g. mission_profile:baseline)")
    p.add_argument("--must-ask", action="append", default=[], metavar="KEY", help="open a MUST_ASK question")

    p = sub.add_parser("answer", help="answer a MUST_ASK question (becomes STATED)")
    p.add_argument("mission_id"); p.add_argument("key"); p.add_argument("value")

    p = sub.add_parser("resolve", help="model-free resolver: settle the ledger from the catalogue (smart defaults)")
    p.add_argument("mission_id")
    p.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="STATED key the user said")
    p.add_argument("--no-ask", action="store_true", help="declined path: costly keys fall to disclosed defaults")

    p = sub.add_parser("skip", help="fold MUST_ASK questions to their disclosed defaults (answer some via --answer)")
    p.add_argument("mission_id")
    p.add_argument("--answer", action="append", default=[], metavar="KEY=VALUE", help="answer this key; rest skip")

    p = sub.add_parser("sheet", help="assemble the review-only build sheet preview (scope finalize)")
    p.add_argument("mission_id")

    p = sub.add_parser("confirm", help="freeze the build sheet (one hash); generation runs only on this revision")
    p.add_argument("mission_id"); p.add_argument("--by", required=True, help="the human's name")

    p = sub.add_parser("pin", help="pin terraform/provider versions into the ledger")
    p.add_argument("mission_id")
    p.add_argument("--terraform")
    p.add_argument("--provider", action="append", default=[], metavar="NAME=VERSION")

    p = sub.add_parser("ledger", help="render the ledger prompt block (or --json for the PR-body packet)")
    p.add_argument("mission_id"); p.add_argument("--json", action="store_true")

    p = sub.add_parser("brief", help="high-level design summary + compiled expert generation context")
    p.add_argument("mission_id"); p.add_argument("--json", action="store_true")

    p = sub.add_parser("rules-check", help="run the deterministic expert-rule detectors over the mission tree")
    p.add_argument("mission_id"); p.add_argument("--tree")

    p = sub.add_parser("status", help="mission status, evidence and gate")
    p.add_argument("mission_id")

    p = sub.add_parser("pickup", help="one complete packet to resume/finish a mission (state, tree-exists, ledger, findings, next step)")
    p.add_argument("mission_id")

    p = sub.add_parser("validate", help="run the toolchain over the mission tree (fmt/init/validate/tflint/checkov/secrets)")
    p.add_argument("mission_id"); p.add_argument("--tree")

    p = sub.add_parser("schema", help="extract or read the provider schema OKF (once per provider@version)")
    p.add_argument("provider"); p.add_argument("version")
    p.add_argument("--resource", action="append", default=[], help="resource type to excerpt")

    p = sub.add_parser("repair", help="record one bounded repair attempt")
    p.add_argument("mission_id"); p.add_argument("--note", default="")

    p = sub.add_parser("approve", help="record a named human acceptance (delivery, or one soft finding)")
    p.add_argument("mission_id"); p.add_argument("--by", required=True)
    p.add_argument("--finding", help="finding id to accept; omit for delivery approval")
    p.add_argument("--reason", default="accepted by human")

    p = sub.add_parser("deliver", help="GitHub PR whose body is the ledger, then read-back")
    p.add_argument("mission_id"); p.add_argument("--repo", required=True, help="owner/name")
    p.add_argument("--base", default="main"); p.add_argument("--tree")

    p = sub.add_parser("package", help="sync the work/ provenance folder and zip the whole mission folder for download")
    p.add_argument("mission_id"); p.add_argument("--out", help="zip path (default: <workspace>/<mission_id>.zip)")

    p = sub.add_parser("remember", help="store a durable profile fact reused across missions (e.g. region=us-east-1)")
    p.add_argument("pair", metavar="KEY=VALUE")
    p.add_argument("--provider", default="aws", choices=["aws", "azure", "gcp"]); p.add_argument("--by", required=True)

    p = sub.add_parser("knowledge", help="list the durable profile facts IaCGenius remembers")
    p.add_argument("--provider", choices=["aws", "azure", "gcp"])

    p = sub.add_parser("forget", help="drop a remembered profile fact")
    p.add_argument("key"); p.add_argument("--provider", default="aws", choices=["aws", "azure", "gcp"])

    p = sub.add_parser("onboard", help="warm the provider cache once, confirm, reuse")
    p.add_argument("--confirm", action="store_true"); p.add_argument("--by", default="operator")

    p = sub.add_parser("board", help="write and print the mission board snapshot")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("serve", help="Unix-socket JSON API for the plugin")
    p.add_argument("--socket", required=True)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    store = Store(args.home)
    try:
        if args.cmd == "create":
            mid = store.new_mission(args.title, args.provider, args.iac_tool, args.build_tier,
                                    tree=args.tree, attempts_allowed=repair.budget())
            if args.requirement:
                ledger.add(store, mid, "user_requirements", args.requirement)
            for text in args.set:
                key, value = _pair(text)
                ledger.add(store, mid, key, value)
            for text in args.default:
                key, value = _pair(text)
                ledger.add(store, mid, key, value, origin="SOURCE", source=args.source)
            for key in args.must_ask:
                ledger.add(store, mid, key, origin="MUST_ASK", rationale="costly or irreversible; no source could supply it")
            versions.pin(store, mid)
            ready, keys = ledger.generation_ready(store, mid)
            print(json.dumps({"mission_id": mid, "generation_ready": ready, "must_ask": keys}, indent=2))
        elif args.cmd == "answer":
            ledger.answer(store, args.mission_id, args.key, args.value)
            ready, keys = ledger.generation_ready(store, args.mission_id)
            print(json.dumps({"answered": args.key, "generation_ready": ready, "must_ask": keys}))
        elif args.cmd == "resolve":
            stated = dict(_pair(t) for t in args.set)
            print(json.dumps(resolver.resolve(store, args.mission_id, stated=stated, ask=not args.no_ask), indent=2))
        elif args.cmd == "skip":
            answers = dict(_pair(t) for t in args.answer)
            print(json.dumps(resolver.apply_answers(store, args.mission_id, answers=answers), indent=2))
        elif args.cmd == "sheet":
            print(json.dumps(build_sheet.assemble(store, args.mission_id), indent=2))
        elif args.cmd == "confirm":
            print(json.dumps(build_sheet.confirm(store, args.mission_id, confirmed_by=args.by), indent=2))
        elif args.cmd == "pin":
            versions.pin(store, args.mission_id, terraform=args.terraform,
                         providers=dict(_pair(t) for t in args.provider) or None)
            print(json.dumps(versions.read(store, args.mission_id)))
        elif args.cmd == "ledger":
            print(ledger.sorted_json(store, args.mission_id) if args.json else ledger.prompt_block(store, args.mission_id))
        elif args.cmd == "brief":
            capability.write_bundle(store, args.mission_id)
            if args.json:
                print(json.dumps({"summary": capability.summary(store, args.mission_id),
                                  "context": capability.context_block(store, args.mission_id)}, indent=2))
            else:
                print(capability.summary(store, args.mission_id))
                print("\n" + "=" * 72 + "\n")
                print(capability.context_block(store, args.mission_id))
        elif args.cmd == "rules-check":
            mission = store.mission(args.mission_id)
            if mission is None:
                raise KeyError(f"unknown mission {args.mission_id}")
            tree = args.tree or mission.get("tree")
            if not tree:
                raise ValueError("no mission tree; pass --tree")
            findings = capability.check(tree, mission["provider"], mission["build_tier"])
            print(json.dumps({"violations": findings, "count": len(findings)}, indent=2))
        elif args.cmd == "status":
            mission = store.mission(args.mission_id)
            if mission is None:
                raise KeyError(f"unknown mission {args.mission_id}")
            print(json.dumps({"mission": mission, "versions": versions.read(store, args.mission_id),
                              "must_ask": [r["key"] for r in ledger.open_questions(store, args.mission_id)],
                              "evidence": [{k: r[k] for k in ("check_name", "tool", "version", "status", "not_run_reason")}
                                           for r in store.latest_evidence(args.mission_id).values()],
                              "gate": gates.delivery_gate(store, args.mission_id),
                              "repairs": store.repairs(args.mission_id)}, indent=2, default=str))
        elif args.cmd == "pickup":
            print(json.dumps(pickup.pickup(store, args.mission_id), indent=2, default=str))
        elif args.cmd == "validate":
            packets = validate.run(store, args.mission_id, tree=args.tree)
            print(json.dumps([{k: p[k] for k in ("check", "status", "tool") if k in p} |
                              ({"not_run_reason": p["not_run_reason"]} if p.get("not_run_reason") else {})
                              for p in packets], indent=2))
        elif args.cmd == "schema":
            result = schema_okf.extract(store, args.provider, args.version)
            if args.resource and result["status"] in ("EXTRACTED", "CACHE_HIT"):
                result["excerpts"] = schema_okf.excerpts(schema_okf.load(store, args.provider, args.version),
                                                         args.provider, args.resource)
            print(json.dumps(result, indent=2))
        elif args.cmd == "repair":
            print(json.dumps(repair.record_attempt(store, args.mission_id, args.note), indent=2))
        elif args.cmd == "approve":
            store.accept(args.mission_id, args.finding or gates.DELIVERY_SCOPE, args.by, args.reason)
            if not args.finding and gates.delivery_gate(store, args.mission_id)["allowed"]:
                store.set_state(args.mission_id, "approved", None)
            print(json.dumps(gates.delivery_gate(store, args.mission_id), indent=2))
        elif args.cmd == "deliver":
            print(json.dumps(deliver.deliver(store, args.mission_id, args.repo, args.base, tree=args.tree), indent=2))
        elif args.cmd == "package":
            print(json.dumps(workspace.package(store, args.mission_id, out=args.out), indent=2))
        elif args.cmd == "remember":
            key, value = _pair(args.pair)
            print(json.dumps(knowledge.remember(store, args.provider, key, value, args.by), indent=2))
        elif args.cmd == "knowledge":
            print(json.dumps(knowledge.facts(store, args.provider), indent=2))
        elif args.cmd == "forget":
            print(json.dumps(knowledge.forget(store, args.provider, args.key), indent=2))
        elif args.cmd == "onboard":
            print(json.dumps(onboard.onboard(store, confirmed_by=args.by if args.confirm else None), indent=2))
        elif args.cmd == "board":
            snap = board.write(store)
            print(json.dumps(snap, indent=2) if args.json else board.summary(snap))
        elif args.cmd == "serve":
            from . import server
            server.serve(args.socket)
    except (ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0