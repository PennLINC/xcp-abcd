# -*- coding: utf-8 -*-
"""Functions related to the documentation.

docdict contains the standard documentation entries used across xcp_d.

source: Eric Larson and MNE-python team.
https://github.com/mne-tools/mne-python/blob/main/mne/utils/docs.py
"""
import sys

###################################
# Standard documentation entries
#
docdict = dict()

docdict[
    "omp_nthreads"
] = """
omp_nthreads : :obj:`int`
    Maximum number of threads an individual process may use.
"""

docdict[
    "mem_gb"
] = """
mem_gb : :obj:`float`
    Memory limit, in gigabytes.
"""

docdict[
    "fmri_dir"
] = """
fmri_dir : :obj:`str`
    Path to the preprocessed derivatives dataset.
    For example, "/path/to/dset/derivatives/fmriprep/".
"""

docdict[
    "output_dir"
] = """
output_dir : :obj:`str`
    Path to the output directory for ``xcp_d`` derivatives.
    For example, "/path/to/dset/derivatives/xcp_d".

    As of version 0.7.0, 'xcp_d' will not be appended to the output directory.
"""

docdict[
    "work_dir"
] = """
work_dir : :obj:`str`
    Directory in which to store workflow execution state and temporary files.
"""

docdict[
    "analysis_level"
] = """
analysis_level : {"participant"}
    The analysis level for ``xcp_d``. Must be specified as "participant" since xcp_d
    performs analyses at the participant level.
"""

docdict[
    "anat_to_template_xfm"
] = """
anat_to_template_xfm : :obj:`str`
    Path to the T1w-to-MNI transform file.
    May be "identity", for testing purposes.
"""

docdict[
    "template_to_anat_xfm"
] = """
template_to_anat_xfm : :obj:`str`
    Path to the MNI-to-T1w transform file.
    May be "identity", for testing purposes.
"""

docdict[
    "name_source"
] = """
name_source : :obj:`str`
    Path to the file that will be used as the ``source_file`` for derivatives.
    This is generally the preprocessed BOLD file.
    This file does not need to exist (e.g., in the case of a concatenated version of the filename).
"""

docdict[
    "boldref"
] = """
boldref : :obj:`str`
    Path to the BOLD reference file associated with the target BOLD run.
    This comes from the preprocessing derivatives.
"""

docdict[
    "TR"
] = """
TR : :obj:`float`
    Repetition time of the BOLD run, in seconds.
"""

docdict[
    "fmriprep_confounds_file"
] = """
fmriprep_confounds_file : :obj:`str`
    Confounds TSV file from preprocessing derivatives.
"""

docdict[
    "params"
] = """
params : {"36P", "24P", "27P", "acompcor", "acompcor_gsr", \
          "aroma", "aroma_gsr", "custom"}, optional
    Shorthand for the parameter set to extract from the confounds TSV.
    Default is "36P", most expansive option.
"""

docdict[
    "input_type"
] = """
input_type : {"fmriprep", "dcan", "hcp", "nibabies", "ukb"}
    The format of the incoming preprocessed BIDS derivatives.
    DCAN- and HCP-format derivatives will automatically be converted to a more
    BIDS-compliant format.
    fMRIPrep and Nibabies derivatives are assumed to be roughly equivalent in terms of
    file organization and naming.
"""

docdict[
    "dcan_qc"
] = """
dcan_qc : :obj:`bool`
    This flag determines if DCAN-related QC steps will be taken.
    Enabling this flag will trigger the following steps:

    1. Brainsprite figures will be generated.
    2. The executive summary will be generated.
    3. DCAN QC files will be generated.
"""

docdict[
    "smoothing"
] = """
smoothing : :obj:`float`
    The full width at half maximum (FWHM), in millimeters,
    of the Gaussian smoothing kernel that will be applied to the post-processed and denoised data.
"""

docdict[
    "custom_confounds_folder"
] = """
custom_confounds_folder : :obj:`str` or None
    Path to folder containing custom nuisance regressors.
    Must be a folder containing confounds files,
    in which case the file with the name matching the preprocessing confounds file will be
    selected.
"""

docdict[
    "custom_confounds_file"
] = """
custom_confounds_file : :obj:`str` or None
    Path to custom nuisance regressors.
"""

docdict[
    "head_radius"
] = """
head_radius : :obj:`float` or "auto"
    Radius of the head, in millimeters, for framewise displacement calculation.

    ``xcp_d``'s default head radius is 50. The recommended value for infants is 35.
    A value of 'auto' is also supported, in which case the brain radius is
    estimated from the preprocessed brain mask.
"""

docdict[
    "fd_thresh"
] = """
fd_thresh : :obj:`float`
    Framewise displacement threshold for censoring, in millimeters.
    Any framewise displacement values higher than the threshold are flagged as "high motion".
    If set to <=0, no censoring will be performed.
    Default is 0.2 mm.
"""

