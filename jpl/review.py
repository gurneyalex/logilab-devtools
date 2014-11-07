#!/usr/bin/python
# -*- coding: utf-8

import itertools
import sys
enc = sys.stdout.encoding or 'ascii'

from logilab.devtools.jpl.jplproxy import build_proxy, RequestError
from cwclientlib import builders

def ask_review(client, revs):
    # def build_trinfo(eid, transition_name,  comment=None):
    eids = client.rql(
        '''Any P WHERE P patch_revision R, R changeset IN ({revs}),
                       P in_state S, S name 'in-progress'
        '''.format(revs=','.join('%r'%rev for rev in revs)))
    queries = [builders.build_trinfo(eid[0], 'ask review') for eid in eids]
    return client.rqlio(queries)

