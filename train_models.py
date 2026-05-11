"""Train all Boosted Tree models individually, one by one."""
import sys, os, time, json
sys.path.insert(0, '.')
from src.ingestion.config import settings
os.environ['GCP_PROJECT_ID'] = settings.GCP_PROJECT_ID
if settings.GCP_CREDENTIALS_PATH:
    os.environ['GCP_CREDENTIALS_PATH'] = settings.GCP_CREDENTIALS_PATH

from src.models.trainer import ModelTrainer

ROOT = os.path.dirname(os.path.abspath(__file__))
trainer = ModelTrainer()

models_to_train = [
    ("comunicación", 2022),
    ("comunicación", 2023),
    ("matemática", 2022),
    ("matemática", 2023),
    ("ccss", None),
]

results = {}

for area, year in models_to_train:
    label = f"{area} (year={year})"
    print(f"\n{'='*60}", flush=True)
    print(f"Training: {label}", flush=True)
    print(f"{'='*60}", flush=True)
    start = time.time()
    try:
        result = trainer.train_model_for_area(area, year=year)
        elapsed = time.time() - start
        results[label] = {
            "status": result.status,
            "duration_seconds": round(elapsed, 2),
            "model_name": result.model_name,
            "errors": result.errors,
            "training_stats": str(result.training_stats),
        }
        print(f"  Model : {result.model_name}", flush=True)
        print(f"  Status: {result.status}", flush=True)
        print(f"  Time  : {elapsed:.1f}s", flush=True)
        if result.errors:
            print(f"  Errors: {result.errors}", flush=True)
    except Exception as e:
        elapsed = time.time() - start
        import traceback
        traceback.print_exc()
        results[label] = {
            "status": "exception",
            "duration_seconds": round(elapsed, 2),
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
        print(f"  EXCEPTION after {elapsed:.1f}s: {e}", flush=True)

print(f"\n{'='*60}", flush=True)
print("TRAINING SUMMARY", flush=True)
print(f"{'='*60}", flush=True)
for label, r in results.items():
    icon = "OK" if r.get("status") == "success" else "FAIL"
    print(f"  [{icon}] {label}: {r['status']} ({r.get('duration_seconds', 0):.1f}s)", flush=True)
    if "model_name" in r:
        print(f"         Model: {r['model_name']}", flush=True)

out_path = os.path.join(ROOT, "training_results.json")
with open(out_path, "w") as f:
    json.dump(results, f, indent=2, default=str)
print(f"\nResults saved to: {out_path}", flush=True)
print("DONE", flush=True)
