# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Miscellaneous file manipulation functions."""
import contextlib
import glob
import gzip
import hashlib
import os
import os.path as op
import pickle
import posixpath
import re
import shutil
import subprocess as sp
from hashlib import md5
from pathlib import Path
from time import sleep, time

import simplejson as json
from nipype import __version__ as version
from nipype import config, logging
from nipype.utils.misc import is_container

fmlogger = logging.getLogger("nipype.utils")

related_filetype_sets = [(".hdr", ".img", ".mat"), (".nii", ".mat"), (".BRIK", ".HEAD")]


def _resolve_with_filenotfound(path, **kwargs):
    """Raise FileNotFoundError instead of OSError."""
    try:
        return path.resolve(**kwargs)
    except OSError as e:
        if isinstance(e, FileNotFoundError):
            raise
        raise FileNotFoundError(str(path))


def split_filename(fname):
    """Split a filename into parts: path, base filename and extension.

    Parameters
    ----------
    fname : str
        file or path name

    Returns
    -------
    pth : str
        base path from fname
    fname : str
        filename from fname, without extension
    ext : str
        file extension from fname

    Examples
    --------
    >>> from nipype.utils.filemanip import split_filename
    >>> pth, fname, ext = split_filename('/home/data/subject.nii.gz')
    >>> pth
    '/home/data'

    >>> fname
    'subject'

    >>> ext
    '.nii.gz'
    """
    # TM 07152022 - edited to add cifti and workbench extensions
    special_extensions = [
        ".nii.gz",
        ".tar.gz",
        ".niml.dset",
        ".dconn.nii",
        ".dlabel.nii",
        ".dpconn.nii",
        ".dscalar.nii",
        ".dtseries.nii",
        ".fiberTEMP.nii",
        ".trajTEMP.wbsparse",
        ".pconn.nii",
        ".pdconn.nii",
        ".plabel.nii",
        ".pscalar.nii",
        ".ptseries.nii",
        ".sdseries.nii",
        ".label.gii",
        ".label.gii",
        ".func.gii",
        ".shape.gii",
        ".rgba.gii",
        ".surf.gii",
        ".dpconn.nii",
        ".dtraj.nii",
        ".pconnseries.nii",
        ".pconnscalar.nii"
    ]

    pth = op.dirname(fname)
    fname = op.basename(fname)

    ext = None
    for special_ext in special_extensions:
        ext_len = len(special_ext)
        if (len(fname) > ext_len) and (fname[-ext_len:].lower() == special_ext.lower()):
            ext = fname[-ext_len:]
            fname = fname[:-ext_len]
            break
    if not ext:
        fname, ext = op.splitext(fname)

    return pth, fname, ext


def fname_presuffix(fname, prefix="", suffix="", newpath=None, use_ext=True):
    """Manipulate path and name of input filename.

    Parameters
    ----------
    fname : string
        A filename (may or may not include path)
    prefix : string
        Characters to prepend to the filename
    suffix : string
        Characters to append to the filename
    newpath : string
        Path to replace the path of the input fname
    use_ext : boolean
        If True (default), appends the extension of the original file
        to the output name.

    Returns
    -------
    str
        Absolute path of the modified filename

    Examples
    --------
    >>> from nipype.utils.filemanip import fname_presuffix
    >>> fname = 'foo.nii.gz'
    >>> fname_presuffix(fname,'pre','post','/tmp')
    '/tmp/prefoopost.nii.gz'

    >>> from nipype.interfaces.base import Undefined
    >>> fname_presuffix(fname, 'pre', 'post', Undefined) == \
            fname_presuffix(fname, 'pre', 'post')
    True
    """
    pth, fname, ext = split_filename(fname)
    if not use_ext:
        ext = ""

    # No need for isdefined: bool(Undefined) evaluates to False
    if newpath:
        pth = op.abspath(newpath)
    return op.join(pth, prefix + fname + suffix + ext)


