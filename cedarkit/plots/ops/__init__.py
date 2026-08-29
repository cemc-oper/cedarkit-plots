"""Declarative operation descriptors and strict registries."""

from .descriptor import OpDescriptor, OpRuntimeContext
from .registry import DuplicateRegistrationError, OpRegistry, RegistryProvenance

__all__ = ["DuplicateRegistrationError", "OpDescriptor", "OpRegistry", "OpRuntimeContext", "RegistryProvenance"]
