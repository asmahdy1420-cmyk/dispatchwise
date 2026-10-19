"""Command-line entry point: ``dispatchwise generate|plan|zones|serve``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from dispatchwise.dispatcher import DispatchError, plan_dispatch
from dispatchwise.synthetic import Scenario, generate_scenario


def _load(path: str) -> Scenario:
    return Scenario.model_validate_json(Path(path).read_text())


def _cmd_generate(args: argparse.Namespace) -> int:
    scenario = generate_scenario(
        n_pharmacies=args.pharmacies,
        n_drivers=args.drivers,
        n_orders=args.orders,
        n_skus=args.skus,
        seed=args.seed,
    )
    payload = scenario.model_dump_json(indent=2)
    if args.output == "-":
        sys.stdout.write(payload + "\n")
    else:
        Path(args.output).write_text(payload)
        print(
            f"wrote {args.output}: {len(scenario.pharmacies)} pharmacies, "
            f"{len(scenario.drivers)} drivers, {len(scenario.orders)} orders"
        )
    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    scenario = _load(args.scenario)
    orders = scenario.orders[args.start : args.start + args.count]
    split = failed = 0
    for order in orders:
        try:
            plan = plan_dispatch(order, scenario.pharmacies, scenario.drivers, hour=args.hour)
        except DispatchError as exc:
            failed += 1
            print(f"{order.id}: FAILED {exc}")
            continue
        split += plan.split
        stops = " -> ".join(plan.route)
        print(
            f"{order.id}: {'SPLIT' if plan.split else 'single'} "
            f"cost={plan.cost.total:.2f} eta={plan.eta_minutes:.0f}min  {stops}"
        )
    print(f"\n{len(orders)} orders, {split} split, {failed} unfulfillable")
    return 0


def _cmd_zones(args: argparse.Namespace) -> int:
    from dispatchwise.clustering import demand_zones, suggest_positioning

    scenario = _load(args.scenario)
    zones = demand_zones([o.customer for o in scenario.orders], k=args.k)
    for z in zones:
        print(
            f"zone {z.zone_id}: {z.order_count} orders ({z.share:.0%}) "
            f"centre=({z.centre.lat:.5f}, {z.centre.lon:.5f})"
        )
    for move in suggest_positioning(zones, scenario.drivers):
        print(f"  {move.driver_id} -> zone {move.zone_id} ({move.distance_km:.1f} km)")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("dispatchwise.api:app", host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dispatchwise", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="write a synthetic scenario as JSON")
    gen.add_argument("-o", "--output", default="scenario.json", help="file path or '-'")
    gen.add_argument("--pharmacies", type=int, default=8)
    gen.add_argument("--drivers", type=int, default=6)
    gen.add_argument("--orders", type=int, default=200)
    gen.add_argument("--skus", type=int, default=25)
    gen.add_argument("--seed", type=int, default=42)
    gen.set_defaults(func=_cmd_generate)

    plan = sub.add_parser("plan", help="plan orders from a scenario file")
    plan.add_argument("scenario")
    plan.add_argument("--start", type=int, default=0)
    plan.add_argument("--count", type=int, default=10)
    plan.add_argument("--hour", type=int, default=None, help="0-23, defaults to now")
    plan.set_defaults(func=_cmd_plan)

    zones = sub.add_parser("zones", help="cluster order demand (needs [clustering] extra)")
    zones.add_argument("scenario")
    zones.add_argument("-k", type=int, default=4)
    zones.set_defaults(func=_cmd_zones)

    serve = sub.add_parser("serve", help="run the HTTP API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=_cmd_serve)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
