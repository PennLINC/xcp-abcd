"""Miscellaneous utility functions for xcp_d."""

import nibabel as nb
import numpy as np
from nipype import logging

from xcp_d.utils.doc import fill_doc

LOGGER = logging.getLogger("nipype.utils")


def get_bold2std_and_t1w_xfms(bold_file, template_to_anat_xfm):
    """Find transform files in reverse order to transform BOLD to MNI152NLin2009cAsym/T1w space.

    Since ANTSApplyTransforms takes in the transform files as a stack,
    these are applied in the reverse order of which they are specified.

    NOTE: This is a Node function.

    Parameters
    ----------
    bold_file : :obj:`str`
        The preprocessed BOLD file.
    template_to_anat_xfm
        The ``from`` field is assumed to be the same space as the BOLD file is in.
        The MNI space could be MNI152NLin2009cAsym, MNI152NLin6Asym, or MNIInfant.

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
    Only used for QCReport in init_postprocess_nifti_wf.
    QCReport wants MNI-space data in MNI152NLin2009cAsym.
    """
    from pkg_resources import resource_filename as pkgrf
    from templateflow.api import get as get_template

    from xcp_d.utils.bids import get_entity

    # Extract the space of the BOLD file
    bold_space = get_entity(bold_file, "space")

    if bold_space in ("native", "T1w"):
        base_std_space = get_entity(template_to_anat_xfm, "from")
        raise ValueError(f"BOLD space '{bold_space}' not supported.")
    elif f"from-{bold_space}" not in template_to_anat_xfm:
        raise ValueError(
            f"Transform does not match BOLD space: {bold_space} != {template_to_anat_xfm}"
        )

    # Pull out the correct transforms based on bold_file name and string them together.
    xforms_to_T1w = [template_to_anat_xfm]  # used for all spaces except T1w and native
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
        # T1w --> ?? (extract from template_to_anat_xfm) --> MNI152NLin2009cAsym
        # Should not be reachable, since xcpd doesn't support T1w-space BOLD inputs
        if base_std_space != "MNI152NLin2009cAsym":
            std_to_mni_xfm = str(
                get_template(
                    template="MNI152NLin2009cAsym",
                    mode="image",
                    suffix="xfm",
                    extension=".h5",
                    **{"from": base_std_space},
                ),
            )
            xforms_to_MNI = [std_to_mni_xfm, template_to_anat_xfm]
            xforms_to_MNI_invert = [False, True]
        else:
            xforms_to_MNI = [template_to_anat_xfm]
            xforms_to_MNI_invert = [True]

        xforms_to_T1w = ["identity"]
        xforms_to_T1w_invert = [False]

    else:
        raise ValueError(f"Space '{bold_space}' in {bold_file} not supported.")

    return xforms_to_MNI, xforms_to_MNI_invert, xforms_to_T1w, xforms_to_T1w_invert


def get_std2bold_xfms(bold_file):
    """Obtain transforms to warp atlases from MNI152NLin6Asym to the same template as the BOLD.

    Since ANTSApplyTransforms takes in the transform files as a stack,
    these are applied in the reverse order of which they are specified.

    NOTE: This is a Node function.

    Parameters
    ----------
    bold_file : :obj:`str`
        The preprocessed BOLD file.

    Returns
    -------
    transform_list : list of str
        A list of paths to transform files.

    Notes
    -----
    Used by:

    - to resample dseg in init_postprocess_nifti_wf for QCReport
    - to warp atlases to the same space as the BOLD data in init_functional_connectivity_nifti_wf
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

    if low_pass > 0 and high_pass > 0:
        btype = "bandpass"
        filt_input = [high_pass, low_pass]
    elif high_pass > 0:
        btype = "highpass"
        filt_input = high_pass
    elif low_pass > 0:
        btype = "lowpass"
        filt_input = low_pass
    else:
        raise ValueError("Filter parameters are not valid.")

    b, a = butter(
        order,
        filt_input,
        btype=btype,
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


@fill_doc
def estimate_brain_radius(mask_file, head_radius="auto"):
    """Estimate brain radius from binary brain mask file.

    Parameters
    ----------
    mask_file : :obj:`str`
        Binary brain mask file, in nifti format.
    %(head_radius)s

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


