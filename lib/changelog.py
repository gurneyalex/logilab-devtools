# everything now lives in logilab.packaging

from logilab.common.deprecation import class_moved, moved
from logilab.devtools.lib import deprecation_msg

from logilab.packaging.lib.changelog import (ChangeLogNotFound, ChangeLog,
                                             DebianChangeLogEntry,
                                             DebianChangeLog,
                                             )

ChangeLogNotFound = class_moved(ChangeLogNotFound, message=deprecation_message)
ChangeLog = class_moved(ChangeLog, message=deprecation_message)
DebianChangeLogEntry = class_moved(DebianChangeLogEntry, message=deprecation_message)
DebianChangeLog = class_moved(DebianChangeLog, message=deprecation_message)

find_ChangeLog = moved('logilab.packaging.lib.changelog', 'find_ChangeLog')
find_debian_changelog = moved('logilab.packaging.lib.changelog', 'find_debian_changelog')
get_pkg_version = moved('logilab.packaging.lib.changelog', 'get_pkg_version')
