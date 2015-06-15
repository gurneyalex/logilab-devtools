""" Helpers that are useful for merge tools that are guestrepo specific. """

import os, os.path as osp
import shutil

from mercurial import config, extensions, hg, ui, util, node, error


def load_guestrepo():
    # load guestrepo module and check that current repo is a guestrepo-managed master repo
    for ext, mod in extensions.extensions():
        if ext == 'guestrepo':
            guestrepo = mod.guestrepo
            break
    else:
        raise util.Abort('Cannot find the guestrepo extension! Check your configuration')
    return guestrepo


def to_gr_entry(ui, gr):
    try:
        guestrepo = hg.repository(ui, gr.root, create=False)
        changeset_id = node.hex(guestrepo[gr.csid].node())
    except error.RepoLookupError:
        ui.write_err("Lookup Error: cannot find '%s' in '%s'\n" % (gr.csid, gr.name))
        changeset_id = gr.csid
    return "%s = %s %s\n" % (gr.configpath.ljust(10), gr.name.ljust(10), changeset_id)


def to_mapping_entry(ui, gr):
    return "%s = %s" % gr.configpath.ljust(10), gr.name


def copy_into_root(repo, path):
    """
    Move file at given `path` into the guestrepo `repo` if it does not
    already lie in it, and return the resulting path.

    Otherwise, do nothing, but return the original path.
    """
    if not path.startswith(repo.root):
        newpath = osp.join(repo.root, osp.basename(path))
        num = 0
        while osp.exists(osp.join(newpath, str(num))):
            num += 1
        shutil.copyfile(path, newpath)
        path = newpath
    return path[len(repo.root)+1:]


def gmmerge(local, other):
    repo = hg.repository(ui.ui(), '.')
    guestrepo = load_guestrepo()

    gmlocald = guestrepo.readconfig(copy_into_root(repo, local), repo[None])['']
    gmotherd = guestrepo.readconfig(copy_into_root(repo, other), repo[None])['']

    conflicts = dict((key, (val, grotherd[key]))
                     for (key, val) in gmlocald.iteritems()
                     if (key in gmotherd and gmotherd[key] != val))

    outstr = ["%s = %s" % (key, val)
              for (key, val) in chain(gmlocald.iteritems(), gmotherd.iteritems())
              if key not in conflicts]

    for key, localval, otherval in conflicts:
        outstr.append('<<<<<<< local')
        pass

    return bool(conflicts), '\n'.join(outstr) + '\n'


def grmerge(local, base, other):
    repo = hg.repository(ui.ui(), '.')
    guestrepo = load_guestrepo()

    try:
        grlocal = guestrepo.getguests(repo, copy_into_root(repo, local), local=True)
        grother = guestrepo.getguests(repo, copy_into_root(repo, other), local=True)
        grbase = guestrepo.getguests(repo, copy_into_root(repo, base), local=True)
    except error.RepoLookupError:
        sys.exit(1)

    grlocald = dict([(guest.name, guest) for guest in grlocal])
    grotherd = dict([(guest.name, guest) for guest in grother])
    grbased = dict([(guest.name, guest) for guest in grbase])

    output = {}
    outnames = []
    for loc in grlocal:
        output[loc.name] = [loc]
        outnames.append(loc.name)
        if loc.name in grotherd:
            oth = grotherd[loc.name]
            if oth.csid != loc.csid:
                srepo = hg.repository(ui.ui(), loc.root)
                anc = srepo.revs('ancestor(%ls)', (oth.csid, loc.csid)).last()
                anc = srepo[anc]
                known = [srepo[oth.csid], srepo[loc.csid]]
                if anc in known:
                    known.remove(anc)
                    output[loc.name][0].csid = known[0].hex()[:12]
                else: # unmanagable conflict
                    output[loc.name].append(oth)

    for loc in grlocal:
        if loc.name not in grotherd:
            if loc.name in grbased:
                if loc.csid != grbased[loc.name].csid:
                    # conflict: other removed an entry that local modified
                    output[loc.name] = [loc, None]
                    outnames.append(loc.name)
                else:
                    # entry has been removed in other branch, keep it removed
                    pass

    for oth in grother:
        if oth.name not in grlocald:
            if oth.name in grbased:
                if loc.name not in grbased or oth.csid != grbased[loc.name].csid:
                    # conflict: local removed an entry that other modified
                    output[oth.name] = [None, oth]
                    outnames.append(oth.name)
                else:
                    # entry has been removed in local branch, keep it removed
                    pass
            else:
                # entry has been added in other
                output[oth.name] = [oth]
                outnames.append(oth.name)

    outstr = []
    conflict = False
    #for name, out in output.iteritems():
    for name in outnames:
        out = output[name]
        if len(out) == 1:
            outstr.append(to_gr_entry(repo.ui, out[0]))
        else:
            outstr.append('<<<<<<< local\n')
            if out[0] is not None:
                outstr.append(to_gr_entry(repo.ui, out[0]))
            outstr.append('=======\n')
            if out[1] is not None:
                outstr.append(to_gr_entry(repo.ui, out[1]))
            outstr.append('>>>>>>> other\n')
            conflict = True
    return conflict, "".join(outstr)