@fill_doc
def denoise_with_nilearn(
    preprocessed_bold,
    confounds_file,
    temporal_mask,
    low_pass,
    high_pass,
    filter_order,
    TR,
):
    """Denoise an array with Nilearn.

    This function is a modified version of Nilearn's signal.clean function, with the following
    changes:

    1.  Use :func:`numpy.linalg.lstsq` to estimate betas, instead of QR decomposition,
        in order to denoise the interpolated data as well.
    2.  Set any leading or trailing high-motion volumes to the closest low-motion volume's values
        instead of disabling extrapolation.
    3.  Return denoised, interpolated data.

    This function does the following:

    1.  Interpolate high-motion volumes in the BOLD data and confounds.
    2.  Estimate the mean of the low-motion BOLD data, to be added back in at a later step.
    3.  Detrend interpolated BOLD and confounds.
        -   Only done if denoising is requested.
        -   This also mean-centers the data.
    4.  Bandpass filter the interpolated data and confounds.
    5.  Censor the data and confounds.
    6.  Estimate betas using only the low-motion volumes.
    7.  Apply the betas to denoise the interpolated BOLD data. This is re-censored in a later step.
    8.  Add the mean BOLD back in after denoising.

    Parameters
    ----------
    preprocessed_bold : :obj:`numpy.ndarray` of shape (T, S)
        Preprocessed BOLD data, after dummy volume removal,
        but without any additional censoring.
    confounds_file : :obj:`str` or None
        Path to TSV file containing selected confounds, after dummy volume removal,
        but without any additional censoring.
        May be None, if no denoising should be performed.
    %(temporal_mask)s
    low_pass, high_pass : float
        Low-pass and high-pass thresholds, in Hertz.
        If 0, that bound will be skipped
        (e.g., if low-pass is 0 and high-pass isn't,
        then high-pass filtering will be performed instead of bnadpass filtering).
    filter_order : int
        Filter order.
    %(TR)s

    Returns
    -------
    denoised_interpolated_bold
        Returned as a :obj:`numpy.ndarray` of shape (T, S)
    """
    import pandas as pd
    from nilearn.signal import butterworth, standardize_signal

    # Coerce 0 filter values to None
    low_pass = low_pass if low_pass != 0 else None
    high_pass = high_pass if high_pass != 0 else None

    censoring_df = pd.read_table(temporal_mask)
    # Only remove high-motion outliers in this step (not the random volumes for trimming).
    sample_mask = ~censoring_df["framewise_displacement"].to_numpy().astype(bool)
    outlier_idx = list(np.where(~sample_mask)[0])

    denoise = bool(confounds_file)
    censor_and_interpolate = bool(outlier_idx)
    if denoise:
        confounds_df = pd.read_table(confounds_file)
        confounds_arr = confounds_df.to_numpy()

    if censor_and_interpolate:
        preprocessed_bold = _interpolate(arr=preprocessed_bold, sample_mask=sample_mask, TR=TR)
        if denoise:
            confounds_arr = _interpolate(arr=confounds_arr, sample_mask=sample_mask, TR=TR)

    if denoise:
        # Estimate the voxel-wise mean of the low-motion BOLD data, to be added back in later.
        # mean_bold = np.mean(preprocessed_bold[sample_mask, :], axis=0)

        # Detrend the interpolated data and confounds.
        # This also mean-centers the data and confounds.
        preprocessed_bold = standardize_signal(preprocessed_bold, detrend=True, standardize=False)
        confounds_arr = standardize_signal(confounds_arr, detrend=True, standardize=False)

    # Now apply the bandpass filter to the interpolated data and confounds
    if low_pass or high_pass:
        preprocessed_bold = butterworth(
            signals=preprocessed_bold,
            sampling_rate=1.0 / TR,
            low_pass=low_pass,
            high_pass=high_pass,
            order=filter_order,
            padtype="constant",
            padlen=preprocessed_bold.shape[0] - 1,
        )
        if denoise:
            confounds_arr = butterworth(
                signals=confounds_arr,
                sampling_rate=1.0 / TR,
                low_pass=low_pass,
                high_pass=high_pass,
                order=filter_order,
                padtype="constant",
                padlen=confounds_arr.shape[0] - 1,
            )

    # Denoise the data using the censored data and confounds
    if denoise:
        # Censor the data and confounds
        censored_bold = preprocessed_bold[sample_mask, :]
        censored_confounds = confounds_arr[sample_mask, :]

        # Estimate betas using only the censored data
        betas = np.linalg.lstsq(
            censored_confounds,
            censored_bold,
            rcond=None,
        )[0]

        # Denoise the interpolated data.
        # The low-motion volumes of the denoised, interpolated data will be the same as the
        # denoised, censored data.
        preprocessed_bold = preprocessed_bold - np.dot(confounds_arr, betas)

        # Add the voxel-wise mean (estimated from low-motion volumes only) back in
        # preprocessed_bold += mean_bold[None, :]

    return preprocessed_bold


