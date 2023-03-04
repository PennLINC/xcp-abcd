#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Miscellaneous utility functions for xcp_d."""
import glob
import os
import tempfile
import warnings
from pathlib import Path

import numpy as np

from xcp_d.utils.doc import fill_doc


@fill_doc
def _t12native(fname):
    """Select T1w-to-scanner transform associated with a given BOLD file.

    TODO: Update names and refactor

    Parameters
    ----------
    fname : str
        The BOLD file from which to identify the transform.

    Returns
    -------
    %(t1w_to_native_xfm)s

    Notes
    -----
    Only used in get_segfile, which should be removed ASAP.
    """
    import os

    pth, fname = os.path.split(fname)
    file_prefix = fname.split("space-")[0]
    t1w_to_native_xfm = os.path.join(pth, f"{file_prefix}from-T1w_to-scanner_mode-image_xfm.txt")

    if not os.path.isfile(t1w_to_native_xfm):
        raise FileNotFoundError(f"File not found: {t1w_to_native_xfm}")

    return t1w_to_native_xfm


def get_segfile(bold_file):
    """Select the segmentation file associated with a given BOLD file.

    This function identifies the appropriate MNI-space discrete segmentation file for carpet
    plots, then applies the necessary transforms to warp the file into BOLD reference space.
    The warped segmentation file will be written to a temporary file and its path returned.

    Parameters
    ----------
    bold_file : str
        Path to the BOLD file.

    Returns
    -------
    segfile : str
        The associated segmentation file.

    Notes
    -----
    Only used in concatenation code and should be dropped in favor of BIDSLayout methods ASAP.
    """
    from templateflow.api import get as get_template

    from xcp_d.interfaces.ants import ApplyTransforms

    # get transform files
    dd = Path(os.path.dirname(bold_file))
    anatdir = str(dd.parent) + "/anat"

    if Path(anatdir).is_dir():
        mni_to_t1 = glob.glob(anatdir + "/*MNI152NLin2009cAsym_to-T1w_mode-image_xfm.h5")[0]
    else:
        anatdir = str(dd.parent.parent) + "/anat"
        mni_to_t1 = glob.glob(anatdir + "/*MNI152NLin2009cAsym_to-T1w_mode-image_xfm.h5")[0]

    transformfilex = get_std2bold_xforms(
        bold_file=bold_file,
        template_to_t1w_xfm=mni_to_t1,
        t1w_to_native_xfm=_t12native(bold_file),
    )

    boldref = bold_file.split("desc-preproc_bold.nii.gz")[0] + "boldref.nii.gz"

    segfile = tempfile.mkdtemp() + "segfile.nii.gz"
    carpet = str(
        get_template(
            "MNI152NLin2009cAsym",
            resolution=1,
            desc="carpet",
            suffix="dseg",
            extension=[".nii", ".nii.gz"],
        ),
    )

    # seg_data file to bold space
    at = ApplyTransforms()
    at.inputs.dimension = 3
    at.inputs.input_image = carpet
    at.inputs.reference_image = boldref
    at.inputs.output_image = segfile
    at.inputs.interpolation = "MultiLabel"
    at.inputs.transforms = transformfilex
    os.system(at.cmdline)

    return segfile


