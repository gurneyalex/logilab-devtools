#!/usr/bin/python
# -*- coding: utf-8

import itertools
import sys
enc = sys.stdout.encoding or 'ascii'

from cwclientlib import builders
from .jplproxy import build_proxy, RequestError

def ask_review(client, revs):
    eids = client.rql(
        '''Any P WHERE P patch_revision R, R changeset IN ({revs}),
                       P in_state S, S name 'in-progress'
        '''.format(revs=','.join('%r'%rev for rev in revs)))
    queries = [builders.build_trinfo(eid[0], 'ask review') for eid in eids]
    return client.rqlio(queries)

def show_review(client, revs):
    return client.rqlio([(
        '''Any PN, URI, N, GROUP_CONCAT(L) GROUPBY PN,URI,N WHERE P patch_revision R, R changeset IN ({revs}),
             P in_state S, S name N, P cwuri URI, P patch_name PN, P patch_reviewer U?, U login L
        '''.format(revs=','.join('%r' % rev for rev in revs)), {}),])[0]

def sudo_make_me_a_ticket(client, ctx, version):
    query = '''INSERT Ticket T: T concerns PROJ, T title %%(title)s, T description %%(desc)s%s
               WHERE REV from_repository REPO, PROJ source_repository REPO, REV changeset %%(cs)s%s'''
    if version:
        query %= (', T done_in V', ', V num %(version)s, V version_of PROJ')
    else:
        query %= ('', '')
    desc = ctx.description()
    if not desc:
        raise Exception('changeset has no description')
    args = {
        'title': desc.splitlines()[0],
        'desc': desc,
        'cs': str(ctx),
        'version': version,
    }
    return client.rqlio([(query, args)])
