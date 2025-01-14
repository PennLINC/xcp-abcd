"""Utility functions for tests."""

import os
import subprocess
import tarfile
from contextlib import contextmanager
from glob import glob
from gzip import GzipFile
from io import BytesIO

import nibabel as nb
import numpy as np
import requests
from bids.layout import BIDSLayout
from nipype import logging

LOGGER = logging.getLogger('nipype.utils')


def _check_arg_specified(argname, arglist):
    for arg in arglist:
        if arg.startswith(argname):
            return True
    return False


def get_cpu_count(max_cpus=4):
    """Figure out how many cpus are available in the test environment."""
    env_cpus = os.getenv('CIRCLE_CPUS')
    if env_cpus:
        return int(env_cpus)
    return max_cpus


def update_resources(parameters):
    """We should use all the available CPUs for testing.

    Sometimes a test will set a specific amount of cpus. In that
    case, the number should be kept. Otherwise, try to read the
    env variable (specified in each job in config.yml). If
    this variable doesn't work, just set it to 4.
    """
    nthreads = get_cpu_count()
    if not _check_arg_specified('--nthreads', parameters):
        parameters.append(f'--nthreads={nthreads}')
    if not _check_arg_specified('--omp-nthreads', parameters):
        parameters.append(f'--omp-nthreads={nthreads}')
    return parameters


def get_nodes(wf_results):
    """Load nodes from a Nipype workflow's results."""
    return {node.fullname: node for node in wf_results.nodes}


def download_test_data(dset, data_dir=None):
    """Download test data."""
    URLS = {
        'fmriprepwithoutfreesurfer': (
            'https://upenn.box.com/shared/static/seyp1cu9w5v3ds6iink37hlsa217yge1.tar.gz'
        ),
        'nibabies': 'https://upenn.box.com/shared/static/rsd7vpny5imv3qkd7kpuvdy9scpnfpe2.tar.gz',
        'ds001419': 'https://upenn.box.com/shared/static/yye7ljcdodj9gd6hm2r6yzach1o6xq1d.tar.gz',
        'ds001419-aroma': (
            'https://upenn.box.com/shared/static/dexcmnlj7yujudr3muu05kch66sko4mt.tar.gz'
        ),
        'pnc': 'https://upenn.box.com/shared/static/ui2847ys49d82pgn5ewai1mowcmsv2br.tar.gz',
        'ukbiobank': 'https://upenn.box.com/shared/static/p5h1eg4p5cd2ef9ehhljlyh1uku0xe97.tar.gz',
        'schaefer100': (
            'https://upenn.box.com/shared/static/b9pn9qebr41kteant4ym2q5u4kcbgiy6.tar.gz'
        ),
    }
    if dset == '*':
        for k in URLS:
            download_test_data(k, data_dir=data_dir)

        return

    if dset not in URLS:
        raise ValueError(f'dset ({dset}) must be one of: {", ".join(URLS.keys())}')

    if not data_dir:
        data_dir = os.path.join(os.path.dirname(get_test_data_path()), 'test_data')

    out_dir = os.path.join(data_dir, dset)

    if os.path.isdir(out_dir):
        LOGGER.info(
            f'Dataset {dset} already exists. '
            'If you need to re-download the data, please delete the folder.'
        )
        if dset.startswith('ds001419'):
            # These test datasets have an extra folder level
            out_dir = os.path.join(out_dir, dset)

        return out_dir
    else:
        LOGGER.info(f'Downloading {dset} to {out_dir}')

    os.makedirs(out_dir, exist_ok=True)
    with requests.get(URLS[dset], stream=True, timeout=10) as req:
        with tarfile.open(fileobj=GzipFile(fileobj=BytesIO(req.content))) as t:
            t.extractall(out_dir)  # noqa: S202

    if dset.startswith('ds001419'):
        # These test datasets have an extra folder level
        out_dir = os.path.join(out_dir, dset)

    return out_dir


def get_test_data_path():
    """Return the path to test datasets, terminated with separator.

    Test-related data are kept in tests folder in "data".
    Based on function by Yaroslav Halchenko used in Neurosynth Python package.
    """
    return os.path.abspath(os.path.join(os.path.dirname(__file__), 'data') + os.path.sep)


def check_generated_files(output_dir, output_list_file):
    """Compare files generated by xcp_d with a list of expected files."""
    found_files = sorted(glob(os.path.join(output_dir, '**/*'), recursive=True))
    found_files = [os.path.relpath(f, output_dir) for f in found_files]

    # Ignore figures
    found_files = [f for f in found_files if 'figures' not in f]

    # Ignore logs
    found_files = [f for f in found_files if 'log' not in f.split(os.path.sep)]

    with open(output_list_file) as fo:
        expected_files = fo.readlines()
        expected_files = [f.rstrip() for f in expected_files]

    if sorted(found_files) != sorted(expected_files):
        expected_not_found = sorted(set(expected_files) - set(found_files))
        found_not_expected = sorted(set(found_files) - set(expected_files))

        msg = ''
        if expected_not_found:
            msg += '\nExpected but not found:\n\t'
            msg += '\n\t'.join(expected_not_found)

        if found_not_expected:
            msg += '\nFound but not expected:\n\t'
            msg += '\n\t'.join(found_not_expected)
        raise ValueError(msg)


