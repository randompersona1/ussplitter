# Copyright (C) 2025 randompersona1
#
# USSplitter is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# USSplitter is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with USSplitter. If not, see <https://www.gnu.org/licenses/>.

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
            raise TypeError(
                "Cannot compare 'SemanticVersion' with a non-'SemanticVersion' type"
            )
        return (
            self.major == other.major
            and self.minor == other.minor
            and self.patch == other.patch
        )

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, SemanticVersion):
            raise TypeError(
                "Cannot compare 'SemanticVersion' with a non-'SemanticVersion' type"
            )
        return (self.major, self.minor, self.patch) < (
            other.major,
            other.minor,
            other.patch,
        )

    def parity(self, other: "SemanticVersion") -> bool:
        if not isinstance(other, SemanticVersion):
            return False
        if self.major != other.major:
            return False
        if self.major == 0:
            return self.minor == other.minor
        return True

    @staticmethod
    def from_string(version: str) -> "SemanticVersion":
        major, minor, patch = map(int, version.split("."))
        return SemanticVersion(major, minor, patch)

    @staticmethod
    def from_tuple(version: tuple) -> "SemanticVersion":
        return SemanticVersion(*version)
