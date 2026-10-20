"""Run NLP evaluation on both the dev split and the held-out novelty set."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.nlp_service import NLPService  # noqa: E402

# Train on expanded dataset
svc = NLPService()

# 1. Dev evaluation split inside messages_dataset.json
dev_metrics = svc.evaluate()
print("=== DEV EVALUATION SPLIT (messages_dataset.json) ===")
print(f"Dataset: {dev_metrics['dataset']}")
print(f"Train size: {dev_metrics['train_size']}")
print(f"Evaluation size: {dev_metrics['evaluation_size']}")
print(f"Accuracy: {dev_metrics['accuracy']:.4f}")
print("\nConfusion matrix:")
for actual, row in dev_metrics["confusion_matrix"].items():
    print(f"  {actual}: {row}")
print("\nClassification report:")
for label, scores in dev_metrics["classification_report"].items():
    if isinstance(scores, dict):
        print(f"  {label}: precision={scores.get('precision', 'n/a'):.3f}, "
              f"recall={scores.get('recall', 'n/a'):.3f}, "
              f"f1={scores.get('f1-score', 'n/a'):.3f}, "
              f"support={scores.get('support', 'n/a')}")

# 2. Held-out novelty set
novelty_path = ROOT / "sample_data" / "novelty_test.json"
novelty_metrics = svc.evaluate(dataset_path=str(novelty_path))
print("\n=== HELD-OUT NOVELTY SET (novelty_test.json) ===")
print(f"Dataset: {novelty_metrics['dataset']}")
print(f"Train size: {novelty_metrics['train_size']}")
print(f"Evaluation size: {novelty_metrics['evaluation_size']}")
print(f"Accuracy: {novelty_metrics['accuracy']:.4f}")
print("\nConfusion matrix:")
for actual, row in novelty_metrics["confusion_matrix"].items():
    print(f"  {actual}: {row}")

# Save both for README reference
results = {
    "dev": dev_metrics,
    "novelty": novelty_metrics,
}
out = ROOT / "sample_data" / "nlp_evaluation_results.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\nResults saved to {out}")