@fill_doc
def get_bold2std_and_t1w_xforms(bold_file, template_to_t1w_xfm, t1w_to_native_xfm):
    """Find transform files in reverse order to transform BOLD to MNI152NLin2009cAsym/T1w space.

    Since ANTSApplyTransforms takes in the transform files as a stack,
    these are applied in the reverse order of which they are specified.

    Parameters
    ----------
    bold_file : str
        The preprocessed BOLD file.
    %(template_to_t1w_xfm)s
        The ``from`` field is assumed to be the same space as the BOLD file is in.
        The MNI space could be MNI152NLin2009cAsym, MNI152NLin6Asym, or MNIInfant.
    %(t1w_to_native_xfm)s

    Returns
    -------
    xforms_to_MNI : list of str
        A list of paths to transform files for warping to MNI152NLin2009cAsym space.
    xforms_to_MNI_invert : list of bool
        A list of booleans indicating whether each transform in xforms_to_MNI indicating
        if each should be inverted (True) or not (False).
    xforms_to_T1w : list of str
        A list of paths to transform files for warping to T1w space.
    xforms_to_T1w_invert : list of bool
        A list of booleans indicating whether each transform in xforms_to_T1w indicating
        if each should be inverted (True) or not (False).

    Notes
    -----
    Only used for QCReport in init_boldpostprocess_wf.
    QCReport wants MNI-space data in MNI152NLin2009cAsym.
    """
    from pkg_resources import resource_filename as pkgrf
    from templateflow.api import get as get_template

    from xcp_d.utils.bids import get_entity

    # Extract the space of the BOLD file
    bold_space = get_entity(bold_file, "space")

    if bold_space in ("native", "T1w"):
        base_std_space = get_entity(template_to_t1w_xfm, "from")
    elif f"from-{bold_space}" not in template_to_t1w_xfm:
        raise ValueError(
            f"Transform does not match BOLD space: {bold_space} != {template_to_t1w_xfm}"
        )

    # Pull out the correct transforms based on bold_file name and string them together.
    xforms_to_T1w = [template_to_t1w_xfm]  # used for all spaces except T1w and native
    xforms_to_T1w_invert = [False]
    if bold_space == "MNI152NLin2009cAsym":
        # Data already in MNI152NLin2009cAsym space.
        xforms_to_MNI = ["identity"]
        xforms_to_MNI_invert = [False]

    elif bold_space == "MNI152NLin6Asym":
        # MNI152NLin6Asym --> MNI152NLin2009cAsym
        MNI152NLin6Asym_to_MNI152NLin2009cAsym = str(
            get_template(
                template="MNI152NLin2009cAsym",
                mode="image",
                suffix="xfm",
                extension=".h5",
                **{"from": "MNI152NLin6Asym"},
            ),
        )
        xforms_to_MNI = [MNI152NLin6Asym_to_MNI152NLin2009cAsym]
        xforms_to_MNI_invert = [False]

    elif bold_space == "MNIInfant":
        # MNIInfant --> MNI152NLin2009cAsym
        MNIInfant_to_MNI152NLin2009cAsym = pkgrf(
            "xcp_d",
            "data/transform/tpl-MNIInfant_from-MNI152NLin2009cAsym_mode-image_xfm.h5",
        )
        xforms_to_MNI = [MNIInfant_to_MNI152NLin2009cAsym]
        xforms_to_MNI_invert = [False]

    elif bold_space == "T1w":
        # T1w --> ?? (extract from template_to_t1w_xfm) --> MNI152NLin2009cAsym
        # Should not be reachable, since xcpd doesn't support T1w-space BOLD inputs
        if base_std_space != "MNI152NLin2009cAsym":
            std_to_mni_xform = str(
                get_template(
                    template="MNI152NLin2009cAsym",
                    mode="image",
                    suffix="xfm",
                    extension=".h5",
                    **{"from": base_std_space},
                ),
            )
            xforms_to_MNI = [std_to_mni_xform, template_to_t1w_xfm]
            xforms_to_MNI_invert = [False, True]
        else:
            xforms_to_MNI = [template_to_t1w_xfm]
            xforms_to_MNI_invert = [True]

        xforms_to_T1w = ["identity"]
        xforms_to_T1w_invert = [False]

    elif bold_space == "native":
        # native (BOLD) --> T1w --> ?? (extract from template_to_t1w_xfm) --> MNI152NLin2009cAsym
        # Should not be reachable, since xcpd doesn't support native-space BOLD inputs
        if base_std_space != "MNI152NLin2009cAsym":
            std_to_mni_xform = str(
                get_template(
                    template="MNI152NLin2009cAsym",
                    mode="image",
                    suffix="xfm",
                    extension=".h5",
                    **{"from": base_std_space},
                ),
            )
            xforms_to_MNI = [std_to_mni_xform, template_to_t1w_xfm, t1w_to_native_xfm]
            xforms_to_MNI_invert = [False, True, True]
        else:
            xforms_to_MNI = [template_to_t1w_xfm, t1w_to_native_xfm]
            xforms_to_MNI_invert = [True, True]

        xforms_to_T1w = [t1w_to_native_xfm]
        xforms_to_T1w_invert = [True]

    else:
        raise ValueError(f"Space '{bold_space}' in {bold_file} not supported.")

    return xforms_to_MNI, xforms_to_MNI_invert, xforms_to_T1w, xforms_to_T1w_invert


