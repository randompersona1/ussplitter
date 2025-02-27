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

from ussplitter.version import SemanticVersion

USSPLITTER_PROTOCOL_VERSION = SemanticVersion(1, 0, 0)
LEAST_COMPATIBLE_USDB_SYNCER_VERSION = SemanticVersion(0, 12, 0)

try:
    from ussplitter._version import __version__
    USSPLITTER_VERSION = SemanticVersion.from_string(__version__)
except ImportError:
    USSPLITTER_VERSION = SemanticVersion(0, 0, 0)
