#!/usr/bin/python
# -*- coding: utf-8

from contextlib import contextmanager
from mercurial.i18n import _
from requests import ConnectionError, HTTPError

from cwclientlib import cwproxy, cwproxy_for

URL = 'https://www.cubicweb.org/'


def wraprql(meth):
    def wrapper(*args, **kwargs):
        reply = meth(*args, **kwargs)
        try:
            reply.raise_for_status()
            return reply.json()
        except ValueError:
            print("ERROR: %s" % reply.text)
            print("REQ: %s %s" % (args, kwargs))
            return None
        except HTTPError as exc:
            return '\n'.join(("%s" % exc, reply.json()['reason']))
    return wrapper


class JplProxy(cwproxy.CWProxy):
    rql = wraprql(cwproxy.CWProxy.rql)
    rqlio = wraprql(cwproxy.CWProxy.rqlio)

    def execute(self, rql, args=None):
        # reimplemented since rqlio is wrapped
        result = self.rqlio([(rql, args)])
        if isinstance(result, list):
            result = result[0]
        return result


def getcwcliopt(name, ui, opts, default=None, isbool=False):
    value = default
    if getattr(ui, 'config', None) and ui.config('jpl', name):
        value = ui.config('jpl', name)
    name = name.replace('-', '_')
    if opts and opts.get(name):
        value = opts[name]
    if isbool and value not in (None, True, False):
        value = value.lower() in ('t', 'true', '1', 'y', 'yes')
    return value


@contextmanager
def build_proxy(ui, opts=None):
    """Build a cwproxy"""
    try:
        endpoint = getcwcliopt('endpoint', ui, opts, default=URL)
        yield cwproxy_for(endpoint, proxycls=JplProxy)
    except ConnectionError as exc:
        if ui.tracebackflag:
            raise
        try:
            msg = exc[0].reason
        except (AttributeError, IndexError):
            msg = str(exc)
        ui.warn(_('abort: error: %s\n') % msg)