def get_std2bold_xforms(bold_file, template_to_t1w_xfm, t1w_to_native_xfm):
    """Obtain transforms to warp atlases from MNI152NLin6Asym to the same space as the BOLD.

    Since ANTSApplyTransforms takes in the transform files as a stack,
    these are applied in the reverse order of which they are specified.

    Parameters
    ----------
    bold_file : str
        The preprocessed BOLD file.
    %(template_to_t1w_xfm)s
        The ``from`` field is assumed to be the same space as the BOLD file is in.
    %(t1w_to_native_xfm)s

    Returns
    -------
    transform_list : list of str
        A list of paths to transform files.

    Notes
    -----
    Used by:

    - get_segfile (to be removed)
    - to resample dseg in init_boldpostprocess_wf for QCReport
    - to warp atlases to the same space as the BOLD data in init_nifti_functional_connectivity_wf
    - to resample dseg to BOLD space for the executive summary plots

    Does not include inversion flag output because there is no need (yet).
    Can easily be added in the future.
    """
    import os

    from pkg_resources import resource_filename as pkgrf
    from templateflow.api import get as get_template

    from xcp_d.utils.bids import get_entity

    # Extract the space of the BOLD file
    bold_space = get_entity(bold_file, "space")

    # Check that the MNI-to-T1w xform is from the right space
    if bold_space in ("native", "T1w"):
        base_std_space = get_entity(template_to_t1w_xfm, "from")
    elif f"from-{bold_space}" not in template_to_t1w_xfm:
        raise ValueError(
            f"Transform does not match BOLD space: {bold_space} != {template_to_t1w_xfm}"
        )

    # Load useful inter-template transforms from templateflow
    MNI152NLin6Asym_to_MNI152NLin2009cAsym = str(
        get_template(
            template="MNI152NLin2009cAsym",
            mode="image",
            suffix="xfm",
            extension=".h5",
            **{"from": "MNI152NLin6Asym"},
        ),
    )

    # Find the appropriate transform(s)
    if bold_space == "MNI152NLin6Asym":
        # NLin6 --> NLin6 (identity)
        transform_list = ["identity"]

    elif bold_space == "MNI152NLin2009cAsym":
        # NLin6 --> NLin2009c
        transform_list = [MNI152NLin6Asym_to_MNI152NLin2009cAsym]

    elif bold_space == "MNIInfant":
        # NLin6 --> NLin2009c --> MNIInfant
        MNI152NLin2009cAsym_to_MNI152Infant = pkgrf(
            "xcp_d",
            "data/transform/tpl-MNIInfant_from-MNI152NLin2009cAsym_mode-image_xfm.h5",
        )
        transform_list = [
            MNI152NLin2009cAsym_to_MNI152Infant,
            MNI152NLin6Asym_to_MNI152NLin2009cAsym,
        ]

    elif bold_space == "T1w":
        # NLin6 --> ?? (extract from template_to_t1w_xfm) --> T1w (BOLD)
        if base_std_space != "MNI152NLin6Asym":
            mni_to_std_xform = str(
                get_template(
                    template=base_std_space,
                    mode="image",
                    suffix="xfm",
                    extension=".h5",
                    **{"from": "MNI152NLin6Asym"},
                ),
            )
            transform_list = [template_to_t1w_xfm, mni_to_std_xform]
        else:
            transform_list = [template_to_t1w_xfm]

    elif bold_space == "native":
        # The BOLD data are in native space
        # NLin6 --> ?? (extract from template_to_t1w_xfm) --> T1w --> native (BOLD)
        if base_std_space != "MNI152NLin6Asym":
            mni_to_std_xform = str(
                get_template(
                    template=base_std_space,
                    mode="image",
                    suffix="xfm",
                    extension=".h5",
                    **{"from": "MNI152NLin6Asym"},
                ),
            )
            transform_list = [t1w_to_native_xfm, template_to_t1w_xfm, mni_to_std_xform]
        else:
            transform_list = [t1w_to_native_xfm, template_to_t1w_xfm]

    else:
        file_base = os.path.basename(bold_file)
        raise ValueError(f"Space '{bold_space}' in {file_base} not supported.")

    return transform_list


def fwhm2sigma(fwhm):
    """Convert full width at half maximum to sigma.

    Parameters
    ----------
    fwhm : float
        Full width at half maximum.

    Returns
    -------
    float
        Sigma.
    """
    return fwhm / np.sqrt(8 * np.log(2))


