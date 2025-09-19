"""Utility functions for handling VLNV strings."""
from dataclasses import dataclass

@dataclass
class VLNV:
    """
    Represents a VLNV (Vendor:Library:Name:Version) identifier.

    Attributes:
        vendor (str): The vendor part of the VLNV string.
        library (str): The library part of the VLNV string.
        name (str): The name part of the VLNV string.
        version (str): The version part of the VLNV string.
    """
    vendor: str
    library: str
    name: str
    version: str

    @classmethod
    def from_string(cls, vlnv: str) -> "VLNV":
        """
        Parses a VLNV string and returns a VLNV instance.
        If vendor or library are missing, sets them to None.

        Args:
            vlnv (str): The VLNV string to parse (format: vendor:library:name:version).

        Returns:
            VLNV: The parsed VLNV instance.
        """
        parts = vlnv.split(':',3)
        while len(parts) < 4:
            parts.insert(0, None)
        return cls(*parts)

    def to_string(self) -> str:
        """
        Returns the VLNV as a colon-separated string.
        """
        return ':'.join(str(part) for part in [self.vendor, self.library, self.name, self.version])

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return self.to_string()
