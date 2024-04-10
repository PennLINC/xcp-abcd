"""Quality control metrics."""

import h5py
import nibabel as nb
import numpy as np
import pandas as pd
from nipype import logging

from xcp_d.utils.doc import fill_doc

LOGGER = logging.getLogger("nipype.utils")


def compute_registration_qc(bold2t1w_mask, anat_brainmask, bold2template_mask, template_mask):
    """Compute quality of registration metrics.

    This function will calculate a series of metrics, including:

    - Dice's similarity index,
    - Pearson correlation coefficient, and
    - Coverage

    between the BOLD-to-T1w brain mask and the T1w mask,
    as well as between the BOLD-to-template brain mask and the template mask.

    Parameters
    ----------
    bold2t1w_mask : :obj:`str`
        Path to the BOLD mask in T1w space.
    anat_brainmask : :obj:`str`
        Path to the T1w mask.
    bold2template_mask : :obj:`str`
        Path to the BOLD mask in template space.
    template_mask : :obj:`str`
        Path to the template mask.

    Returns
    -------
    reg_qc : dict
        Quality control measures between different inputs.
    qc_metadata : dict
        Metadata describing the QC measures.
    """
    bold2t1w_mask_arr = nb.load(bold2t1w_mask).get_fdata()
    t1w_mask_arr = nb.load(anat_brainmask).get_fdata()
    bold2template_mask_arr = nb.load(bold2template_mask).get_fdata()
    template_mask_arr = nb.load(template_mask).get_fdata()

    reg_qc = {
        "coreg_dice": [dice(bold2t1w_mask_arr, t1w_mask_arr)],
        "coreg_correlation": [pearson(bold2t1w_mask_arr, t1w_mask_arr)],
        "coreg_overlap": [overlap(bold2t1w_mask_arr, t1w_mask_arr)],
        "norm_dice": [dice(bold2template_mask_arr, template_mask_arr)],
        "norm_correlation": [pearson(bold2template_mask_arr, template_mask_arr)],
        "norm_overlap": [overlap(bold2template_mask_arr, template_mask_arr)],
    }
    qc_metadata = {
        "coreg_dice": {
            "LongName": "Coregistration Sørensen-Dice Coefficient",
            "Description": (
                "The Sørensen-Dice coefficient calculated between the binary brain masks from the "
                "coregistered anatomical and functional images. "
                "Values are bounded between 0 and 1, "
                "with higher values indicating better coregistration."
            ),
            "Term URL": "https://en.wikipedia.org/wiki/S%C3%B8rensen%E2%80%93Dice_coefficient",
        },
        "coreg_correlation": {
            "LongName": "Coregistration Pearson Correlation",
            "Description": (
                "The Pearson correlation coefficient calculated between the binary brain masks "
                "from the coregistered anatomical and functional images. "
                "Values are bounded between 0 and 1, "
                "with higher values indicating better coregistration."
            ),
            "Term URL": "https://en.wikipedia.org/wiki/Pearson_correlation_coefficient",
        },
        "coreg_overlap": {
            "LongName": "Coregistration Coverage Metric",
            "Description": (
                "The Szymkiewicz-Simpson overlap coefficient calculated between the binary brain "
                "masks from the normalized functional image and the associated template. "
                "Higher values indicate better normalization."
            ),
            "Term URL": "https://en.wikipedia.org/wiki/Overlap_coefficient",
        },
        "norm_dice": {
            "LongName": "Normalization Sørensen-Dice Coefficient",
            "Description": (
                "The Sørensen-Dice coefficient calculated between the binary brain masks from the "
                "normalized functional image and the associated template. "
                "Values are bounded between 0 and 1, "
                "with higher values indicating better normalization."
            ),
            "Term URL": "https://en.wikipedia.org/wiki/S%C3%B8rensen%E2%80%93Dice_coefficient",
        },
        "norm_correlation": {
            "LongName": "Normalization Pearson Correlation",
            "Description": (
                "The Pearson correlation coefficient calculated between the binary brain masks "
                "from the normalized functional image and the associated template. "
                "Values are bounded between 0 and 1, "
                "with higher values indicating better normalization."
            ),
            "Term URL": "https://en.wikipedia.org/wiki/Pearson_correlation_coefficient",
        },
        "norm_overlap": {
            "LongName": "Normalization Overlap Coefficient",
            "Description": (
                "The Szymkiewicz-Simpson overlap coefficient calculated between the binary brain "
                "masks from the normalized functional image and the associated template. "
                "Higher values indicate better normalization."
            ),
            "Term URL": "https://en.wikipedia.org/wiki/Overlap_coefficient",
        },
    }
    return reg_qc, qc_metadata


