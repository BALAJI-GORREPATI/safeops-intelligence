import argparse
import json
from pathlib import Path
from .generator import GeneratorConfig, generate, checksums, canonical
from .rules import detect, evaluate
from .validation import validate
from .artifacts import export_dataset, write_dictionary


def main():
    parser = argparse.ArgumentParser(description="SafeOps deterministic data tools")
    parser.add_argument("command", choices=["generate", "validate", "evaluate", "reproduce", "dictionary", "seed"])
    parser.add_argument("--preset", choices=["starter", "full"], default="starter")
    parser.add_argument("--seed", type=int, default=20261022)
    parser.add_argument("--output", default="exports/starter")
    args = parser.parse_args()
    if args.command == "dictionary":
        write_dictionary(Path("docs")); return
    config = GeneratorConfig.preset_config(args.preset, seed=args.seed)
    data = generate(config)
    operational = {k: v for k, v in data.items() if k != "ground_truth"}
    detections = detect(operational)
    report = {"validation": validate(operational, data["ground_truth"]), "evaluation": evaluate(operational, data["ground_truth"], detections), "detections": detections}
    repro = None
    if args.command in ("generate", "reproduce"):
        second = generate(config)
        first_sums, second_sums = checksums(data), checksums(second)
        repro = {"tested": True, "identical": first_sums == second_sums, "first": first_sums, "second": second_sums,
                 "excluded_metadata": "None; generated ingestion timestamps are deterministic"}
        export_dataset(data, config, report, args.output, repro)
    if args.command == "seed":
        from .services import generate_and_store
        from .db import Session
        from .models import DatasetGenerationRun
        from .generator import digest, VERSION
        id = "sim-"+digest({"version": VERSION, **config.model_dump()})[:10]
        with Session.begin() as db:
            if db.get(DatasetGenerationRun, id):
                print("Dataset already exists; preserved unchanged:", id); return
            db.add(DatasetGenerationRun(id=id, status="QUEUED", progress=0, config=config.model_dump(), counts={}))
        generate_and_store(id, config)
    print(json.dumps({"counts": checksums(data)["counts"], "checksum": checksums(data)["overall"], "validation": report["validation"]["counts"],
                      "evaluation": report["evaluation"], "reproducible": repro and repro["identical"]}, indent=2))
    if report["validation"]["status"] == "FAIL": raise SystemExit(1)


if __name__ == "__main__": main()
