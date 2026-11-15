"""The three models. Each one learns from the examples of all fields and is judged on fields it has never seen.

All share the `Learner` interface (so validation, registry and training treat them alike) and the gradual rule of `pooling`:
B corrects the satellite, A turns the stress the model computes into the chance the producer calls the season bad, C reads what
grew from the shape of a greenness curve. They need numpy and scipy; model C also needs scikit-learn (the `learn` extra).
"""

import math
from collections import Counter

import numpy as np
from scipy.optimize import minimize

from ..engine import crops_uy as cu
from ..engine import deficit, tables
from . import ndvi, pooling


class Learner:
    """What validation, registry and training need from a model."""

    name = ""
    primary = ""  # metric that decides publication
    baseline = ""  # the same metric for the fixed starting rule
    lower_is_better = False
    min_constant = ""  # constant holding the minimum amount of data to publish

    def ready(self, rows):
        """(True, "") if there is enough data to publish, else (False, why)."""
        raise NotImplementedError

    def fit(self, rows):
        raise NotImplementedError

    def metrics(self, rows):
        """{metric: value} on examples the model did not see; must contain `primary` and `baseline`."""
        raise NotImplementedError

    def improves(self, metrics):
        better = metrics[self.primary] < metrics[self.baseline] if self.lower_is_better else metrics[self.primary] > metrics[self.baseline]
        return bool(better)


def _by_field(rows):
    groups = {}
    for row in rows:
        groups.setdefault(row["field_id"], []).append(row)
    return groups


def _rmse(errors):
    return float(math.sqrt(np.mean(np.square(errors))))


class ModelB(Learner):
    """How much the satellite is off in a field like this one: sensor = f(satellite, clay, slope, season), then the field's own mean error."""

    name, primary, baseline, lower_is_better = "B", "regional_rmse", "satellite_rmse", True

    @staticmethod
    def _regional_design(rows):
        s = np.array([r["smap"] for r in rows])
        clay, slope = np.array([r["clay"] for r in rows], float), np.array([r["slope_pct"] for r in rows], float)
        return np.column_stack([np.ones(len(rows)), s, clay, slope, s * clay, s * slope,
                                [r["season_sin"] for r in rows], [r["season_cos"] for r in rows]])

    def ready(self, rows):
        enough = [f for f, rs in _by_field(rows).items() if len(rs) >= tables.constant("learn_min_days_b")]
        return (len(enough) >= 3, "" if len(enough) >= 3 else f"{len(enough)} fields with {tables.constant('learn_min_days_b')} days of overlap, 3 needed")

    def fit(self, rows):
        self.regional = np.linalg.lstsq(self._regional_design(rows), np.array([r["sensor"] for r in rows]), rcond=None)[0]
        return self

    def predict(self, rows, own=()):
        """Corrected moisture of `rows`; with `own` (earlier rows of the same field) the regional estimate is shifted by the field's own
        mean error, weighed by how many days there are (a line fitted to a few months extrapolates badly, a mean does not)."""
        regional = self._regional_design(rows) @ self.regional
        if not own:
            return regional
        gap = float(np.mean(np.array([r["sensor"] for r in own]) - self._regional_design(own) @ self.regional))
        return pooling.shrink(len(own), regional + gap, regional, tables.constant("learn_pool_k_b"))

    def metrics(self, rows):
        days = tables.constant("learn_min_days_b")
        satellite, regional, own_errors, after_satellite = [], [], [], []
        for field_rows in _by_field(rows).values():
            ordered = sorted(field_rows, key=lambda r: r["date"])
            y = np.array([r["sensor"] for r in ordered])
            s = np.array([r["smap"] for r in ordered])
            satellite += list(s - y)
            regional += list(self.predict(ordered) - y)
            own, rest = ordered[:days], ordered[days:]
            if rest:
                own_errors += list(self.predict(rest, own) - np.array([r["sensor"] for r in rest]))
                after_satellite += [r["smap"] - r["sensor"] for r in rest]
        out = {"satellite_rmse": _rmse(satellite), "regional_rmse": _rmse(regional)}
        if own_errors:
            out.update({f"with_{days}_days_rmse": _rmse(own_errors), f"satellite_rmse_after_{days}_days": _rmse(after_satellite)})
        return out


CLASSES = ("bad", "normal", "good")
BASELINE_CLASS = {"low_deficit": "good", "moderate_deficit": "normal", "high_deficit": "bad"}


def _sigmoid(x):
    return 1 / (1 + np.exp(-x))


