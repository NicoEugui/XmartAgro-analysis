"""The model registry: every trained version, whether it was published, and the trained file.

A candidate replaces the published version only if the data is enough and it beats the fixed starting rule on fields it has never
seen; otherwise it stays a candidate with the reason. The pipeline always reads `published`, so a bad training changes nothing."""

import json
import pickle
from pathlib import Path


class Registry:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.path = self.folder / "registry.json"

    def entries(self):
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else []

    def register(self, learner, validation, n_examples, n_fields, trained_on, ready, simulated):
        """Store the trained model as the next version; returns its entry."""
        entries = self.entries()
        mine = [e for e in entries if e["model"] == learner.name]
        metrics = {k: v["mean"] for k, v in validation["metrics"].items()}
        publish = ready[0] and learner.improves(metrics)
        reason = ("beats the fixed rule on fields apart" if publish else ready[1] or "does not beat the fixed rule on fields apart")
        version = max((e["version"] for e in mine), default=0) + 1
        if publish:
            for e in mine:
                if e["state"] == "published":
                    e["state"] = "retired"
        self.folder.mkdir(parents=True, exist_ok=True)
        artifact = f"model_{learner.name}_v{version}.pkl"
        (self.folder / artifact).write_bytes(pickle.dumps(learner))
        entry = {"model": learner.name, "version": version, "state": "published" if publish else "candidate", "reason": reason,
                 "trained_on": trained_on, "n_examples": n_examples, "n_fields": n_fields, "simulated_data": simulated,
                 "validation": validation, "artifact": artifact}
        self.path.write_text(json.dumps(entries + [entry], indent=2) + "\n", encoding="utf-8")
        return entry

    def published(self, name):
        """(entry, model) of the published version of a model, or None."""
        live = [e for e in self.entries() if e["model"] == name and e["state"] == "published"]
        if not live:
            return None
        return live[-1], pickle.loads((self.folder / live[-1]["artifact"]).read_bytes())
