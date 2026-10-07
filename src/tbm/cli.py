"""Command-line entry point: `python -m tbm <command>` (or `tbm <command>` after install)."""

from __future__ import annotations

import argparse
import dataclasses
import os

from .config import DATA, load_config, results_root


def _targets(config, ids):
    if not ids or ids == ["all"]:
        return list(config.targets.values())
    return [config.target(i) for i in ids]


def cmd_status(config, args):
    for t in _targets(config, args.targets):
        try:
            native = t.native_path().name
        except FileNotFoundError:
            native = "missing"
        from .af3 import find_models
        n_af3 = len(find_models(t.af3_dir))
        a1 = t.result_dir / "agent1" / "final_model.pdb"
        a2 = t.result_dir / "agent2" / "metrics.json"
        print(f"{t.id} ({t.difficulty}, PDB {t.pdb}, EU {t.eu[0]}-{t.eu[1]})\n"
              f"  fasta   : {'ok' if t.fasta.exists() else 'missing'} ({t.fasta.relative_to(DATA.parent)})\n"
              f"  native  : {native}\n"
              f"  af3     : {n_af3} model(s) in {t.af3_dir.relative_to(DATA.parent)}\n"
              f"  agent1  : {'done' if a1.exists() else 'not run'}\n"
              f"  agent2  : {'done' if a2.exists() else 'not run'}")


def cmd_fetch_native(config, args):
    from .template_search import download_cif
    for t in _targets(config, args.targets):
        p = download_cif(t.pdb, DATA / "native")
        print(f"{t.id}: {p}")


def cmd_agent1(config, args):
    from . import agent1
    settings = config.settings
    if args.backend:
        settings = dataclasses.replace(settings, search_backend=args.backend)
    if args.evalue is not None:
        settings = dataclasses.replace(settings, evalue_cutoff=args.evalue)
    if args.no_date_cutoff:
        settings = dataclasses.replace(settings, template_release_cutoff="")
    for t in _targets(config, args.targets):
        agent1.run(t, settings, n_models=args.n_models, search_only=args.search_only,
                   template=args.template if len(args.targets or []) == 1 else None)


def cmd_agent2(config, args):
    from . import agent2, claude_agent
    from .visualize import make_target_figures
    for t in _targets(config, args.targets):
        if claude_agent.baseline_mode():
            agent2.run(t)
            for p in make_target_figures(t):
                print(f"[agent2 {t.id}] wrote {p.name}")
        else:
            agent2.run_agent(t)


def cmd_report(config, args):
    from . import report
    rows = report.write(config)
    root = results_root().relative_to(DATA.parent)
    print(f"{len(rows)} row(s) -> {root}/summary.csv, summary.md, summary_metrics.png")


def cmd_run_all(config, args):
    cmd_agent1(config, args)
    cmd_agent2(config, args)
    cmd_report(config, args)


def main(argv=None):
    p = argparse.ArgumentParser(prog="tbm", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("targets", nargs="*", help="target ids (default: all)")
        sp.set_defaults(fn=fn)
        return sp

    add("status", cmd_status, "show which inputs/outputs exist")
    add("fetch-native", cmd_fetch_native, "download experimental mmCIF files into data/native")

    def agent1_opts(sp):
        sp.add_argument("--n-models", type=int, help="number of MODELLER models")
        sp.add_argument("--search-only", action="store_true",
                        help="search and rank templates without running MODELLER")
        sp.add_argument("--backend", choices=["rcsb", "local"], help="template search backend")
        sp.add_argument("--evalue", type=float, help="E-value cutoff for the search")
        sp.add_argument("--no-date-cutoff", action="store_true",
                        help="only exclude the target's own PDB entry")
        sp.add_argument("--template", help="force a template, e.g. 1ABC:A (single target only)")

    agent1_opts(add("agent1", cmd_agent1, "Agent 1: template search + MODELLER"))
    add("agent2", cmd_agent2, "Agent 2: evaluate models against the experimental structure")
    add("report", cmd_report, "aggregate results into tables and figures")
    agent1_opts(add("run-all", cmd_run_all, "agent1 + agent2 + report"))

    p.add_argument("--baseline", "--no-claude", dest="baseline", action="store_true",
                   help="score-only run without the Claude agents; results in results/baseline/")
    args = p.parse_args(argv)
    if args.baseline:
        os.environ["TBM_BASELINE"] = "1"
    args.fn(load_config(), args)


if __name__ == "__main__":
    main()
