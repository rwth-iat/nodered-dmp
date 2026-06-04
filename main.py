"""
nodered-dmp CLI

Subcommands:
  sync-aas    Read an AIMC submodel from an AAS server and reconcile with the store.
  build-flow  Build a Node-RED flow JSON from the store; optionally deploy to Node-RED.
  sync-flow   Parse a Node-RED flow (file or live server) and reconcile with the store.
  write-aas   Write ETLPaths from the store back to the AAS server.
"""

import argparse
import json
import sys
from pathlib import Path

DEFAULT_STORE = "tmp/etl_paths.json"


def cmd_sync_aas(args: argparse.Namespace) -> None:
    from nodered_dmp.aas import sync_aas
    from nodered_dmp.model import ETLPathStore

    store = ETLPathStore(args.store)
    result = sync_aas(args.aimc_url, args.server, store)

    print("sync-aas complete")
    print(f"  created : {len(result.created)}")
    print(f"  updated : {len(result.updated)}")
    print(f"  deleted : {len(result.deleted)}")
    for p in result.created:
        print(f"    + {p.extract.protocol} {p.extract.href}")
    for _, after in result.updated:
        print(f"    ~ {after.extract.protocol} {after.extract.href}")
    for p in result.deleted:
        print(f"    - {p.extract.protocol} {p.extract.href}")


def cmd_build_flow(args: argparse.Namespace) -> None:
    from nodered_dmp.flow_builder import build_and_store_flow
    from nodered_dmp.model import ETLPathStore

    store = ETLPathStore(args.store)
    etl_paths = store.load_all()

    if not etl_paths:
        print("No ETLPaths in store. Run sync-aas or sync-flow first.", file=sys.stderr)
        sys.exit(1)

    # Capture old anchors and fetch existing flow before building overwrites nodered anchors
    old_anchors: dict[str, str] = {}
    old_flow_nodes: list[dict] | None = None
    if args.preserve_visual and args.nodered_server:
        from nodered_dmp.nodered import FlowNotFoundError, get_flow_nodes

        old_anchors = {
            p.etl_path_id: p.nodered.endpoint_node_id
            for p in etl_paths if p.nodered
        }
        flow_label = args.label or next(
            (p.aas.aimc_submodel_id for p in etl_paths if p.aas), "Flow 1"
        )
        try:
            old_flow_nodes = get_flow_nodes(args.nodered_server, flow_label, token=args.token)
        except FlowNotFoundError:
            pass  # First deploy — nothing to preserve

    flow = build_and_store_flow(etl_paths, store, label=args.label or None)
    flow_nodes = json.loads(flow.generate_json())

    if old_flow_nodes and old_anchors:
        from nodered_dmp.nodered import apply_visual_overrides
        flow_nodes = apply_visual_overrides(old_flow_nodes, flow_nodes, old_anchors, etl_paths)
        print("Visual properties preserved from existing flow.")

    # Always write to file (default: flow.json)
    output = Path(args.output)
    output.write_text(json.dumps(flow_nodes, indent=2))
    print(f"Flow written to {output}  ({len(etl_paths)} path(s))")

    # Optionally deploy to (or preview against) a live Node-RED instance
    if args.nodered_server:
        from nodered_dmp.nodered import deploy_flow, preview_deploy

        tab = next(n for n in flow_nodes if n.get("type") == "tab")
        flow_name = tab["label"]
        preview = preview_deploy(args.nodered_server, flow_nodes, flow_name, token=args.token)

        if preview.action == "replace":
            print(f"  would replace : '{flow_name}'  "
                  f"({preview.removed_node_count} old nodes removed, "
                  f"{preview.new_node_count} new nodes added)")
        else:
            print(f"  would add     : '{flow_name}'  "
                  f"({preview.new_node_count} nodes)")
        print(f"  untouched     : {preview.other_tab_count} other tab(s), "
              f"{preview.other_node_count} other node(s)")

        if args.dry_run:
            print("Dry run — nothing deployed.")
        else:
            deploy_flow(args.nodered_server, flow_nodes, flow_name, token=args.token)
            print(f"Deployed '{flow_name}' to {args.nodered_server}")


