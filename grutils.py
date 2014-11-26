""" Helpers that are useful for merge tools that are guestrepo specific. """

import os, os.path as osp
import shutil

from mercurial import extensions, hg, util, node, error


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