def hash_infile(afile, chunk_len=8192, crypto=hashlib.md5, raise_notfound=False):
    """Compute hash of a file using 'crypto' module.

    Examples
    --------
    >>> hash_infile('smri_ants_registration_settings.json')
    'f225785dfb0db9032aa5a0e4f2c730ad'

    >>> hash_infile('surf01.vtk')
    'fdf1cf359b4e346034372cdeb58f9a88'

    >>> hash_infile('spminfo')
    '0dc55e3888c98a182dab179b976dfffc'

    >>> hash_infile('fsl_motion_outliers_fd.txt')
    'defd1812c22405b1ee4431aac5bbdd73'
    """
    if not op.isfile(afile):
        if raise_notfound:
            raise RuntimeError(f'File "{afile}" not found.')
        return None

    crypto_obj = crypto()
    with open(afile, "rb") as fp:
        while True:
            data = fp.read(chunk_len)
            if not data:
                break
            crypto_obj.update(data)
    return crypto_obj.hexdigest()


def hash_timestamp(afile):
    """Compute md5 hash of the timestamp of a file."""
    md5hex = None
    if op.isfile(afile):
        md5obj = md5()
        stat = os.stat(afile)
        md5obj.update(str(stat.st_size).encode())
        md5obj.update(str(stat.st_mtime).encode())
        md5hex = md5obj.hexdigest()
    return md5hex


def _parse_mount_table(exit_code, output):
    """Parse the output of ``mount`` to produce ``(path, fs_type)`` pairs.

    Separated from _generate_cifs_table to enable testing logic with real outputs.
    """
    # Not POSIX
    if exit_code != 0:
        return []

    # Linux mount example:  sysfs on /sys type sysfs (rw,nosuid,nodev,noexec)
    #                          <PATH>^^^^      ^^^^^<FSTYPE>
    # OSX mount example:    /dev/disk2 on / (hfs, local, journaled)
    #                               <PATH>^  ^^^<FSTYPE>
    pattern = re.compile(r".*? on (/.*?) (?:type |\()([^\s,\)]+)")

    # Keep line and match for error reporting (match == None on failure)
    # Ignore empty lines
    matches = [(line, pattern.match(line)) for line in output.strip().splitlines() if line]

    # (path, fstype) tuples, sorted by path length (longest first)
    mount_info = sorted(
        (match.groups() for _, match in matches if match is not None),
        key=lambda x: len(x[0]),
        reverse=True,
    )
    cifs_paths = [path for path, fstype in mount_info if fstype.lower() == "cifs"]

    # Report failures as warnings
    for line, match in matches:
        if match is None:
            fmlogger.debug("Cannot parse mount line: '%s'", line)

    return [
        mount
        for mount in mount_info
        if any(mount[0].startswith(path) for path in cifs_paths)
    ]


def _generate_cifs_table():
    """Construct a reverse-length-ordered list of mount points that fall under a CIFS mount.

    This precomputation allows efficient checking for whether a given path
    would be on a CIFS filesystem.

    On systems without a ``mount`` command, or with no CIFS mounts, returns an empty list.

    Returns
    -------
    list
        A list of mount points under a CIFS mount.
    """
    exit_code, output = sp.getstatusoutput("mount")
    return _parse_mount_table(exit_code, output)


_cifs_table = _generate_cifs_table()


def on_cifs(fname):
    """Check whether a file path is on a CIFS filesystem mounted in a POSIX host.

    On Windows, Docker mounts host directories into containers through CIFS
    shares, which has support for Minshall+French symlinks, or text files that
    the CIFS driver exposes to the OS as symlinks.
    We have found that under concurrent access to the filesystem, this feature
    can result in failures to create or read recently-created symlinks,
    leading to inconsistent behavior and ``FileNotFoundError``.

    This check is written to support disabling symlinks on CIFS shares.

    Parameters
    ----------
    fname : str
        The file to be checked.

    Returns
    -------
    bool or str
        Either returns "cifs" if the file is on a CIFS filesystem or False if not.
    """
    # Only the first match (most recent parent) counts
    for fspath, fstype in _cifs_table:
        if fname.startswith(fspath):
            return fstype == "cifs"
    return False


