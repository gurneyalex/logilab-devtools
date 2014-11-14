# everythin now lives in logilab.packaging

from logilab.common.deprecation import class_moved, moved
from logilab.devtools.lib import deprecation_msg
from logilab.packaging.lib.utils import SGMLCatalog

SGMLCatalog = class_moved(SGMLCatalog, message=deprecation_msg)
glob_match = moved('logilab.packaging.lib.pkginfo', 'glob_match')
get_scripts = moved('logilab.packaging.lib.pkginfo', 'get_scripts')

