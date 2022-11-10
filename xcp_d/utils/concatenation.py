# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Functions for concatenating scans across runs."""
import os
import tempfile
from json import loads
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from bids.layout import BIDSLayout, Query
from nilearn.image import concat_imgs
from nipype import logging
from pkg_resources import resource_filename as _pkgres

from xcp_d.utils.bids import _get_tr
from xcp_d.utils.modified_data import _drop_dummy_scans
from xcp_d.utils.plot import plot_svgx
from xcp_d.utils.qcmetrics import compute_dvars
from xcp_d.utils.utils import get_segfile
from xcp_d.utils.write_save import read_ndata

_pybids_spec = loads(Path(_pkgres("xcp_d", "data/nipreps.json")).read_text())
path_patterns = _pybids_spec["default_path_patterns"]
LOGGER = logging.getLogger("nipype.interface")


def concatenate_derivatives(dummytime, fmridir, outputdir, work_dir, subjects, cifti, dcan_qc):
    """Concatenate derivatives.

    This function does a lot more than concatenate derivatives.
    It also makes DCAN QC files, creates figures, and copies figures from the preprocessed
    dataset to the post-processed dataset.

    TODO: Move concatenation to *inside* main workflow.
    That way we can feed files in directly instead of searching for them,
    and we can pass the already-initialized fMRIPrep BIDSLayout.

    Parameters
    ----------
    dummytime: float
        Amount of time to drop from the beginning of the scan
    fmridir : str
        Path to preprocessed derivatives (not xcpd post-processed derivatives).
    outputdir : str
        Path to location of xcpd derivatives.
    work_dir : str
        Working directory.
    subjects : list of str
        List of subjects to run concatenation on.
    cifti : bool
        Whether xcpd was run on CIFTI files or not.
    dcan_qc : bool
        Whether to perform DCAN QC or not.
    """
    LOGGER.debug("Starting concatenation workflow.")

    # NOTE: The config has no effect when derivatives is True :(
    # At least for pybids ~0.15.1.
    # TODO: Find a way to support the xcpd config file in the BIDSLayout.
    layout_xcpd = BIDSLayout(
        outputdir,
        validate=False,
        derivatives=True,
    )
    layout_fmriprep = BIDSLayout(
        fmridir,
        validate=False,
        derivatives=True,
        config=["bids", "derivatives"],
    )

    if cifti:
        tsv_extensions = [".ptseries.nii"]
        img_extensions = [".dtseries.nii"]
    else:
        tsv_extensions = [".tsv"]
        img_extensions = [".nii.gz"]

    for subject in subjects:
        if subject.startswith("sub-"):
            subject = subject[4:]

        LOGGER.debug(f"Concatenating subject {subject}")

        sessions = layout_xcpd.get_sessions(subject=subject)
        if not sessions:
            sessions = [None]

        for session in sessions:
            LOGGER.debug(f"Concatenating session {session}")

            base_entities = {
                "subject": subject,
                "session": session,
                "datatype": "func",
            }
            tasks = layout_xcpd.get_tasks(
                desc="denoised",
                suffix="bold",
                extension=img_extensions,
                **base_entities,
            )
            for task in tasks:
                LOGGER.debug(f"Concatenating task {task}")

                task_entities = base_entities.copy()
                task_entities["task"] = task

                motion_files = layout_xcpd.get(
                    run=Query.ANY,
                    desc=["filtered", None],
                    suffix="motion",
                    extension=".tsv",
                    **task_entities,
                )
                if len(motion_files) == 0:
                    # No run-wise motion files exist, so task probably only has one run.
                    motion_files = layout_xcpd.get(
                        run=None,
                        desc=["filtered", None],
                        suffix="motion",
                        extension=".tsv",
                        **task_entities,
                    )
                    if len(motion_files) == 1:
                        if dcan_qc:
                            # Make DCAN HDF5 file from single motion file
                            dcan_df_file = (
                                f"{'.'.join(motion_files[0].path.split('.')[:-1])}-DCAN.hdf5"
                            )

                            # Get TR from one of the preproc files
                            preproc_files = layout_fmriprep.get(
                                desc=["preproc", None],
                                suffix="bold",
                                extension=img_extensions,
                                **task_entities,
                            )
                            TR = _get_tr(preproc_files[0].path)

                            make_dcan_df([motion_files[0].path], dcan_df_file, TR)
                            LOGGER.debug(f"Only one run found for task {task}")

                        continue
                    elif len(motion_files) == 0:
                        LOGGER.warning(f"No motion files found for task {task}")
                        continue
                    else:
                        raise ValueError(
                            "Found multiple motion files when there should only be one: "
                            f"{motion_files}"
                        )

                # Get TR from one of the preproc files
                preproc_files = layout_fmriprep.get(
                    desc=["preproc", None],
                    run=Query.ANY,
                    suffix="bold",
                    extension=img_extensions,
                    **task_entities,
                )
                TR = _get_tr(preproc_files[0].path)

                # Make DCAN HDF5 file for each of the motion files
                if dcan_qc:
                    for motion_file in motion_files:
                        dcan_df_file = f"{'.'.join(motion_file.path.split('.')[:-1])}-DCAN.hdf5"
                        make_dcan_df([motion_file.path], dcan_df_file, TR)

                # Concatenate motion files
                motion_file_names = ", ".join([motion_file.path for motion_file in motion_files])
                LOGGER.debug(f"Concatenating motion files: {motion_file_names}")
                concat_motion_file = _get_concat_name(layout_xcpd, motion_files[0])
                concatenate_tsv_files(motion_files, concat_motion_file)

                # Make DCAN HDF5 file from concatenated motion file
                if dcan_qc:
                    concat_dcan_df_file = (
                        f"{'.'.join(concat_motion_file.split('.')[:-1])}-DCAN.hdf5"
                    )
                    make_dcan_df([concat_motion_file], concat_dcan_df_file, TR)

                # Concatenate outlier files
                outlier_files = layout_xcpd.get(
                    run=Query.ANY,
                    desc=None,
                    suffix="outliers",
                    extension=".tsv",
                    **task_entities,
                )
                outlier_file_names = ", ".join(
                    [outlier_file.path for outlier_file in outlier_files]
                )
                LOGGER.debug(f"Concatenating outlier files: {outlier_file_names}")
                concat_outlier_file = _get_concat_name(layout_xcpd, outlier_files[0])
                outfile = concatenate_tsv_files(outlier_files, concat_outlier_file)

                # otherwise, concatenate stuff
                output_spaces = layout_xcpd.get_spaces(
                    run=Query.ANY,
                    desc="denoised",
                    suffix="bold",
                    extension=img_extensions,
                    **task_entities,
                )

                for space in output_spaces:
                    LOGGER.debug(f"Concatenating files in {space} space")
                    space_entities = task_entities.copy()
                    space_entities["space"] = space

                    # Preprocessed BOLD files
                    preproc_files = layout_fmriprep.get(
                        run=Query.ANY,
                        desc=["preproc", None],
                        suffix="bold",
                        extension=img_extensions,
                        **space_entities,
                    )
                    concat_preproc_file = os.path.join(
                        tempfile.mkdtemp(),
                        f"rawdata{preproc_files[0].extension}",
                    )
                    preproc_files_str = "\n\t".join(
                        [preproc_file.path for preproc_file in preproc_files]
                    )
                    LOGGER.debug(
                        f"Concatenating preprocessed file ({concat_preproc_file}) from\n"
                        f"{preproc_files_str}"
                    )

                    _concatenate_niimgs(preproc_files, concat_preproc_file)

                    if not cifti:
                        # Mask file
                        mask_files = layout_fmriprep.get(
                            run=1,
                            desc=["brain"],
                            suffix="mask",
                            extension=[".nii.gz"],
                            **space_entities,
                        )
                        if len(mask_files) == 0:
                            raise ValueError(f"No mask files found for {preproc_files[0].path}")
                        elif len(mask_files) != 1:
                            LOGGER.warning(
                                f"More than one mask file found. Using first: {mask_files}"
                            )

                        mask = mask_files[0].path
                        # TODO: Use layout_fmriprep for this
                        segfile = get_segfile(preproc_files[0].path)
                    else:
                        mask = None
                        segfile = None

                    # Calculate DVARS from preprocessed BOLD
                    raw_dvars = []
                    for preproc_file in preproc_files:
                        dvar = compute_dvars(read_ndata(preproc_file.path, mask))
                        dvar[0] = np.mean(dvar)
                        raw_dvars.append(dvar)
                    raw_dvars = np.concatenate(raw_dvars)

                    TR = _get_tr(preproc_files[0].path)

                    # Denoised BOLD files
                    bold_files = layout_xcpd.get(
                        run=Query.ANY,
                        desc="denoised",
                        suffix="bold",
                        extension=img_extensions,
                        **space_entities,
                    )
                    concat_bold_file = _get_concat_name(layout_xcpd, bold_files[0])
                    LOGGER.debug(f"Concatenating postprocessed file: {concat_bold_file}")
                    _concatenate_niimgs(bold_files, concat_bold_file)

                    # Calculate DVARS from denoised BOLD
                    regressed_dvars = []
                    for bold_file in bold_files:
                        dvar = compute_dvars(read_ndata(bold_file.path, mask))
                        dvar[0] = np.mean(dvar)
                        regressed_dvars.append(dvar)
                    regressed_dvars = np.concatenate(regressed_dvars)

                    # Concatenate smoothed BOLD files if they exist
                    smooth_bold_files = layout_xcpd.get(
                        run=Query.ANY,
                        desc="denoisedSmoothed",
                        suffix="bold",
                        extension=img_extensions,
                        **space_entities,
                    )
                    if len(smooth_bold_files):
                        concat_file = _get_concat_name(layout_xcpd, smooth_bold_files[0])
                        LOGGER.debug(f"Concatenating smoothed postprocessed file: {concat_file}")
                        _concatenate_niimgs(smooth_bold_files, concat_file)

                    # Executive summary carpet plots
                    if dcan_qc:
                        LOGGER.debug("Generating carpet plots")
                        carpet_entities = bold_files[0].get_entities()
                        carpet_entities = _sanitize_entities(carpet_entities)
                        carpet_entities["run"] = None
                        carpet_entities["datatype"] = "figures"
                        carpet_entities["extension"] = ".svg"

                        carpet_entities["desc"] = "precarpetplot"
                        precarpet = layout_xcpd.build_path(
                            carpet_entities,
                            path_patterns=path_patterns,
                            strict=False,
                            validate=False,
                        )

                        carpet_entities["desc"] = "postcarpetplot"
                        postcarpet = layout_xcpd.build_path(
                            carpet_entities,
                            path_patterns=path_patterns,
                            strict=False,
                            validate=False,
                        )

                        # Build figures
                        initial_volumes_to_drop = 0
                        if dummytime > 0:
                            initial_volumes_to_drop = int(np.ceil(dummytime / TR))

                        LOGGER.debug("Starting plot_svgx")
                        plot_svgx(
                            preprocessed_file=concat_preproc_file,
                            denoised_file=concat_bold_file,
                            denoised_filtered_file=concat_bold_file,
                            dummyvols=initial_volumes_to_drop,
                            tmask=outfile,
                            filtered_motion=concat_motion_file,
                            raw_dvars=raw_dvars,
                            regressed_dvars=regressed_dvars,
                            filtered_dvars=regressed_dvars,
                            processed_filename=postcarpet,
                            unprocessed_filename=precarpet,
                            mask=mask,
                            seg_data=segfile,
                            TR=TR,
                            work_dir=work_dir,
                        )
                        LOGGER.debug("plot_svgx done")

                    # Now timeseries files
                    atlases = layout_xcpd.get_atlases(
                        suffix="timeseries",
                        extension=tsv_extensions,
                        **space_entities,
                    )
                    for atlas in atlases:
                        LOGGER.debug(f"Concatenating time series files for atlas {atlas}")
                        atlas_timeseries_files = layout_xcpd.get(
                            run=Query.ANY,
                            atlas=atlas,
                            suffix="timeseries",
                            extension=tsv_extensions,
                            **space_entities,
                        )
                        concat_file = _get_concat_name(layout_xcpd, atlas_timeseries_files[0])
                        if atlas_timeseries_files[0].extension == ".tsv":
                            concatenate_tsv_files(atlas_timeseries_files, concat_file)
                        elif atlas_timeseries_files[0].extension == ".ptseries.nii":
                            _concatenate_niimgs(atlas_timeseries_files, concat_file)
                        else:
                            raise ValueError(
                                f"Unknown extension for {atlas_timeseries_files[0].path}"
                            )


