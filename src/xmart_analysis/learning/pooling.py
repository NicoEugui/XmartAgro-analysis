"""The gradual rule shared by the three models: value = (n * own + k * regional) / (n + k).

A field or crop with no data of its own (n = 0) gets the regional value; with many examples it weighs almost only its own.
`k` is how many examples of its own make it weigh as much as the region."""


def shrink(n, own, regional, k):
    return (n * own + k * regional) / (n + k)
