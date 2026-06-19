"""FortiObfuscator — local FortiGate config obfuscation.

Pure-stdlib core. See ``engine.obfuscate`` for the entry point.
"""

from .engine import Options, obfuscate

__all__ = ["Options", "obfuscate"]
__version__ = "1.0.0"