def dice(input1, input2):
    r"""Calculate Dice coefficient between two arrays.

    Computes the Dice coefficient (also known as Sorensen index) between two binary images.

    The metric is defined as

    .. math::

        DC=\frac{2|A\cap B|}{|A|+|B|}

    , where :math:`A` is the first and :math:`B` the second set of samples (here: binary objects).
    This method was first proposed in :footcite:t:`dice1945measures` and
    :footcite:t:`sorensen1948method`.

    Parameters
    ----------
    input1/input2 : :obj:`numpy.ndarray`
        Numpy arrays to compare.
        Can be any type but will be converted into binary:
        False where 0, True everywhere else.

    Returns
    -------
    coef : :obj:`float`
        The Dice coefficient between ``input1`` and ``input2``.
        It ranges from 0 (no overlap) to 1 (perfect overlap).

    References
    ----------
    .. footbibliography::
    """
    input1 = np.atleast_1d(input1.astype(bool))
    input2 = np.atleast_1d(input2.astype(bool))

    intersection = np.count_nonzero(input1 & input2)

    size_i1 = np.count_nonzero(input1)
    size_i2 = np.count_nonzero(input2)

    if (size_i1 + size_i2) == 0:
        coef = 0
    else:
        coef = (2 * intersection) / (size_i1 + size_i2)

    return coef


def pearson(input1, input2):
    """Calculate Pearson product moment correlation between two images.

    Parameters
    ----------
    input1/input2 : :obj:`numpy.ndarray`
        Numpy arrays to compare.
        Can be any type but will be converted into binary:
        False where 0, True everywhere else.

    Returns
    -------
    coef : :obj:`float`
        Correlation between the two images.
    """
    input1 = np.atleast_1d(input1.astype(bool)).flatten()
    input2 = np.atleast_1d(input2.astype(bool)).flatten()

    return np.corrcoef(input1, input2)[0, 1]


def overlap(input1, input2):
    r"""Calculate overlap coefficient between two images.

    The metric is defined as

    .. math::

        DC=\frac{|A \cap B||}{min(|A|,|B|)}

    , where :math:`A` is the first and :math:`B` the second set of samples (here: binary objects).

    The overlap coefficient is also known as the Szymkiewicz-Simpson coefficient
    :footcite:p:`vijaymeena2016survey`.

    Parameters
    ----------
    input1/input2 : :obj:`numpy.ndarray`
        Numpy arrays to compare.
        Can be any type but will be converted into binary:
        False where 0, True everywhere else.

    Returns
    -------
    coef : :obj:`float`
        Coverage between two images.

    References
    ----------
    .. footbibliography::
    """
    input1 = np.atleast_1d(input1.astype(bool))
    input2 = np.atleast_1d(input2.astype(bool))

    intersection = np.count_nonzero(input1 & input2)
    smallv = np.minimum(np.sum(input1), np.sum(input2))

    return intersection / smallv


def compute_dvars(
    datat,
    intensity_normalization=1000,
    remove_zerovariance=True,
    variance_tol=1e-7,
):
    """Compute standard DVARS.

    Parameters
    ----------
    datat : :obj:`numpy.ndarray`
        The data matrix from which to calculate DVARS.
        Ordered as vertices by timepoints.

    Returns
    -------
    :obj:`numpy.ndarray`
        The calculated DVARS array.
        A (timepoints,) array.
    :obj:`numpy.ndarray`
        The calculated standardized DVARS array.
        A (timepoints,) array.
    """
    from nipype.algorithms.confounds import _AR_est_YW, regress_poly

    if intensity_normalization != 0:
        # Perform 1000 intensity normalization
        datat = (datat / np.median(datat)) * intensity_normalization

    # Robust standard deviation (we are using "lower" interpolation because this is what FSL does
    try:
        func_sd = (
            np.percentile(datat, 75, axis=1, method="lower")
            - np.percentile(datat, 25, axis=1, method="lower")
        ) / 1.349
    except TypeError:  # NP < 1.22
        func_sd = (
            np.percentile(datat, 75, axis=1, interpolation="lower")
            - np.percentile(datat, 25, axis=1, interpolation="lower")
        ) / 1.349

    if remove_zerovariance:
        zero_variance_voxels = func_sd > variance_tol
        datat = datat[zero_variance_voxels, :]
        func_sd = func_sd[zero_variance_voxels]

    # Compute (non-robust) estimate of lag-1 autocorrelation
    temp_data = regress_poly(0, datat, remove_mean=True)[0].astype(np.float32)
    if np.any(np.isnan(temp_data)):
        nan_idx = np.where(np.isnan(temp_data))[0]
        nan_datat = datat[nan_idx, :]
        raise ValueError(
            f"NaNs found in data after detrending in {nan_idx.size} voxels"
        )

    if np.any(np.isinf(temp_data)):
        raise ValueError("Infs found in data after detrending")

    ar1 = np.apply_along_axis(_AR_est_YW, 1, temp_data, 1)

    # Compute (predicted) standard deviation of temporal difference time series
    diff_sdhat = np.squeeze(np.sqrt(((1 - ar1) * 2).tolist())) * func_sd
    diff_sd_mean = diff_sdhat.mean()

    # Compute temporal difference time series
    func_diff = np.diff(datat, axis=1)

    # DVARS (no standardization)
    dvars_nstd = np.sqrt(np.square(func_diff).mean(axis=0))

    # standardization
    dvars_stdz = dvars_nstd / diff_sd_mean

    # Insert 0 at the beginning (fMRIPrep would add a NaN here)
    dvars_nstd = np.insert(dvars_nstd, 0, 0)
    dvars_stdz = np.insert(dvars_stdz, 0, 0)

    return dvars_nstd, dvars_stdz