def check_affines(data_dir, out_dir, input_type):
    """Confirm affines don't change across XCP-D runs."""
    preproc_layout = BIDSLayout(str(data_dir), validate=False)
    xcp_layout = BIDSLayout(str(out_dir), validate=False)
    if input_type == 'cifti':  # Get the .dtseries.nii
        denoised_files = xcp_layout.get(
            invalid_filters='allow',
            datatype='func',
            extension='.dtseries.nii',
        )
        space = denoised_files[0].get_entities()['space']
        preproc_files = preproc_layout.get(
            invalid_filters='allow',
            datatype='func',
            space=space,
            extension='.dtseries.nii',
        )

    elif input_type in ('nifti', 'ukb'):  # Get the .nii.gz
        # Problem: it's collecting native-space data
        denoised_files = xcp_layout.get(
            datatype='func',
            suffix='bold',
            extension='.nii.gz',
        )
        space = denoised_files[0].get_entities()['space']
        preproc_files = preproc_layout.get(
            invalid_filters='allow',
            datatype='func',
            space=space,
            suffix='bold',
            extension='.nii.gz',
        )

    else:  # Nibabies
        denoised_files = xcp_layout.get(
            datatype='func',
            space='MNIInfant',
            suffix='bold',
            extension='.nii.gz',
        )
        preproc_files = preproc_layout.get(
            invalid_filters='allow',
            datatype='func',
            space='MNIInfant',
            suffix='bold',
            extension='.nii.gz',
        )

    preproc_file = preproc_files[0].path
    denoised_file = denoised_files[0].path
    img1 = nb.load(preproc_file)
    img2 = nb.load(denoised_file)

    if input_type == 'cifti':
        assert img1._nifti_header.get_intent() == img2._nifti_header.get_intent()
        np.testing.assert_array_equal(img1.nifti_header.get_zooms(), img2.nifti_header.get_zooms())
    else:
        np.testing.assert_array_equal(img1.affine, img2.affine)
        if input_type != 'ukb':
            # The UK Biobank test dataset has the wrong TR in the header.
            # I'll fix it at some point, but it's not the software's fault.
            np.testing.assert_array_equal(img1.header.get_zooms(), img2.header.get_zooms())


def run_command(command, env=None):
    """Run a given shell command with certain environment variables set.

    Keep this out of the real XCP-D code so that devs don't need to install XCP-D to run tests.
    """
    merged_env = os.environ
    if env:
        merged_env.update(env)

    process = subprocess.Popen(
        command.split(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
        env=merged_env,
    )
    while True:
        line = process.stdout.readline()
        line = str(line, 'utf-8')[:-1]
        print(line)
        if line == '' and process.poll() is not None:
            break

    if process.returncode != 0:
        raise RuntimeError(
            f'Non zero return code: {process.returncode}\n{command}\n\n{process.stdout.read()}'
        )


@contextmanager
def chdir(path):
    """Temporarily change directories.

    Taken from https://stackoverflow.com/a/37996581/2589328.
    """
    oldpwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(oldpwd)


def reorder_expected_outputs():
    """Load each of the expected output files and sort the lines alphabetically.

    This function is called manually by devs when they modify the test outputs.
    """
    test_data_path = get_test_data_path()
    expected_output_files = sorted(glob(os.path.join(test_data_path, 'test_*_outputs.txt')))
    for expected_output_file in expected_output_files:
        LOGGER.info(f'Sorting {expected_output_file}')

        with open(expected_output_file) as fo:
            file_contents = fo.readlines()

        file_contents = sorted(set(file_contents))

        with open(expected_output_file, 'w') as fo:
            fo.writelines(file_contents)


def list_files(startpath):
    """List files in a directory."""
    tree = ''
    for root, _, files in os.walk(startpath):
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * (level)
        tree += f'{indent}{os.path.basename(root)}/\n'
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            tree += f'{subindent}{f}\n'

    return tree


@contextmanager
def modified_environ(*remove, **update):
    """
    Temporarily updates the ``os.environ`` dictionary in-place.

    The ``os.environ`` dictionary is updated in-place so that the modification
    is sure to work in all situations.

    :param remove: Environment variables to remove.
    :param update: Dictionary of environment variables and values to add/update.
    """
    env = os.environ
    update = update or {}
    remove = remove or []

    # List of environment variables being updated or removed.
    stomped = (set(update.keys()) | set(remove)) & set(env.keys())
    # Environment variables and values to restore on exit.
    update_after = {k: env[k] for k in stomped}
    # Environment variables and values to remove on exit.
    remove_after = frozenset(k for k in update if k not in env)

    try:
        env.update(update)
        [env.pop(k, None) for k in remove]
        yield
    finally:
        env.update(update_after)
        [env.pop(k) for k in remove_after]
