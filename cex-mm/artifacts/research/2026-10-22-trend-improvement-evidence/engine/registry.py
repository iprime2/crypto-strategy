"""Variant registry shared by evaluate.py (the harness) and variants.py (the pre-registered list)."""
VARIANTS = {}


def variant(name):
    def deco(f):
        VARIANTS[name] = f
        return f
    return deco
