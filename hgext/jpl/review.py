#!/usr/bin/python
# -*- coding: utf-8

import itertools
import sys
enc = sys.stdout.encoding or 'ascii'

from cwclientlib import builders
from .jplproxy import build_proxy

def ask_review(client, revs):
    eids = client.rql(
        '''Any P WHERE P patch_revision R, R changeset IN ({revs}),
                       P in_state S, S name 'in-progress'
        '''.format(revs=','.join('%r'%rev for rev in revs)))
    queries = [builders.build_trinfo(eid[0], 'ask review') for eid in eids]
    return client.rqlio(queries)

def show_review(client, revs, committer=None):
    query = '''Any PN, P, C, N, GROUP_CONCAT(L) GROUPBY PN,P,C,N WHERE
                P patch_revision R, R changeset IN ({revs}), P in_state S,
                S name N, P patch_name PN, P patch_reviewer U?,
                U login L, R changeset C'''
    fmt = {'revs': ','.join('%r' % rev for rev in revs)}
    if committer:
        query += ', P patch_committer PC, PC login "{committer}"'
        fmt['committer'] = committer
    return client.rqlio([(query.format(**fmt), {})])[0]

def assign(client, revs, committer):
    """Assign patches corresponding to specified revisions to specified committer.
    """
    revstr = ','.join('%r'%rev for rev in revs)
    if revstr.count(',') > 0:
        revq = 'IN ({revs})'.format(revs=revstr)
    else:
        revq = revstr
    query = '''SET P patch_committer U WHERE P patch_revision R,
                                             R changeset {revq},
                                             U login '{login}'
            '''.format(revq=revq, login=committer)
    return client.rqlio([(query, {})])[0]

def sudo_make_me_a_ticket(client, repo, rev, version):
    query = '''INSERT Ticket T: T concerns PROJ, T title %%(title)s, T description %%(desc)s%s
               WHERE REV from_repository REPO, PROJ source_repository REPO, REV changeset %%(cs)s%s'''
    if version:
        query %= (', T done_in V', ', V num %(version)s, V version_of PROJ')
    else:
        query %= ('', '')
    desc = repo[rev].description()
    if not desc:
        raise Exception('changeset has no description')
    args = {
        'title': desc.splitlines()[0],
        'desc': desc,
        'cs': str(repo[0]),
        'version': version,
    }
    return client.rqlio([(query, args)])
