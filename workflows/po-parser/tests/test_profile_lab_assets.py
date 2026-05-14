import importlib


def test_profile_lab_package_imports():
    module = importlib.import_module("profile_lab")
    assert module.__all__ == ["__version__"]


def test_commands_module_exposes_main():
    commands = importlib.import_module("profile_lab.commands")
    assert callable(commands.main)