def copyfile(
    originalfile,
    newfile,
    copy=False,
    create_new=False,
    hashmethod=None,
    use_hardlink=False,
    copy_related_files=True,
):
    """Copy or link ``originalfile`` to ``newfile``.

    If ``use_hardlink`` is True, and the file can be hard-linked, then a
    link is created, instead of copying the file.

    If a hard link is not created and ``copy`` is False, then a symbolic
    link is created.

    Parameters
    ----------
    originalfile : str
        full path to original file
    newfile : str
        full path to new file
    copy : bool
        specifies whether to copy or symlink files
        (default=False) but only for POSIX systems
    use_hardlink : bool
        specifies whether to hard-link files, when able
        (Default=False), taking precedence over copy
    copy_related_files : bool
        specifies whether to also operate on related files, as defined in
        ``related_filetype_sets``

    Returns
    -------
    newfile : str
        The full path to the new file.
    """
    newhash = None
    orighash = None
    fmlogger.debug(newfile)

    if create_new:
        while op.exists(newfile):
            base, fname, ext = split_filename(newfile)
            s = re.search(r"_c[0-9]{4,4}$", fname)
            i = 0
            if s:
                i = int(s.group()[2:]) + 1
                fname = fname[:-6] + f"_c{i:04d}"
            else:
                fname += f"_c{i:04d}"
            newfile = base + os.sep + fname + ext

    if hashmethod is None:
        hashmethod = config.get("execution", "hash_method").lower()

    # Don't try creating symlinks on CIFS
    if copy is False and on_cifs(newfile):
        copy = True

    # Existing file
    # -------------
    # Options:
    #   symlink
    #       to regular file originalfile            (keep if symlinking)
    #       to same dest as symlink originalfile    (keep if symlinking)
    #       to other file                           (unlink)
    #   regular file
    #       hard link to originalfile               (keep)
    #       copy of file (same hash)                (keep)
    #       different file (diff hash)              (unlink)
    keep = False
    if op.lexists(newfile):
        if op.islink(newfile):
            if all(
                (
                    os.readlink(newfile) == op.realpath(originalfile),
                    not use_hardlink,
                    not copy,
                )
            ):
                keep = True
        elif posixpath.samefile(newfile, originalfile):
            keep = True
        else:
            if hashmethod == "timestamp":
                hashfn = hash_timestamp
            elif hashmethod == "content":
                hashfn = hash_infile
            else:
                raise AttributeError("Unknown hash method found:", hashmethod)
            newhash = hashfn(newfile)
            fmlogger.debug(
                "File: %s already exists,%s, copy:%d", newfile, newhash, copy
            )
            orighash = hashfn(originalfile)
            keep = newhash == orighash
        if keep:
            fmlogger.debug(
                "File: %s already exists, not overwriting, copy:%d", newfile, copy
            )
        else:
            os.unlink(newfile)

    # New file
    # --------
    # use_hardlink & can_hardlink => hardlink
    # ~hardlink & ~copy & can_symlink => symlink
    # ~hardlink & ~symlink => copy
    if not keep and use_hardlink:
        try:
            fmlogger.debug("Linking File: %s->%s", newfile, originalfile)
            # Use realpath to avoid hardlinking symlinks
            os.link(op.realpath(originalfile), newfile)
        except OSError:
            use_hardlink = False  # Disable hardlink for associated files
        else:
            keep = True

    if not keep and not copy and os.name == "posix":
        try:
            fmlogger.debug("Symlinking File: %s->%s", newfile, originalfile)
            os.symlink(originalfile, newfile)
        except OSError:
            copy = True  # Disable symlink for associated files
        else:
            keep = True

    if not keep:
        try:
            fmlogger.debug("Copying File: %s->%s", newfile, originalfile)
            shutil.copyfile(originalfile, newfile)
        except shutil.Error as e:
            fmlogger.warning(str(e))

    # Associated files
    if copy_related_files:
        related_file_pairs = (
            get_related_files(f, include_this_file=False)
            for f in (originalfile, newfile)
        )
        for alt_ofile, alt_nfile in zip(*related_file_pairs):
            if op.exists(alt_ofile):
                copyfile(
                    alt_ofile,
                    alt_nfile,
                    copy,
                    hashmethod=hashmethod,
                    use_hardlink=use_hardlink,
                    copy_related_files=False,
                )

    return newfile


