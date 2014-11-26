#!/usr/bin/python
# -*- coding: utf-8


URL = 'https://www.cubicweb.org/'

from contextlib import contextmanager
from mercurial import util
from mercurial.i18n import _
from requests import ConnectionError, HTTPError

import itertools

from cwclientlib import cwproxy

def wraprql(meth):
    def wrapper(*args, **kwargs):
        reply = meth(*args, **kwargs)
        try:
            reply.raise_for_status()
            return reply.json()
        except ValueError:
            print "ERROR:", reply.text
            print "REQ:", args, kwargs
            return None
        except HTTPError as exc:
            return '\n'.join(("%s" % exc, reply.json()['reason']))
    return wrapper

class MyProxy(cwproxy.CWProxy):
    rql = wraprql(cwproxy.CWProxy.rql)
    rqlio = wraprql(cwproxy.CWProxy.rqlio)

class RequestError(IOError):
    """Exception raised when the request fails."""

def getlglbopt(name, ui, opts, default=None, isbool=False):
    value = default
    if getattr(ui, 'config', None) and ui.config('lglb', name):
        value = ui.config('lglb', name)
    name = name.replace('-', '_')
    if opts.get(name):
        value = opts[name]
    if isbool and value not in (None, True, False):
        value = value.lower() in ('t','true','1','y','yes')
    return value

@contextmanager
def build_proxy(ui, opts):
    """Build a cwproxy"""

    try:
        base_url = getlglbopt('forge-url', ui, opts, default=URL)
        verify = not getlglbopt('no-verify-ssl', ui, opts, isbool=True)
        mech = getlglbopt('auth-mech', ui, opts)
        auth = None

        if mech and mech not in ('signedrequest', 'kerberos'):
            raise util.Abort(_('unknown authentication mechanisme specified with --auth-mech'))

        if mech == 'signedrequest':
            token = getlglbopt('auth-token', ui, opts)
            secret = getlglbopt('auth-secret', ui, opts)
            if not token or not secret:
                raise util.Abort(_('you must provide your authentication token and secret'))

            auth = cwproxy.SignedRequestAuth(token, secret)
        if mech == 'kerberos':
            from requests_kerberos import HTTPKerberosAuth, OPTIONAL
            auth = HTTPKerberosAuth(mutual_authentication=OPTIONAL)

        yield MyProxy(base_url, auth=auth, verify=verify)
    except ConnectionError as exc:
        if ui.tracebackflag:
            raise
        try:
            msg = exc[0].reason
        except (AttributeError, IndexError):
            msg = str(exc)
        ui.warn(_('abort: error: %s\n') % msg)