def make_dcan_qc_file(filtered_motion, TR):
    """Make DCAN HDF5 file from single motion file.

    NOTE: This is a Node function.

    Parameters
    ----------
    filtered_motion_file : :obj:`str`
        File from which to extract information.
    TR : :obj:`float`
        Repetition time.

    Returns
    -------
    dcan_df_file : :obj:`str`
        Name of the HDF5-format file that is created.
    """
    import os

    from xcp_d.utils.qcmetrics import make_dcan_df

    dcan_df_file = os.path.abspath("desc-dcan_qc.hdf5")

    make_dcan_df(filtered_motion, dcan_df_file, TR)
    return dcan_df_file


@fill_doc
def make_dcan_df(filtered_motion, name, TR):
    """Create an HDF5-format file containing a DCAN-format dataset.

    Parameters
    ----------
    %(filtered_motion)s
    name : :obj:`str`
        Name of the HDF5-format file to be created.
    %(TR)s

    Notes
    -----
    The metrics in the file are:

    -   ``FD_threshold``: a number >= 0 that represents the FD threshold used to calculate
        the metrics in this list.
    -   ``frame_removal``: a binary vector/array the same length as the number of frames
        in the concatenated time series, indicates whether a frame is removed (1) or not (0)
    -   ``format_string`` (legacy): a string that denotes how the frames were excluded.
        This uses a notation devised by Avi Snyder.
    -   ``total_frame_count``: a whole number that represents the total number of frames
        in the concatenated series
    -   ``remaining_frame_count``: a whole number that represents the number of remaining
        frames in the concatenated series
    -   ``remaining_seconds``: a whole number that represents the amount of time remaining
        after thresholding
    -   ``remaining_frame_mean_FD``: a number >= 0 that represents the mean FD of the
        remaining frames
    """
    LOGGER.debug(f"Generating DCAN file: {name}")

    # Load filtered framewise_displacement values from file
    filtered_motion_df = pd.read_table(filtered_motion)
    fd = filtered_motion_df["framewise_displacement"].values

    with h5py.File(name, "w") as dcan:
        for thresh in np.linspace(0, 1, 101):
            thresh = np.around(thresh, 2)

            dcan.create_dataset(
                f"/dcan_motion/fd_{thresh}/skip",
                data=0,
                dtype="float",
            )
            dcan.create_dataset(
                f"/dcan_motion/fd_{thresh}/binary_mask",
                data=(fd > thresh).astype(int),
                dtype="float",
            )
            dcan.create_dataset(
                f"/dcan_motion/fd_{thresh}/threshold",
                data=thresh,
                dtype="float",
            )
            dcan.create_dataset(
                f"/dcan_motion/fd_{thresh}/total_frame_count",
                data=len(fd),
                dtype="float",
            )
            dcan.create_dataset(
                f"/dcan_motion/fd_{thresh}/remaining_total_frame_count",
                data=len(fd[fd <= thresh]),
                dtype="float",
            )
            dcan.create_dataset(
                f"/dcan_motion/fd_{thresh}/remaining_seconds",
                data=len(fd[fd <= thresh]) * TR,
                dtype="float",
            )
            dcan.create_dataset(
                f"/dcan_motion/fd_{thresh}/remaining_frame_mean_FD",
                data=(fd[fd <= thresh]).mean(),
                dtype="float",
            )
