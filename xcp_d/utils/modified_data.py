# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Functions for interpolating over high-motion volumes."""

import os

import nibabel as nb
import numpy as np
import pandas as pd
from nipype import logging

from xcp_d.utils.confounds import _infer_dummy_scans, _modify_motion_filter, load_motion
from xcp_d.utils.doc import fill_doc
from xcp_d.utils.filemanip import fname_presuffix

LOGGER = logging.getLogger('nipype.utils')


@fill_doc
def compute_fd(confound, head_radius=50, filtered=False):
    """Compute framewise displacement.

    NOTE: TS- Which kind of FD? Power?
    NOTE: TS- What units must rotation parameters be in?

    Parameters
    ----------
    confound : pandas.DataFrame
        DataFrame with six motion parameters.
    %(head_radius)s

    Returns
    -------
    fdres : numpy.ndarray
        The framewise displacement time series.
    """
    confound = confound.replace(np.nan, 0)
    motion_columns = ['trans_x', 'trans_y', 'trans_z', 'rot_x', 'rot_y', 'rot_z']
    if filtered:
        motion_columns = [f'{col}_filtered' for col in motion_columns]

    mpars = confound[motion_columns].to_numpy()
    diff = mpars[:-1, :6] - mpars[1:, :6]
    diff[:, 3:6] *= head_radius
    fd_res = np.abs(diff).sum(axis=1)
    fdres = np.hstack([0, fd_res])

    return fdres


def _drop_dummy_scans(bold_file, dummy_scans):
    """Remove the first X volumes from a BOLD file.

    Parameters
    ----------
    bold_file : :obj:`str`
        Path to a nifti or cifti file.
    dummy_scans : :obj:`int`
        If an integer, the first ``dummy_scans`` volumes will be removed.

    Returns
    -------
    dropped_image : img_like
        The BOLD image, with the first X volumes removed.
    """
    # read the bold file
    bold_image = nb.load(bold_file)

    data = bold_image.get_fdata()

    if bold_image.ndim == 2:  # cifti
        dropped_data = data[dummy_scans:, ...]  # time series is the first element
        time_axis, brain_model_axis = (
            bold_image.header.get_axis(i) for i in range(bold_image.ndim)
        )
        new_total_volumes = dropped_data.shape[0]
        dropped_time_axis = time_axis[:new_total_volumes]
        dropped_header = nb.cifti2.Cifti2Header.from_axes((dropped_time_axis, brain_model_axis))
        dropped_image = nb.Cifti2Image(
            dropped_data, header=dropped_header, nifti_header=bold_image.nifti_header
        )

    else:  # nifti
        dropped_data = data[..., dummy_scans:]
        dropped_image = nb.Nifti1Image(
            dropped_data, affine=bold_image.affine, header=bold_image.header
        )

    return dropped_image


def downcast_to_32(in_file):
    """Downcast a file from >32-bit to 32-bit if necessary.

    Parameters
    ----------
    in_file : None or str
        Path to a file to downcast.
        If None, None will be returned.
        If the file is lower-precision than 32-bit,
        then it will be returned without modification.

    Returns
    -------
    None or str
        Path to the downcast file.
        If in_file is None, None will be returned.
        If in_file is a file with lower than 32-bit precision,
        then it will be returned without modification.
        Otherwise, a new path will be returned.
    """
    if in_file is None:
        return in_file

    elif not os.path.isfile(in_file):
        raise FileNotFoundError(f'File not found: {in_file}')

    img = nb.load(in_file)
    if hasattr(img, 'nifti_header'):
        header = img.nifti_header
    else:
        header = img.header

    SIZE32 = 4  # number of bytes in float32/int32
    dtype = header.get_data_dtype()
    if dtype.itemsize > SIZE32:
        LOGGER.warning(f'Downcasting {in_file} to 32-bit.')
        if np.issubdtype(dtype, np.integer):
            header.set_data_dtype(np.int32)
        elif np.issubdtype(dtype, np.floating):
            header.set_data_dtype(np.float32)
        else:
            raise TypeError(f"Unknown datatype '{dtype}'.")

        out_file = fname_presuffix(in_file, newpath=os.getcwd(), suffix='_downcast', use_ext=True)
        img.to_filename(out_file)
    else:
        out_file = in_file

    return out_file


