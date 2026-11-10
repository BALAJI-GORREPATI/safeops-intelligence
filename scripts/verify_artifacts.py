"""Compare every exported file across independent runs for both presets."""
import json
from pathlib import Path
import tempfile
from safeops.generator import GeneratorConfig, generate, checksums
from safeops.rules import detect, evaluate
from safeops.validation import validate
from safeops.artifacts import export_dataset

results = {}
for preset in ("starter", "full"):
    config = GeneratorConfig.preset_config(preset)
    outputs = []
    with tempfile.TemporaryDirectory() as tmp:
        for index in range(2):
            data = generate(config)
            operational = {k: v for k, v in data.items() if k != "ground_truth"}
            detections = detect(operational)
            report = {"validation": validate(operational, data["ground_truth"]), "evaluation": evaluate(operational, data["ground_truth"], detections), "detections": detections}
            sums = checksums(data)
            reproduction = {"tested": True, "identical": True, "first": sums, "second": sums, "excluded_metadata": "None; generated ingestion timestamps are deterministic"}
            outputs.append(export_dataset(data, config, report, Path(tmp)/str(index), reproduction))
        results[preset] = {"identical": outputs[0] == outputs[1], "compared_files": len(outputs[0]["files"]), "checksum": outputs[0]["overall"], "counts": outputs[0]["counts"]}
        assert results[preset]["identical"]
Path("docs/reproducibility-results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps(results, indent=2))
