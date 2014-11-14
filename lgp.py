# everything now lives in logilab.packaging

from warnings import warn

deprecation_msg = '[0.23] logilab.devtools.lgp moved to logilab.packaging.lgp'
warn(deprecation_msg, DeprecationWarning)

from logilab.packaging.lgp import LGP


