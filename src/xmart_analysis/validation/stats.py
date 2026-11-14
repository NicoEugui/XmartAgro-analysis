import itertools
import random


def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    out, i = [0.0] * len(values), 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sx = sum((a - mx) ** 2 for a in x) ** 0.5
    sy = sum((b - my) ** 2 for b in y) ** 0.5
    return cov / (sx * sy) if sx and sy else float("nan")


def spearman(x, y):
    return pearson(ranks(x), ranks(y))


def permutation_p(x, y, exact_up_to=8, samples=20000, seed=0):
    """Two-sided permutation p-value of the Spearman correlation (exact for small n, seeded sampling otherwise)."""
    observed = abs(spearman(x, y))
    rx = ranks(x)
    if len(x) <= exact_up_to:
        perms = itertools.permutations(ranks(y))
        total = sum(1 for _ in itertools.permutations(range(len(y))))
    else:
        rng = random.Random(seed)
        base = ranks(y)
        perms = (rng.sample(base, len(base)) for _ in range(samples))
        total = samples
    hits = sum(abs(pearson(rx, list(p))) >= observed - 1e-12 for p in perms)
    return hits / total