def get_related_files(filename, include_this_file=True):
    """Return a list of related files, as defined in ``related_filetype_sets``, for a filename.

    For example, Nifti-Pair, Analyze (SPM), and AFNI files.

    Parameters
    ----------
    filename : str
        File name to find related filetypes of.
    include_this_file : bool
        If true, output includes the input filename.

    Returns
    -------
    related_files : list of str
        List of file related to ``filename``.
    """
    related_files = []
    path, name, this_type = split_filename(filename)
    for type_set in related_filetype_sets:
        if this_type in type_set:
            for related_type in type_set:
                if include_this_file or related_type != this_type:
                    related_files.append(op.join(path, name + related_type))
    if not len(related_files):
        related_files = [filename]
    return related_files


def copyfiles(filelist, dest, copy=False, create_new=False):
    """Copy or symlink files in ``filelist`` to ``dest`` directory.

    Parameters
    ----------
    filelist : list of str
        List of files to copy.
    dest : str or list of str
        full path to destination. If it is a list of length greater
        than 1, then it assumes that these are the names of the new
        files.
    copy : Bool
        specifies whether to copy or symlink files
        (default=False) but only for posix systems

    Returns
    -------
    newfiles : list of str
        List of new copied files.
    """
    outfiles = ensure_list(dest)
    newfiles = []
    for i, f in enumerate(ensure_list(filelist)):
        if isinstance(f, list):
            newfiles.insert(i, copyfiles(f, dest, copy=copy, create_new=create_new))
        else:
            if len(outfiles) > 1:
                destfile = outfiles[i]
            else:
                destfile = fname_presuffix(f, newpath=outfiles[0])
            destfile = copyfile(f, destfile, copy, create_new=create_new)
            newfiles.insert(i, destfile)
    return newfiles


def ensure_list(filename):
    """Return a list given either a string or a list."""
    if isinstance(filename, (str, bytes)):
        return [filename]
    elif isinstance(filename, list):
        return filename
    elif is_container(filename):
        return [x for x in filename]
    else:
        return None


def simplify_list(filelist):
    """Return a list from a list of length greater than 1 or the first element if not.

    Parameters
    ----------
    filelist : list
        A list to simplify.

    Returns
    -------
    list or str
        A list of ``filelist`` is longer than 1. Otherwise the first element from the list.
    """
    if len(filelist) > 1:
        return filelist
    else:
        return filelist[0]


filename_to_list = ensure_list
list_to_filename = simplify_list


def loadpkl(infile):
    """Load a zipped or plain cPickled file."""
    infile = Path(infile)
    fmlogger.debug("Loading pkl: %s", infile)
    pklopen = gzip.open if infile.suffix == ".pklz" else open

    t = time()
    timeout = float(config.get("execution", "job_finished_timeout"))
    timed_out = True
    while (time() - t) < timeout:
        if infile.exists():
            timed_out = False
            break
        fmlogger.debug(f"'{infile}' missing; waiting 2s")
        sleep(2)
    if timed_out:
        error_message = (
            f"Result file {infile} expected, but "
            f"does not exist after ({timeout}) "
            "seconds."
        )
        raise IOError(error_message)

    with pklopen(str(infile), "rb") as pkl_file:
        pkl_contents = pkl_file.read()

    pkl_metadata = None

    # Look if pkl file contains version metadata
    idx = pkl_contents.find(b"\n")
    if idx >= 0:
        try:
            pkl_metadata = json.loads(pkl_contents[:idx])
        except (UnicodeDecodeError, json.JSONDecodeError):
            # Could not get version info
            pass
        else:
            # On success, skip JSON metadata
            pkl_contents = pkl_contents[idx + 1:]

    # Pickle files may contain relative paths that must be resolved relative
    # to the working directory, so use indirectory while attempting to load
    unpkl = None
    try:
        with indirectory(infile.parent):
            unpkl = pickle.loads(pkl_contents)
    except UnicodeDecodeError:
        # Was this pickle created with Python 2.x?
        with indirectory(infile.parent):
            unpkl = pickle.loads(pkl_contents, fix_imports=True, encoding="utf-8")
        fmlogger.info("Successfully loaded pkl in compatibility mode.")
    # Unpickling problems
    except Exception as e:
        if pkl_metadata and "version" in pkl_metadata:
            if pkl_metadata["version"] != version:
                fmlogger.error(
                    """\
Attempted to open a results file generated by Nipype version %s, \
with an incompatible Nipype version (%s)""",
                    pkl_metadata["version"],
                    version,
                )
                raise e
        fmlogger.warning(
            """\
No metadata was found in the pkl file. Make sure you are currently using \
the same Nipype version from the generated pkl."""
        )
        raise e

    if unpkl is None:
        raise ValueError(f"Loading {infile} resulted in None.")

    return unpkl


