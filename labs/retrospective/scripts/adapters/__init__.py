from . import claude

ADAPTERS = {"claude": claude}


def get_adapter(name):
    return ADAPTERS.get(name)