def butter_bandpass(
    data,
    sampling_rate,
    low_pass,
    high_pass,
    padtype="constant",
    padlen=None,
    order=2,
):
    """Apply a Butterworth bandpass filter to data.

    Parameters
    ----------
    data : (T, S) numpy.ndarray
        Time by voxels/vertices array of data.
    sampling_rate : float
        Sampling frequency. 1/TR(s).
    low_pass : float
        frequency, in Hertz
    high_pass : float
        frequency, in Hertz
    padlen
    padtype
    order : int
        The order of the filter.

    Returns
    -------
    filtered_data : (T, S) numpy.ndarray
        The filtered data.
    """
    from scipy.signal import butter, filtfilt

    b, a = butter(
        order,
        [high_pass, low_pass],
        btype="bandpass",
        output="ba",
        fs=sampling_rate,  # eliminates need to normalize cutoff frequencies
    )

    filtered_data = np.zeros_like(data)  # create something to populate filtered values with

    # apply the filter, loop through columns of regressors
    for i_voxel in range(filtered_data.shape[1]):
        filtered_data[:, i_voxel] = filtfilt(
            b,
            a,
            data[:, i_voxel],
            padtype=padtype,
            padlen=padlen,
        )

    return filtered_data


def estimate_brain_radius(mask_file, head_radius="auto"):
    """Estimate brain radius from binary brain mask file.

    Parameters
    ----------
    mask_file : str
        Binary brain mask file, in nifti format.
    head_radius : float or "auto", optional
        Head radius to use. Either a number, in millimeters, or "auto".
        If set to "auto", the brain radius will be estimated from the mask file.
        Default is "auto".

    Returns
    -------
    brain_radius : float
        Estimated brain radius, in millimeters.

    Notes
    -----
    This function estimates the brain radius based on the brain volume,
    assuming that the brain is a sphere.
    This was Paul Taylor's idea, shared in this NeuroStars post:
    https://neurostars.org/t/estimating-head-brain-radius-automatically/24290/2.
    """
    import nibabel as nb
    import numpy as np
    from nipype import logging

    LOGGER = logging.getLogger("nipype.utils")

    if head_radius == "auto":
        mask_img = nb.load(mask_file)
        mask_data = mask_img.get_fdata()
        n_voxels = np.sum(mask_data)
        voxel_size = np.prod(mask_img.header.get_zooms())
        volume = n_voxels * voxel_size

        brain_radius = ((3 * volume) / (4 * np.pi)) ** (1 / 3)

        LOGGER.info(f"Brain radius estimated at {brain_radius} mm.")

    else:
        brain_radius = head_radius

    return brain_radius