def make_dcan_df(fds_files, name, TR):
    """Create an HDF5-format file containing a DCAN-format dataset.

    Parameters
    ----------
    fds_files : list of str
        List of files from which to extract information.
    name : str
        Name of the HDF5-format file to be created.
    TR : float
        Repetition time.

    Notes
    -----
    FD_threshold: a number >= 0 that represents the FD threshold used to calculate
    the metrics in this list.
    frame_removal: a binary vector/array the same length as the number of frames
    in the concatenated time series, indicates whether a frame is removed (1) or
    not (0)
    format_string (legacy): a string that denotes how the frames were excluded
    -- uses a notation devised by Avi Snyder
    total_frame_count: a whole number that represents the total number of frames
    in the concatenated series
    remaining_frame_count: a whole number that represents the number of remaining
    frames in the concatenated series
    remaining_seconds: a whole number that represents the amount of time remaining
    after thresholding
    remaining_frame_mean_FD: a number >= 0 that represents the mean FD of the
    remaining frames
    """
    LOGGER.debug(f"Generating DCAN file: {name}")

    # Load filtered framewise_displacement values from files and concatenate
    filtered_motion_dfs = [pd.read_table(fds_file) for fds_file in fds_files]
    filtered_motion_df = pd.concat(filtered_motion_dfs, axis=0)
    fd = filtered_motion_df["framewise_displacement"].values

    with h5py.File(name, "w") as dcan:
        for thresh in np.linspace(0, 1, 101):
            thresh = np.around(thresh, 2)

            dcan.create_dataset(f"/dcan_motion/fd_{thresh}/skip", data=0, dtype="float")
            dcan.create_dataset(
                f"/dcan_motion/fd_{thresh}/binary_mask",
                data=(fd > thresh).astype(int),
                dtype="float",
            )
            dcan.create_dataset(f"/dcan_motion/fd_{thresh}/threshold", data=thresh, dtype="float")
            dcan.create_dataset(
                f"/dcan_motion/fd_{thresh}/total_frame_count", data=len(fd), dtype="float"
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


def concatenate_tsv_files(tsv_files, fileout):
    """Concatenate framewise displacement time series across files.

    This function doesn't return anything, but it writes out the ``fileout`` file.

    Parameters
    ----------
    tsv_files : list of str
        Paths to TSV files to concatenate.
    fileout : str
        Path to the file that will be written out.
    """
    # TODO: Support headers in timeseries files
    if tsv_files[0].path.endswith("timeseries.tsv"):
        # timeseries files have no header
        data = [np.loadtxt(tsv_file.path, delimiter="\t") for tsv_file in tsv_files]
        data = np.vstack(data)
        np.savetxt(fileout, data, fmt="%.5f", delimiter="\t")
    else:
        # other tsv files have a header
        data = [pd.read_table(tsv_file.path) for tsv_file in tsv_files]
        data = pd.concat(data, axis=0)
        data.to_csv(fileout, sep="\t", index=False)
    return fileout


def _get_concat_name(layout_xcpd, in_file):
    """Drop run entity from filename to get concatenated version."""
    in_file_entities = in_file.get_entities()
    in_file_entities["run"] = None
    concat_file = layout_xcpd.build_path(
        in_file_entities,
        path_patterns=path_patterns,
        strict=False,
        validate=False,
    )
    return concat_file


def _sanitize_entities(dict_):
    """Ensure "description" isn't in dictionary keys."""
    dict_ = dict_.copy()
    if "description" in dict_.keys():
        dict_["desc"] = dict_["description"]
        del dict_["description"]

    return dict_


def _concatenate_niimgs(files, out_file, dummy_scans=None):
    """Concatenate niimgs.

    This is generally a very simple proposition (especially with niftis).
    However, sometimes we need to account for dummy scans- especially when we want to use
    the non-steady-state volume indices from fMRIPrep.

    Parameters
    ----------
    files : :obj:`list` of :obj:`bids.layout.models.BIDSImageFile`
        List of BOLD files to concatenate over the time dimension.
    out_file : :obj:`str`
        The concatenated file to write out.
    dummy_scans : None or int, optional
        The number of dummy scans to drop from the beginning of each file before concatenation.
        If None (default), no volumes will be dropped.
        If an integer, the same number of volumes will be dropped from each file.
    """
    if dummy_scans is not None:
        assert isinstance(dummy_scans, int)

    is_nifti = files[0].extension == ".nii.gz"

    if isinstance(dummy_scans, int):
        runwise_dummy_scans = [dummy_scans] * len(files)

    if dummy_scans is not None:
        bold_imgs = [
            _drop_dummy_scans(f.path, dummy_scans=runwise_dummy_scans[i])
            for i, f in enumerate(files)
        ]
        if is_nifti:
            bold_files = bold_imgs
        else:
            # Create temporary files for cifti images
            bold_files = []
            for i_img, img in enumerate(bold_imgs):
                temporary_file = f"temp_{i_img}{files[0].extension}"
                img.to_filename(temporary_file)
                bold_files.append(temporary_file)

    else:
        bold_files = [f.path for f in files]

    if is_nifti:
        concat_preproc_img = concat_imgs(bold_files)
        concat_preproc_img.to_filename(out_file)
    else:
        os.system(f"wb_command -cifti-merge {out_file} -cifti {' -cifti '.join(bold_files)}")

        if dummy_scans is not None:
            # Delete temporary files
            for bold_file in bold_files:
                os.remove(bold_file)