def cmd_sync_flow(args: argparse.Namespace) -> None:
    from nodered_dmp.model import ETLPathStore
    from nodered_dmp.parse import sync_flow

    if args.nodered_server:
        from nodered_dmp.nodered import get_flow_nodes
        if not args.flow_name:
            print("--flow-name is required when using --nodered-server.", file=sys.stderr)
            sys.exit(1)
        nodes = get_flow_nodes(args.nodered_server, args.flow_name, token=args.token)
    elif args.flow:
        flow_file = Path(args.flow)
        if not flow_file.exists():
            print(f"Flow file not found: {flow_file}", file=sys.stderr)
            sys.exit(1)
        nodes = json.loads(flow_file.read_text())
    else:
        print("Provide either --flow FILE or --nodered-server URL --flow-name NAME.", file=sys.stderr)
        sys.exit(1)

    store = ETLPathStore(args.store)
    result = sync_flow(nodes, store)

    print("sync-flow complete")
    print(f"  created : {len(result.created)}")
    print(f"  updated : {len(result.updated)}")
    print(f"  deleted : {len(result.deleted)}")
    for p in result.created:
        print(f"    + {p.extract.protocol} {p.extract.href}")
    for _, after in result.updated:
        print(f"    ~ {after.extract.protocol} {after.extract.href}")
    for p in result.deleted:
        print(f"    - {p.extract.protocol} {p.extract.href}")


def cmd_write_aas(args: argparse.Namespace) -> None:
    from nodered_dmp.aas import write_to_aas
    from nodered_dmp.model import ETLPathStore

    store = ETLPathStore(args.store)
    etl_paths = store.load_all()

    paths_with_aas = [p for p in etl_paths if p.aas is not None]
    if not paths_with_aas:
        print("No ETLPaths with AAS anchor in store — nothing to write.", file=sys.stderr)
        sys.exit(1)

    write_to_aas(etl_paths, args.server)
    print(f"write-aas complete  ({len(paths_with_aas)} path(s) written)")
    for p in paths_with_aas:
        print(f"  {p.extract.protocol} {p.extract.href}  →  {p.aas.aimc_idshort_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nodered-dmp",
        description="Bidirectional AAS ↔ Node-RED integration tool.",
    )
    parser.add_argument(
        "--store",
        default=DEFAULT_STORE,
        metavar="PATH",
        help=f"ETLPath store file (default: {DEFAULT_STORE})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # sync-aas
    p_sync_aas = sub.add_parser(
        "sync-aas",
        help="Read AIMC submodel from AAS server and reconcile with the store.",
    )
    p_sync_aas.add_argument("--aimc-url", required=True, metavar="URL",
                            help="Submodel root URL of the AIMC submodel (e.g. http://host/submodels/<base64id>). Must point to the submodel root, not a specific element.")
    p_sync_aas.add_argument("--server", required=True, metavar="URL",
                            help="AAS server base URL (e.g. http://localhost:8081).")

    # build-flow
    p_build = sub.add_parser(
        "build-flow",
        help="Build a Node-RED flow JSON from the store.",
    )
    p_build.add_argument("--output", default="tmp/flow.json", metavar="FILE",
                         help="Output file for the flow JSON (default: tmp/flow.json).")
    p_build.add_argument("--label", default=None, metavar="LABEL",
                         help="Flow tab label. Defaults to the AIMC submodel ID.")
    p_build.add_argument("--nodered-server", default=None, metavar="URL",
                         help="Node-RED server base URL. If given, deploys the flow directly.")
    p_build.add_argument("--token", default=None, metavar="TOKEN",
                         help="Node-RED admin API bearer token (if adminAuth is enabled).")
    p_build.add_argument("--dry-run", action="store_true",
                         help="Preview what would be deployed without actually deploying.")
    p_build.add_argument("--preserve-visual", action="store_true",
                         help="(Experimental) Copy node positions, labels, and colours from the "
                              "existing live flow to the rebuilt nodes before deploying. "
                              "Requires --nodered-server.")

    # sync-flow
    p_sync_flow = sub.add_parser(
        "sync-flow",
        help="Parse a Node-RED flow and reconcile with the store.",
    )
    p_sync_flow.add_argument("--flow", default=None, metavar="FILE",
                             help="Path to a Node-RED flow JSON file.")
    p_sync_flow.add_argument("--nodered-server", default=None, metavar="URL",
                             help="Node-RED server base URL (alternative to --flow).")
    p_sync_flow.add_argument("--flow-name", default=None, metavar="NAME",
                             help="Flow tab name to fetch (required with --nodered-server).")
    p_sync_flow.add_argument("--token", default=None, metavar="TOKEN",
                             help="Node-RED admin API bearer token (if adminAuth is enabled).")

    # write-aas
    p_write = sub.add_parser(
        "write-aas",
        help="Write ETLPaths from the store back to the AAS server.",
    )
    p_write.add_argument("--server", required=True, metavar="URL",
                         help="AAS server base URL (e.g. http://localhost:8081).")

    return parser


_COMMANDS = {
    "sync-aas":   cmd_sync_aas,
    "build-flow": cmd_build_flow,
    "sync-flow":  cmd_sync_flow,
    "write-aas":  cmd_write_aas,
}

if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    _COMMANDS[args.command](args)
