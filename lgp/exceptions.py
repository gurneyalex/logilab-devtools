"""Exceptions package

:organization: Logilab
:copyright: 2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

class LGPException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return self.value
 
class ArchitectureException(LGPException):
   def __str__(self):
        return "unknown architecture '%s'" % self.value

class DistributionException(LGPException):
    def __str__(self):
        return "unknown distribution '%s'" % self.value