class ModelA(Learner):
    """Chance that the producer calls a season bad, normal or good given the stress: an ordinal logistic curve per crop and one for all."""

    name, primary, baseline = "A", "accuracy", "fixed_cuts_accuracy"

    def ready(self, rows):
        counts = Counter(r["crop"] for r in rows)
        need = tables.constant("learn_min_examples_a")
        short = sorted(c for c, n in counts.items() if n < need)
        return (not short, "" if not short else f"fewer than {need} seasons: {', '.join(short)}")

    @staticmethod
    def _fit(stress, labels):
        """(slope, first threshold, log gap) of P(class <= j) = sigmoid(theta_j + slope * stress)."""
        y = np.array([CLASSES.index(c) for c in labels])
        x = np.asarray(stress, float)

        def loss(w):
            slope, t1, gap = w
            cum = [_sigmoid(t1 + slope * x), _sigmoid(t1 + math.exp(gap) + slope * x)]
            p = np.column_stack([cum[0], cum[1] - cum[0], 1 - cum[1]])
            return -np.sum(np.log(np.clip(p[np.arange(len(y)), y], 1e-9, 1))) + 1e-3 * slope ** 2
        return minimize(loss, [5.0, -2.5, 0.5], method="L-BFGS-B").x

    @staticmethod
    def _proba(w, stress):
        slope, t1, gap = w
        cum = [_sigmoid(t1 + slope * stress), _sigmoid(t1 + math.exp(gap) + slope * stress)]
        return np.array([cum[0], cum[1] - cum[0], 1 - cum[1]])

    def fit(self, rows):
        self.regional = self._fit([r["model_stress"] for r in rows], [r["class"] for r in rows])
        self.crops = {}
        for crop in {r["crop"] for r in rows}:
            own = [r for r in rows if r["crop"] == crop]
            if len({r["class"] for r in own}) > 1:
                self.crops[crop] = (len(own), self._fit([r["model_stress"] for r in own], [r["class"] for r in own]))
        return self

    def predict_proba(self, crop, stress):
        regional = self._proba(self.regional, stress)
        if crop not in self.crops:
            return regional
        n, w = self.crops[crop]
        return pooling.shrink(n, self._proba(w, stress), regional, tables.constant("learn_pool_k_a"))

    def predict(self, crop, stress):
        return CLASSES[int(np.argmax(self.predict_proba(crop, stress)))]

    def metrics(self, rows):
        hits = sum(self.predict(r["crop"], r["model_stress"]) == r["class"] for r in rows)
        fixed = sum(BASELINE_CLASS[deficit.classify(r["model_stress"])] == r["class"] for r in rows)
        return {"accuracy": hits / len(rows), "fixed_cuts_accuracy": fixed / len(rows)}


class ModelC(Learner):
    """What grew (a crop, or fallow) from five numbers of the greenness curve: a random forest."""

    name, primary, baseline = "C", "accuracy", "most_common_accuracy"

    def ready(self, rows):
        need = tables.constant("learn_min_examples_c")
        return (len(rows) >= need, "" if len(rows) >= need else f"{len(rows)} seasons, {need} needed")

    @staticmethod
    def _x(rows):
        return [[r[f] for f in ndvi.FEATURES] for r in rows]

    def fit(self, rows):
        from sklearn.ensemble import RandomForestClassifier
        self.forest = RandomForestClassifier(n_estimators=tables.constant("learn_forest_trees"),
                                             random_state=tables.constant("learn_seed") % 2 ** 31).fit(self._x(rows), [r["crop"] for r in rows])
        self.common = Counter(r["crop"] for r in rows).most_common(1)[0][0]
        return self

    def predict(self, rows):
        return list(self.forest.predict(self._x(rows)))

    def propose(self, rows):
        """[(crop or fallow, confidence)] for curves: the most likely answer and how much of the forest's vote it has."""
        votes = self.forest.predict_proba(self._x(rows))
        return [(str(self.forest.classes_[row.argmax()]), float(row.max())) for row in votes]

    @staticmethod
    def _group(crop):
        """winter crop, summer crop or fallow: what the sowing month of the table says."""
        if crop == "fallow":
            return crop
        return "winter" if cu.CROPS[crop]["sowing"][0] in (5, 6) else "summer"

    def metrics(self, rows):
        truth, predicted = [r["crop"] for r in rows], self.predict(rows)
        return {"accuracy": float(np.mean([p == t for p, t in zip(predicted, truth)])),
                "most_common_accuracy": float(np.mean([self.common == t for t in truth])),
                "season_group_accuracy": float(np.mean([self._group(p) == self._group(t) for p, t in zip(predicted, truth)]))}


MODELS = {"B": ModelB, "A": ModelA, "C": ModelC}
