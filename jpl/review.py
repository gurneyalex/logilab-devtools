#!/usr/bin/python
# -*- coding: utf-8

import itertools
import sys
enc = sys.stdout.encoding or 'ascii'

from logilab.devtools.jpl.jplproxy import build_proxy, RequestError
from cwclientlib import builders

def ask_review(client, revs):
    eids = client.rql(
        '''Any P WHERE P patch_revision R, R changeset IN ({revs}),
                       P in_state S, S name 'in-progress'
        '''.format(revs=','.join('%r'%rev for rev in revs)))
    queries = [builders.build_trinfo(eid[0], 'ask review') for eid in eids]
    return client.rqlio(queries)

def show_review(client, revs):
    return client.rql(
        '''Any PN, URI, N WHERE P patch_revision R, R changeset IN ({revs}),
             P in_state S, S name N, P cwuri URI, P patch_name PN
        '''.format(revs=','.join('%r' % rev for rev in revs)), vid='jsonexport')