docdict[
    "bandpass_filter"
] = """
bandpass_filter : :obj:`bool`
    If True, a Butterworth bandpass filter will be applied to the fMRI data after interpolation,
    but before regression.
    If False, bandpass filtering will not be performed.
"""

docdict[
    "high_pass"
] = """
high_pass : :obj:`float`
    Lower cut-off frequency for the Butterworth bandpass filter, in Hertz.
    The bandpass filter is applied to the fMRI data after post-processing and denoising.
    Bandpass filtering will only be performed if ``bandpass_filter`` is True.
    This internal parameter corresponds to the command-line parameter ``--lower-bpf``.
    If set to <= 0, high-pass filtering will be disabled.

    Default value is 0.01.
"""

docdict[
    "low_pass"
] = """
low_pass : :obj:`float`
    Upper cut-off frequency for the Butterworth bandpass filter, in Hertz.
    The bandpass filter is applied to the fMRI data after post-processing and denoising.
    Bandpass filtering will only be performed if ``bandpass_filter`` is True.
    This internal parameter corresponds to the command-line parameter ``--upper-bpf``.
    If set to <= 0, low-pass filtering will be disabled.

    Default value is 0.08.
"""

docdict[
    "bpf_order"
] = """
bpf_order : :obj:`int`
    Number of filter coefficients for Butterworth bandpass filter.
    Bandpass filtering will only be performed if ``bandpass_filter`` is True.
    This parameter is used in conjunction with ``lower_bpf``/``high_pass`` and
    ``upper_bpf``/``low_pass``.
"""

docdict[
    "motion_filter_type"
] = """
motion_filter_type : {None, "lp", "notch"}
    Type of filter to use for removing respiratory artifact from motion regressors.

    If None, no filter will be applied.

    If the filter type is set to "notch", frequencies between
    ``band_stop_min`` and ``band_stop_max`` will be removed with a notch filter.
    In this case, both ``band_stop_min`` and ``band_stop_max`` must be defined.

    If "lp", frequencies above ``band_stop_min`` will be removed with a Butterworth filter.
    In this case, only ``band_stop_min`` must be defined.
"""

docdict[
    "motion_filter_order"
] = """
motion_filter_order : :obj:`int`
    Number of filter coefficients for the motion parameter filter.
    Motion filtering is only performed if ``motion_filter_type`` is not None.
    This parameter is used in conjunction with ``band_stop_max`` and ``band_stop_min``.
"""

docdict[
    "band_stop_min"
] = """
band_stop_min : :obj:`float` or None
    Lower frequency for the motion parameter filter, in breaths-per-minute (bpm).
    Motion filtering is only performed if ``motion_filter_type`` is not None.
    If used with the "lp" ``motion_filter_type``, this parameter essentially corresponds to a
    low-pass filter (the maximum allowed frequency in the filtered data).
    This parameter is used in conjunction with ``motion_filter_order`` and ``band_stop_max``.

    Here is a list of recommended values, based on participant age:

    ================= =================
    Age Range (years) Recommended Value
    ================= =================
    < 1               30
    1 - 2             25
    2 - 6             20
    6 - 12            15
    12 - 18           12
    19 - 65           12
    65 - 80           12
    > 80              10
    ================= =================

    When ``motion_filter_type`` is set to "lp" (low-pass filter), another commonly-used value for
    this parameter is 6 BPM (equivalent to 0.1 Hertz), based on :footcite:t:`gratton2020removal`.
"""

docdict[
    "band_stop_max"
] = """
band_stop_max : :obj:`float` or None
    Upper frequency for the motion parameter filter, in breaths-per-minute (bpm).
    Motion filtering is only performed if ``motion_filter_type`` is not None.
    This parameter is only used if ``motion-filter-type`` is set to "notch".
    This parameter is used in conjunction with ``motion_filter_order`` and ``band_stop_min``.

    Here is a list of recommended values, based on participant age:

    ================= =================
    Age Range (years) Recommended Value
    ================= =================
    < 1               60
    1 - 2             50
    2 - 6             35
    6 - 12            25
    12 - 18           20
    19 - 65           18
    65 - 80           28
    > 80              30
    ================= =================
"""

docdict[
    "exact_time"
] = """
exact_time : :obj:`list` of :obj:`float`, optional
    If used, this parameter will produce correlation matrices limited to each requested
    amount of time.
    If there is more than the required amount of low-motion data,
    then volumes will be randomly selected to produce denoised outputs with the exact
    amounts of time requested.
    If there is less than the required amount of 'good' data,
    then the run will not be post-processed.
"""

