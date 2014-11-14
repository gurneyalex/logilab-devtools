# everythin now lives in logilab.packaging

from logilab.common.deprecation import class_moved

deprecation_msg = '[0.23] logilab.devtools.lib moved to logilab.packaging.lib'
from logilab.packaging.lib import TextReporter
TextReporter = class_moved(TextReporter, message=deprecation_msg)

