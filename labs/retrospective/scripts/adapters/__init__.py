from . import claude, qwen

ADAPTERS = {"claude": claude, "qwen": qwen}


def get_adapter(name):
    return ADAPTERS.get(name)