docdict[
    "exact_scans"
] = """
exact_scans : :obj:`list` of :obj:`int`, optional
    If used, this parameter will produce correlation matrices limited to each requested
    amount of time.
    If there is more than the required amount of low-motion data,
    then volumes will be randomly selected to produce denoised outputs with the exact
    amounts of time requested.
    If there is less than the required amount of 'good' data,
    then the run will not be post-processed.
"""

docdict[
    "name"
] = """
name : :obj:`str`, optional
    Name of the workflow. This is used for working directories and workflow graphs.
"""

docdict[
    "cifti"
] = """
cifti : :obj:`bool`
    Post-process surface data (CIFTIs) instead of volumetric data (NIFTIs).
    This parameter is overridden when DCAN- or HCP-format data are provided.
    Default is False.
"""

docdict[
    "process_surfaces"
] = """
process_surfaces : :obj:`bool`, optional
    If True, a workflow will be run to warp native-space (fsnative) reconstructed cortical
    surfaces (surf.gii files) produced by Freesurfer into standard (fsLR) space.
    These surface files are primarily used for visual quality control.
    By default, this workflow is disabled.
"""

docdict[
    "subject_id"
] = """
subject_id : :obj:`str`
    The participant ID. This SHOULD NOT include the ``sub-`` prefix.
"""

docdict[
    "layout"
] = """
layout : :obj:`bids.layout.BIDSLayout`
    BIDSLayout indexing the ingested (e.g., fMRIPrep-format) derivatives.
"""

docdict[
    "dummy_scans"
] = """
dummy_scans : :obj:`int` or "auto"
    Number of volumes to remove from the beginning of each run.
    If set to 'auto', xcp_d will extract non-steady-state volume indices from the
    preprocessing derivatives' confounds file.
"""

docdict[
    "random_seed"
] = """
random_seed : :obj:`int` or None
    Random seed for the workflow.
    This is currently only used with the ``--exact-time`` parameter,
    when randomly selecting volumes to censor for correlation matrices.
"""

docdict[
    "min_coverage"
] = """
min_coverage : :obj:`float`
    Coverage threshold to apply to parcels in each atlas.
    Any parcels with lower coverage than the threshold will be replaced with NaNs.
    Must be a value between zero and one.
    Default is 0.5.
"""

docdict[
    "min_time"
] = """
min_time : :obj:`float`
    Post-scrubbing threshold to apply to individual runs in the dataset.
    This threshold determines the minimum amount of time, in seconds,
    needed to post-process a given run, once high-motion outlier volumes are removed.
    This will have no impact if scrubbing is disabled
    (i.e., if the FD threshold is zero or negative).
    This parameter can be disabled by providing a zero or a negative value.
    Default is 100.
"""

docdict[
    "despike"
] = """
despike : :obj:`bool`
    If True, the BOLD data will be despiked before censoring/denoising/filtering/interpolation.
    If False, no despiking will be performed.

    For NIFTI data, despiking is performed with AFNI's 3dDespike.
    For CIFTI data, the data will be converted to NIFTI format, 3dDespike will be run, and then
    the despiked data will be converted back to CIFTI format.
"""

docdict[
    "filtered_motion"
] = """
filtered_motion : :obj:`str`
    Framewise displacement timeseries, potentially after bandstop or low-pass filtering.
    This is a TSV file with one column: 'framewise_displacement'.
"""

docdict[
    "temporal_mask"
] = """
temporal_mask : :obj:`str`
    Temporal mask; all values above ``fd_thresh`` set to 1.
    This is a TSV file with one column: 'framewise_displacement'.
"""

docdict[
    "denoised_interpolated_bold"
] = """
denoised_interpolated_bold : :obj:`str`
    Path to the censored, denoised, interpolated, and filtered BOLD file.
    This file is the result of denoising the censored preprocessed BOLD data,
    followed by cubic spline interpolation and band-pass filtering.

    This output should not be used for analysis. It is primarily for DCAN QC plots.
"""

docdict[
    "censored_denoised_bold"
] = """
censored_denoised_bold : :obj:`str`
    Path to the censored, denoised, interpolated, filtered, and re-censored BOLD file.
    This file is the result of denoising the censored preprocessed BOLD data,
    followed by cubic spline interpolation, band-pass filtering, and re-censoring.

    This output is the primary derivative for analysis.
"""

docdict[
    "smoothed_denoised_bold"
] = """
smoothed_denoised_bold : :obj:`str`
    Path to the censored, denoised, interpolated, filtered, re-censored, and smoothed BOLD file.
    This file is the result of denoising the censored preprocessed BOLD data,
    followed by cubic spline interpolation, band-pass filtering, re-censoring, and spatial
    smoothing.
"""

docdict[
    "atlases"
] = """
atlases : :obj:`list` of :obj:`str`
    A list of atlases used for parcellating the BOLD data.
    The set of atlases to use is defined by the user.
"""

docdict[
    "coverage"
] = """
coverage : :obj:`list` of :obj:`str`
    List of paths to atlas-specific coverage TSV files.
"""

