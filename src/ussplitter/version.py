from typing import Any


class SemanticVersion:
    def __init__(self, major: int, minor: int, patch: int):
        self.major = major
        self.minor = minor
        self.patch = patch

    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}"

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, SemanticVersion):
            return False
        return (
            self.major == other.major
            and self.minor == other.minor
            and self.patch == other.patch
        )

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, SemanticVersion):
            return False
        if self.major < other.major:
            return True
        elif self.major == other.major:
            if self.minor < other.minor:
                return True
            elif self.minor == other.minor:
                return self.patch < other.patch
        return False

    def parity(self, other: "SemanticVersion") -> bool:
        return self.major == other.major

    @staticmethod
    def from_string(version: str) -> "SemanticVersion":
        major, minor, patch = map(int, version.split("."))
        return SemanticVersion(major, minor, patch)

    @staticmethod
    def from_tuple(version: tuple) -> "SemanticVersion":
        return SemanticVersion(*version)


class ProtocolVersion(SemanticVersion):
    """Semantic versioning for protocol versions."""