@fill_doc
def flag_bad_run(
    motion_file,
    dummy_scans,
    TR,
    motion_filter_type,
    motion_filter_order,
    band_stop_min,
    band_stop_max,
    head_radius,
    fd_thresh,
):
    """Determine if a run has too many high-motion volumes to continue processing.

    Parameters
    ----------
    motion_file
        Tabular confounds file containing motion parameters.
    %(dummy_scans)s
    %(TR)s
    %(motion_filter_type)s
    %(motion_filter_order)s
    %(band_stop_min)s
    %(band_stop_max)s
    %(head_radius)s
    %(fd_thresh)s
    brain_mask

    Returns
    -------
    post_scrubbing_duration : :obj:`float`
        Amount of time remaining in the run after dummy scan removal, in seconds.
    """
    dummy_scans = _infer_dummy_scans(
        dummy_scans=dummy_scans,
        confounds_file=motion_file,
    )

    # Read in fmriprep confounds tsv to calculate FD
    fmriprep_confounds_df = pd.read_table(motion_file)

    # Remove dummy volumes
    fmriprep_confounds_df = fmriprep_confounds_df.drop(np.arange(dummy_scans))

    retained_sec = np.inf
    if fd_thresh > 0:
        # Calculate filtered FD
        band_stop_min_adjusted, band_stop_max_adjusted, _ = _modify_motion_filter(
            motion_filter_type=motion_filter_type,
            band_stop_min=band_stop_min,
            band_stop_max=band_stop_max,
            TR=TR,
        )
        motion_df = load_motion(
            fmriprep_confounds_df,
            TR=TR,
            motion_filter_type=motion_filter_type,
            motion_filter_order=motion_filter_order,
            band_stop_min=band_stop_min_adjusted,
            band_stop_max=band_stop_max_adjusted,
        )
        fd_arr = compute_fd(
            confound=motion_df,
            head_radius=head_radius,
            filtered=bool(motion_filter_type),
        )
        retained_sec = np.sum(fd_arr <= fd_thresh) * TR

    return retained_sec


def calculate_dof(n_volumes, t_r, high_pass=0, low_pass=np.inf):
    """Calculate the number of degrees of freedom lost by a temporal filter.

    Parameters
    ----------
    n_volumes : int
        Number of data points in the time series.
    t_r : float
        Repetition time of the time series, in seconds.
    high_pass : float
        High-pass frequency in Hertz. Default is 0 (no high-pass filter).
    low_pass : float or numpy.inf
        Low-pass frequency in Hertz. Default is np.inf (no low-pass filter).

    Returns
    -------
    dof_lost : int
        Number of degrees of freedom lost by applying the filter.

    Notes
    -----
    Both Caballero-Gaudes & Reynolds (2017) and Reynolds et al. (preprint)
    say that each frequency removed drops two degrees of freedom.
    """
    import numpy as np

    duration = t_r * n_volumes
    fs = 1 / t_r
    nyq = 0.5 * fs
    spacing = 1 / duration
    n_freqs = int(np.ceil(nyq / spacing))
    frequencies_hz = np.linspace(0, nyq, n_freqs)

    # Figure out what the change in DOF is from the bandpass filter
    dropped_freqs_idx = np.where((frequencies_hz < high_pass) | (frequencies_hz > low_pass))[0]
    n_dropped_freqs = dropped_freqs_idx.size

    # Calculate the lost degrees of freedom
    dof_lost = n_dropped_freqs * 2
    return dof_lost


def calculate_exact_scans(exact_times, scan_length, t_r, bold_file):
    """Calculate the exact scans corresponding to exact times.

    Parameters
    ----------
    exact_times : :obj:`list`
        List of exact times in seconds.
    scan_length : :obj:`int`
        Length of the scan in seconds.
    t_r : :obj:`float`
        Repetition time of the scan in seconds.
    bold_file : :obj:`str`
        Path to the BOLD file.

    Returns
    -------
    exact_scans : :obj:`list`
        List of exact scans corresponding to the exact times.
    """
    float_times = []
    non_float_times = []

    exact_times = [time for time in exact_times if time != 'all']
    for time in exact_times:
        try:
            float_times.append(float(time))
        except ValueError:
            non_float_times.append(time)

    retained_exact_times = [t for t in float_times if t <= scan_length]
    dropped_exact_times = [t for t in float_times if t > scan_length]
    if dropped_exact_times:
        LOGGER.warning(
            f'{scan_length} seconds in {os.path.basename(bold_file)} '
            'survive high-motion outlier scrubbing. '
            'Only retaining exact-time values greater than this '
            f'({retained_exact_times}).'
        )

    if non_float_times:
        LOGGER.warning(
            f'Non-float values {non_float_times} in {os.path.basename(bold_file)} will be ignored.'
        )

    exact_scans = [int(t // t_r) for t in retained_exact_times]
    return exact_scans
