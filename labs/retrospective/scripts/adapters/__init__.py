from . import claude, kimi, qwen

ADAPTERS = {"claude": claude, "kimi": kimi, "qwen": qwen}


def get_adapter(name):
    return ADAPTERS.get(name)
