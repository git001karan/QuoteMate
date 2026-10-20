"""Restructure messages_dataset.json: split existing training into training/evaluation
(stratified by intent), keeping all newly added samples in training only."""
import json
import random
from collections import defaultdict
from pathlib import Path

DATASET = Path("sample_data/messages_dataset.json")

with open(DATASET, "r", encoding="utf-8") as f:
    data = json.load(f)

training = data.get("training", [])
if not training:
    raise ValueError("No training samples found")

# If evaluation already exists, skip restructure
if "evaluation" in data:
    print(f"Evaluation already exists: {len(data['evaluation'])} samples")
else:
    # Stratified split: 20% of each intent goes to evaluation
    by_intent = defaultdict(list)
    for s in training:
        by_intent[s["intent"]].append(s)

    random.seed(42)
    eval_samples = []
    new_training = []
    for intent, samples in by_intent.items():
        random.shuffle(samples)
        n_eval = max(1, int(len(samples) * 0.2))
        eval_samples.extend(samples[:n_eval])
        new_training.extend(samples[n_eval:])

    data["training"] = new_training
    data["evaluation"] = eval_samples

    with open(DATASET, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Training: {len(new_training)}, Evaluation: {len(eval_samples)}")
    for intent in sorted(by_intent):
        n_train = sum(1 for s in new_training if s["intent"] == intent)
        n_eval = sum(1 for s in eval_samples if s["intent"] == intent)
        print(f"  {intent}: train={n_train}, eval={n_eval}")