def denoise_with_nilearn(
    preprocessed_bold,
    confounds_file,
    temporal_mask,
    lowpass,
    highpass,
    filter_order,
    TR,
):
    """Denoise an array with Nilearn.

    This step does the following:

        1. Orthogonalize nuisance regressors w.r.t. any signal regressors.
        2. Censor the data and associated confounds.
        3. Mean-center the censored and uncensored confounds, based on the censored confounds.
        4. Estimate betas using only the censored data.
        5. Apply the betas to denoise the *full* (uncensored) BOLD data.
        6. Apply the betas to denoise the censored BOLD data.
        7. Interpolate the censored, denoised data.
        8. Bandpass filter the interpolated, denoised data.

    Parameters
    ----------
    preprocessed_bold : :obj:`numpy.ndarray` of shape (T, S)
        Preprocessed BOLD data, after dummy volume removal,
        but without any additional censoring.
    confounds_file : str
        Path to TSV file containing selected confounds, after dummy volume removal,
        but without any additional censoring.
    temporal_mask : str
        Path to TSV file containing one column with zeros for low-motion volumes and
        ones for high-motion outliers.
    lowpass, highpass : float or None
        Lowpass and highpass thresholds, in Hertz.
    filter_order : int
        Filter order.
    TR : float
        Repetition time, in seconds.

    Returns
    -------
    uncensored_denoised_bold : :obj:`numpy.ndarray` of shape (T, S)
        The result of denoising the full (uncensored) preprocessed BOLD data using
        betas estimated using the *censored* BOLD data and nuisance regressors.
        This is only used for DCAN figures.
    interpolated_denoised_bold : :obj:`numpy.ndarray` of shape (T, S)
        The result of denoising the censored preprocessed BOLD data,
        followed by cubic spline interpolation.
    interpolated_filtered_bold : :obj:`numpy.ndarray` of shape (T, S)
        The result of denoising the censored preprocessed BOLD data,
        followed by cubic spline interpolation and band-pass filtering.
        This is the primary output.
    """
    import pandas as pd
    from nilearn import signal

    n_volumes, n_voxels = preprocessed_bold.shape
    confounds_df = pd.read_table(confounds_file)

    assert "intercept" in confounds_df.columns
    assert "linear_trend" in confounds_df.columns
    assert confounds_df.columns[-1] == "intercept"

    censoring_df = pd.read_table(temporal_mask)
    sample_mask = ~censoring_df["framewise_displacement"].to_numpy().astype(bool)

    # Orthogonalize full nuisance regressors w.r.t. any signal regressors
    signal_columns = [c for c in confounds_df.columns if c.startswith("signal__")]
    if signal_columns:
        warnings.warn(
            "Signal columns detected. "
            "Orthogonalizing nuisance columns w.r.t. the following signal columns: "
            f"{', '.join(signal_columns)}"
        )
        noise_columns = [c for c in confounds_df.columns if not c.startswith("signal__")]
        # Don't orthogonalize the intercept or linear trend regressors
        columns_to_denoise = [c for c in noise_columns if c not in ["linear_trend", "intercept"]]
        temp_confounds_df = confounds_df[noise_columns].copy()

        signal_regressors = confounds_df[signal_columns].to_numpy()
        noise_regressors = confounds_df[columns_to_denoise].to_numpy()
        signal_betas = np.linalg.lstsq(signal_regressors, noise_regressors, rcond=None)[0]
        pred_noise_regressors = np.dot(signal_regressors, signal_betas)
        orth_noise_regressors = noise_regressors - pred_noise_regressors
        temp_confounds_df.loc[:, columns_to_denoise] = orth_noise_regressors
        confounds_df = temp_confounds_df

    # Censor the data and confounds
    preprocessed_bold_censored = preprocessed_bold[sample_mask, :]
    nuisance_arr = confounds_df.to_numpy()
    nuisance_censored = nuisance_arr[sample_mask, :]

    # Mean-center all of the confounds, except the intercept, to be safe
    nuisance_censored_mean = np.mean(nuisance_censored[:, :-1], axis=0)
    nuisance_arr[:, :-1] -= nuisance_censored_mean
    nuisance_censored[:, :-1] -= nuisance_censored_mean  # use censored mean on full regressors

    # Estimate betas using only the censored data
    betas = np.linalg.lstsq(nuisance_censored, preprocessed_bold_censored, rcond=None)[0]

    # Apply the betas to denoise the *full* (uncensored) BOLD data
    uncensored_denoised_bold = preprocessed_bold - np.dot(nuisance_arr, betas)

    # Also denoise the censored BOLD data
    censored_denoised_bold = preprocessed_bold_censored - np.dot(nuisance_censored, betas)

    # Now interpolate the censored, denoised data with cubic spline interpolation
    interpolated_denoised_bold = np.zeros(
        (n_volumes, n_voxels),
        dtype=censored_denoised_bold.dtype,
    )
    interpolated_denoised_bold[sample_mask, :] = censored_denoised_bold
    interpolated_denoised_bold = signal._interpolate_volumes(
        interpolated_denoised_bold,
        sample_mask=sample_mask,
        t_r=TR,
    )

    # Now apply the bandpass filter to the interpolated, denoised data
    if lowpass is not None and highpass is not None:
        # TODO: Replace with nilearn.signal.butterworth once 0.10.1 is released.
        interpolated_filtered_bold = butter_bandpass(
            interpolated_denoised_bold.copy(),
            sampling_rate=1 / TR,
            low_pass=lowpass,
            high_pass=highpass,
            order=filter_order / 2,
            padtype="constant",
            padlen=n_volumes - 1,
        )
    else:
        interpolated_filtered_bold = interpolated_denoised_bold

    return uncensored_denoised_bold, interpolated_denoised_bold, interpolated_filtered_bold


def _select_first(lst):
    """Select the first element in a list."""
    return lst[0]
