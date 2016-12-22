#!/usr/bin/python
# -*- coding: utf-8

import itertools
import sys

from .jplproxy import build_proxy, URL

ENCODING = sys.stdout.encoding or 'ascii'
INDENT = '  '

PATCH_RQL = """
rql:
DISTINCT
Any P,PN,SN,R,T,TTITLE,TDESC,TSN
ORDERBY R
WITH P,PN,SN,R,T,TTITLE,TDESC,TSN
BEING ({unions})
"""

UNIONS = ["""
(Any P,PN,SN,R,T,TTITLE,TDESC,TSN
 WHERE P patch_revision R, R changeset IN ({revs}),
       P in_state S, P patch_name PN,
       S name SN, P has_activity T, T in_state TS, T title TTITLE,
       T description TDESC?, TS name TSN
       {taskstate})
""", """
(Any P,PN,SN,R,T,TTITLE,TDESC,TSN ORDERBY R
 WHERE P patch_revision R, R changeset IN ({revs}),
       P in_state S, P patch_name PN,
       S name SN, X has_activity T, X point_of RX, P patch_revision RX,
       T in_state TS, T title TTITLE, T description TDESC?, TS name TSN
       {taskstate})
""", """
(Any P,PN,SN,R,NULL,NULL,NULL,NULL
 WHERE P patch_revision R, R changeset IN ({revs}),
       P in_state S, P patch_name PN,
       S name SN, NOT EXISTS(P has_activity T),
       NOT EXISTS(P patch_revision RX, X point_of RX, X has_activity T))
"""]

TASKNOTDONE_RQL = ', NOT TS name "done" '

COMMENTS_RQL = """
Any C
WHERE C comments X,
      X eid {eid}
"""


def print_comment(ui, comment, level=1):
    indent = INDENT * level
    content = comment['content'].strip().replace('\n', '\n' + indent + INDENT)
    msg = u'{indent}> {content}\n'.format(indent=indent, content=content)
    ui.write(msg.encode(ENCODING, 'replace'), label='jpl.tasks.comment')
    for c in comment['comments']:
        print_comment(ui, c, level=level + 1)


def print_task(ui, reveid, ttitle, tstate, tdesc, url):
    msg = u'{indent}[{state}] {title} ({url})\n'.format(
        indent=INDENT, url=url,
        state=tstate.upper(), title=ttitle)
    ui.write(msg.encode(ENCODING, 'replace'),
             label='jpl.tasks.task.{state}'.format(state=tstate))
    if tdesc:
        desc = tdesc.strip().replace('\n', '\n' + INDENT)
        msg = u'{indent}{content}\n'.format(indent=INDENT, content=desc)
        ui.write(msg.encode(ENCODING, 'replace'),
                 label='jpl.tasks.description')
        # for comment in task['comments']:
        #     print_comment(ui, comment)
    ui.write('\n')


def print_tasks(client, ui, revs, showall=False):
    """A python script that displays tasks requested by reviewwers on a patch
    on www.cubicweb.org"""
    revs = ','.join('%r' % rev for rev in revs)
    if showall:
        rql = PATCH_RQL.format(unions='UNION'.join(UNIONS))
        taskstate = ''
    else:
        rql = PATCH_RQL.format(unions='UNION'.join(UNIONS[:2]))
        taskstate = TASKNOTDONE_RQL

    patchesdata = client.rql(rql.format(revs=revs, taskstate=taskstate),
                             vid='jsonexport')
    if not patchesdata:
        raise ValueError("no tasks found for revisions: %r" % ','.join(revs))

    patchesdata = itertools.groupby(patchesdata, lambda x: x[:3])
    for (peid, pname, pstate), patchdata in patchesdata:
        msg = '{name} {url} ({state})\n\n'.format(
            url=client.build_url(str(peid)), state=pstate, name=pname)
        ui.write(msg, label='jpl.tasks.patch')
        teids = set()
        for (peid, pname, pstate, reveid,
             teid, ttitle, tdesc, tstate) in patchdata:
            if teid is None or teid in teids:
                continue
            teids.add(teid)
            print_task(ui, reveid, ttitle, tstate, tdesc,
                       client.build_url(str(teid)))


if __name__ == '__main__':
    import sys
    import argparse
    # cmdline interface
    epilog = ('The `colorama <https://pypi.python.org/pypi/colorama>`_ '
              'module is required to enable colored output.')
    parser = argparse.ArgumentParser(epilog=epilog)
    parser.add_argument('revs', default=[], metavar='REVS', nargs='+',
                        help='tasks for the given revision (short hex)', ),
    parser.add_argument('-U', '--endpoint', default=URL, metavar='URL',
                        help=('cwclientlib endpoint ID of the forge (jpl) '
                              'server [%s]' % URL))
    parser.add_argument('-c', '--color', default='auto', metavar='WHEN',
                        choices=('auto', 'never', 'always'),
                        help='display data with color [auto]')
    parser.add_argument('-a', '--all', default=False, action='store_true',
                        help='display data with color [auto]')
    parser.add_argument('-S', '--no-verify-ssl', default=False,
                        action='store_true',
                        help='do NOT verify SSL server certificates')
    opts = vars(parser.parse_args())
    revs = opts.pop('revs')

    # colors
    try:
        if opts['color'] == 'never':
            raise ImportError
        if opts['color'] == 'auto' and not sys.stdout.isatty():
            raise ImportError
        from colorama import Fore
        colortable = {'reset': Fore.RESET,
                      'jpl.tasks.patch': Fore.CYAN,
                      'jpl.tasks.task': Fore.RED,
                      'jpl.tasks.description': Fore.RESET,
                      'jpl.tasks.comment': Fore.YELLOW,
                      'jpl.tasks.notask': Fore.GREEN}
    except ImportError:
        colortable = {}

    # output
    class output(object):
        def write(self, msg, label=None):
            sys.stdout.write(colortable.get(label, ''))
            sys.stdout.write(msg)
            sys.stdout.write(colortable.get('reset', ''))
    ui = output()
    with build_proxy(ui, opts) as client:
        print_tasks(client, ui, revs, opts)