docdict[
    "coverage_ciftis"
] = """
coverage_ciftis : :obj:`list` of :obj:`str`
    List of paths to atlas-specific coverage CIFTI (pscalar) files.
"""

docdict[
    "timeseries"
] = """
timeseries : :obj:`list` of :obj:`str`
    List of paths to atlas-specific time series TSV files.
    These time series are produced from the ``censored_denoised_bold`` outputs.
"""

docdict[
    "timeseries_ciftis"
] = """
timeseries_ciftis : :obj:`list` of :obj:`str`
    List of paths to atlas-specific time series CIFTI (ptseries) files.
    These time series are produced from the ``censored_denoised_bold`` outputs.
"""

docdict[
    "correlations"
] = """
correlations : :obj:`list` of :obj:`str`
    List of paths to atlas-specific ROI-to-ROI correlation TSV files.
    These correlations are produced from the ``timeseries`` outputs.
"""

docdict[
    "correlation_ciftis"
] = """
correlation_ciftis : :obj:`list` of :obj:`str`
    List of paths to atlas-specific ROI-to-ROI correlation CIFTI (pconn) files.
    These correlations are produced from the ``timeseries_cifti`` outputs.
"""

docdict[
    "correlations_exact"
] = """
correlations_exact : :obj:`list` of :obj:`list` of :obj:`str`
    Exact-scan-wise list of lists of paths to atlas-specific ROI-to-ROI correlation TSV files.
    These correlations are produced from the ``timeseries`` outputs and the ``temporal_mask``
    input.
"""

docdict[
    "correlation_ciftis_exact"
] = """
correlation_ciftis : :obj:`list` of :obj:`list` of :obj:`str`
    Exact-scan-wise list of lists of paths to atlas-specific ROI-to-ROI correlation CIFTI (pconn)
    files.
    These correlations are produced from the ``timeseries`` outputs and the ``temporal_mask``
    input.
"""

docdict_indented = {}


def _indentcount_lines(lines):
    """Minimum indent for all lines in line list.

    >>> lines = [' one', '  two', '   three']
    >>> _indentcount_lines(lines)
    1
    >>> lines = []
    >>> _indentcount_lines(lines)
    0
    >>> lines = [' one']
    >>> _indentcount_lines(lines)
    1
    >>> _indentcount_lines(['    '])
    0

    """
    indentno = sys.maxsize
    for line in lines:
        stripped = line.lstrip()
        if stripped:
            indentno = min(indentno, len(line) - len(stripped))
    if indentno == sys.maxsize:
        return 0
    return indentno


def fill_doc(f):
    """Fill a docstring with docdict entries.

    Parameters
    ----------
    f : callable
        The function to fill the docstring of. Will be modified in place.

    Returns
    -------
    f : callable
        The function, potentially with an updated ``__doc__``.

    """
    docstring = f.__doc__
    if not docstring:
        return f
    lines = docstring.splitlines()
    # Find the minimum indent of the main docstring, after first line
    if len(lines) < 2:
        icount = 0
    else:
        icount = _indentcount_lines(lines[1:])
    # Insert this indent to dictionary docstrings
    try:
        indented = docdict_indented[icount]
    except KeyError:
        indent = " " * icount
        docdict_indented[icount] = indented = {}
        for name, dstr in docdict.items():
            lines = dstr.splitlines()
            try:
                newlines = [lines[0]]
                for line in lines[1:]:
                    newlines.append(indent + line)
                indented[name] = "\n".join(newlines)
            except IndexError:
                indented[name] = dstr
    try:
        f.__doc__ = docstring % indented
    except (TypeError, ValueError, KeyError) as exp:
        funcname = f.__name__
        funcname = docstring.split("\n")[0] if funcname is None else funcname
        raise RuntimeError(f"Error documenting {funcname}:\n{str(exp)}")
    return f


def download_example_data(out_dir=None, overwrite=False):
    """Download example data from Box."""
    import os
    import tarfile

    import requests

    from xcp_d.data import load as load_data

    if not out_dir:
        out_dir = str(load_data("."))

    out_dir = os.path.abspath(out_dir)

    url = "https://upenn.box.com/shared/static/1dd4u115invn60cr3qm8xl8p5axho5dp"
    target_path = os.path.join(out_dir, "ds001419-example")

    if overwrite or not os.path.isdir(target_path):
        target_file = os.path.join(out_dir, "ds001419-example.tar.gz")

        if overwrite or not os.path.isfile(target_file):
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                with open(target_file, "wb") as fo:
                    fo.write(response.raw.read())

        if not os.path.isfile(target_file):
            raise FileNotFoundError(f"File DNE: {target_file}")

        # Expand the file
        with tarfile.open(target_file, "r:gz") as fo:
            fo.extractall(out_dir)

    return target_path