def which(cmd, env=None, pathext=None):
    """Return the path to an executable which would be run if the given cmd was called.

    If no cmd would be called, return ``None``.

    Code for Python < 3.3 is based on a code snippet from
    http://orip.org/2009/08/python-checking-if-executable-exists-in.html
    """
    if pathext is None:
        pathext = os.getenv("PATHEXT", "").split(os.pathsep)
        pathext.insert(0, "")

    path = os.getenv("PATH", os.defpath)
    if env and "PATH" in env:
        path = env.get("PATH")

    for ext in pathext:
        filename = shutil.which(cmd + ext, path=path)
        if filename:
            return filename
    return None


def relpath(path, start=None):
    """Return a relative version of a path.

    Parameters
    ----------
    path : str
        Path to reformat.
    start : None or str, optional
        The starting location for the relative path.
        If None, use the current working directory.
        Default is None.

    Returns
    -------
    str
        Relative version of the path.
    """
    try:
        return op.relpath(path, start)
    except AttributeError:
        pass

    if start is None:
        start = os.curdir
    if not path:
        raise ValueError("no path specified")
    start_list = op.abspath(start).split(op.sep)
    path_list = op.abspath(path).split(op.sep)
    if start_list[0].lower() != path_list[0].lower():
        unc_path, rest = op.splitunc(path)
        unc_start, rest = op.splitunc(start)
        if bool(unc_path) ^ bool(unc_start):
            raise ValueError(
                ("Cannot mix UNC and non-UNC paths " "(%s and %s)") % (path, start)
            )
        else:
            raise ValueError(
                f"path is on drive {path_list[0]}, start on drive {start_list[0]}"
            )
    # Work out how much of the filepath is shared by start and path.
    for i in range(min(len(start_list), len(path_list))):
        if start_list[i].lower() != path_list[i].lower():
            break
    else:
        i += 1

    rel_list = [op.pardir] * (len(start_list) - i) + path_list[i:]
    if not rel_list:
        return os.curdir
    return op.join(*rel_list)


@contextlib.contextmanager
def indirectory(path):
    """Change working directory to path."""
    cwd = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(cwd)


def find_and_copy_files(seek_dir, pattern, output_dir):
    """Find all files within the directory specified that match the glob-style pattern.

    Copies each file to the output directory.

    Parameters
    ----------
    seek_dir : str
        Directory to be searched.
    pattern : str
        Unix shell pattern for finding files.
    output_dir : str
        Directory to which to copy files.

    Returns
    -------
    rel_paths : list of str
        List of relative paths of copied files (may be empty).
    """
    rel_paths = []

    glob_pattern = os.path.join(seek_dir, pattern)
    for found_file in glob.glob(glob_pattern):
        # TODO: change name to BIDS name?
        filename = os.path.basename(found_file)
        rel_path = os.path.relpath(os.path.join(output_dir, filename),
                                   os.getcwd())
        shutil.copy(found_file, rel_path)
        rel_paths.append(rel_path)

    return rel_paths


def find_one_file(seek_dir, pattern):
    """Find a single file within seek_dir, using the pattern.

    Parameters
    ----------
    seek_dir : str
        Directory to be searched.
    pattern : str
        Unix shell pattern for finding files.

    Returns
    -------
    one_file : str
        Path to the found file.
    """
    one_file = None

    # Try to find a file with the pattern given in the directory given.
    glob_pattern = os.path.join(seek_dir, pattern)
    filelist = glob.glob(glob_pattern)

    # Make sure we got exactly one file.
    # numfiles = len(filelist)
    # if numfiles is 1:
    # one_file = filelist[0]
    # else:
    # TODO: Log info in errorfile.
    # print('info: Found %s files with pattern: %s' % (numfiles, glob_pattern))
    one_file = filelist[0]
    return one_file
