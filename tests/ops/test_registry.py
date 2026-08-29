import pytest

from cedarkit.plots.ops import DuplicateRegistrationError, OpDescriptor, OpRegistry


def test_descriptor_registry_rejects_duplicate_and_has_stable_manifest():
    registry = OpRegistry.builtins()
    with pytest.raises(DuplicateRegistrationError):
        registry.register_descriptor(OpDescriptor("unit_scale", "transform", 1, 1, lambda value: value))
    assert registry.manifest() == registry.manifest()


def test_scoped_override_is_restored():
    registry = OpRegistry.builtins()
    original = registry.get("unit_scale")
    replacement = OpDescriptor("unit_scale", "transform", 1, 1, lambda value: value)
    with registry.scoped_override(replacement):
        assert registry.get("unit_scale") is replacement
    assert registry.get("unit_scale") is original
