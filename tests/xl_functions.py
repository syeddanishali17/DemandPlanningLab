"""Excel functions that pycel (the formula evaluator used in tests) does not implement."""

from statistics import NormalDist, stdev


def _flatten(args):
    for a in args:
        if isinstance(a, tuple):
            yield from _flatten(a)
        elif isinstance(a, (int, float)) and not isinstance(a, bool):
            yield a


def stdev_s(*args):
    return stdev(list(_flatten(args)))


def norm_s_inv(p):
    return NormalDist().inv_cdf(p)