def _interpolate(*, arr, sample_mask, TR):
    from nilearn import signal

    outlier_idx = list(np.where(~sample_mask)[0])
    n_volumes = arr.shape[0]

    interpolated_arr = signal._interpolate_volumes(
        arr,
        sample_mask=sample_mask,
        t_r=TR,
        extrapolate=True,
    )
    # Replace any high-motion volumes at the beginning or end of the run with the closest
    # low-motion volume's data.
    # Use https://stackoverflow.com/a/48106843/2589328 to group consecutive blocks of outliers.
    gaps = [[s, e] for s, e in zip(outlier_idx, outlier_idx[1:]) if s + 1 < e]
    edges = iter(outlier_idx[:1] + sum(gaps, []) + outlier_idx[-1:])
    consecutive_outliers_idx = list(zip(edges, edges))
    first_outliers = consecutive_outliers_idx[0]
    last_outliers = consecutive_outliers_idx[-1]

    # Replace outliers at beginning of run
    if first_outliers[0] == 0:
        LOGGER.warning(
            f"Outlier volumes at beginning of run ({first_outliers[0]}-{first_outliers[1]}) "
            "will be replaced with first non-outlier volume's values."
        )
        interpolated_arr[: first_outliers[1] + 1, :] = interpolated_arr[first_outliers[1] + 1, :]

    # Replace outliers at end of run
    if last_outliers[1] == n_volumes - 1:
        LOGGER.warning(
            f"Outlier volumes at end of run ({last_outliers[0]}-{last_outliers[1]}) "
            "will be replaced with last non-outlier volume's values."
        )
        interpolated_arr[last_outliers[0] :, :] = interpolated_arr[last_outliers[0] - 1, :]

    return interpolated_arr


def _select_first(lst):
    """Select the first element in a list."""
    return lst[0]


def list_to_str(lst):
    """Convert a list to a pretty string."""
    if not lst:
        raise ValueError("Zero-length list provided.")

    lst_str = [str(item) for item in lst]
    if len(lst_str) == 1:
        return lst_str[0]
    elif len(lst_str) == 2:
        return " and ".join(lst_str)
    else:
        return f"{', '.join(lst_str[:-1])}, and {lst_str[-1]}"


def _listify(obj):
    """Wrap all non-list or tuple objects in a list.

    This provides a simple way to accept flexible arguments.
    """
    return obj if isinstance(obj, (list, tuple, type(None), np.ndarray)) else [obj]


def _make_dictionary(metadata=None, **kwargs):
    """Create or modify a dictionary.

    This will add kwargs to a metadata dictionary if the dictionary is provided,
    or create a dictionary from scratch if not.
    """
    from copy import deepcopy

    from xcp_d.utils.utils import _listify

    if metadata:
        out_metadata = deepcopy(metadata)
        for key, value in kwargs.items():
            if key not in metadata.keys():
                out_metadata[key] = value
            elif isinstance(value, list) or isinstance(out_metadata[key], list):
                # Append the values if they're a list
                out_metadata[key] = _listify(out_metadata[key]) + _listify(value)
            else:
                # Overwrite the old value
                out_metadata[key] = value

        return out_metadata
    else:
        return dict(kwargs)


def _transpose_lol(lol):
    """Transpose list of lists."""
    return list(map(list, zip(*lol)))
