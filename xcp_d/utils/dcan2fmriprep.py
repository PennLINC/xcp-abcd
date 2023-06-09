# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Functions for converting DCAN-format derivatives to fMRIPrep format."""
import glob
import logging
import os
import re

import nibabel as nb
import numpy as np
import pandas as pd
from pkg_resources import resource_filename as pkgrf

from xcp_d.utils.filemanip import ensure_list
from xcp_d.utils.ingestion import copy_file, extract_mean_signal, plot_bbreg, write_json

LOGGER = logging.getLogger("nipype.utils")


def convert_dcan2bids(in_dir, out_dir, participant_ids=None):
    """Convert DCAN derivatives to BIDS-compliant derivatives.

    Parameters
    ----------
    in_dir : str
        Path to DCAN derivatives.
    out_dir : str
        Path to the output BIDS-compliant derivatives folder.
    participant_ids : None or list of str
        List of participant IDs to run conversion on.
        The participant IDs must not have the "sub-" prefix.
        If None, the function will search for all subjects in ``in_dir`` and convert all of them.

    Returns
    -------
    participant_ids : list of str
        The list of subjects whose derivatives were converted.

    Notes
    -----
    Since the T1w is in standard space already, we use identity transforms instead of the
    individual transforms available in the DCAN derivatives.
    """
    LOGGER.warning("convert_dcan2bids is an experimental function.")
    in_dir = os.path.abspath(in_dir)
    out_dir = os.path.abspath(out_dir)

    if participant_ids is None:
        subject_folders = sorted(glob.glob(os.path.join(in_dir, "sub*")))
        subject_folders = [
            subject_folder for subject_folder in subject_folders if os.path.isdir(subject_folder)
        ]
        participant_ids = [os.path.basename(subject_folder) for subject_folder in subject_folders]
        if not participant_ids:
            raise ValueError(f"No subject found in {in_dir}")

    else:
        participant_ids = ensure_list(participant_ids)

    for subject_id in participant_ids:
        LOGGER.info(f"Processing {subject_id}")
        convert_dcan_to_bids_single_subject(
            in_dir=in_dir,
            out_dir=out_dir,
            sub_ent=subject_id,
        )

    return participant_ids


def convert_dcan_to_bids_single_subject(in_dir, out_dir, sub_ent):
    """Convert DCAN derivatives to BIDS-compliant derivatives for a single subject.

    Parameters
    ----------
    in_dir : str
        Path to the subject's DCAN derivatives.
    out_dir : str
        Path to the output BIDS-compliant derivatives folder.
    sub_ent : str
        Subject identifier, with "sub-" prefix.

    Notes
    -----
    Since the T1w is in standard space already, we use identity transforms instead of the
    individual transforms available in the DCAN derivatives.
    """
    assert isinstance(in_dir, str)
    assert os.path.isdir(in_dir)
    assert isinstance(out_dir, str)
    assert isinstance(sub_ent, str)

    sub_id = sub_ent.replace("sub-", "")
    # Reset the subject entity in case the sub- prefix wasn't included originally.
    sub_ent = f"sub-{sub_id}"

    VOLSPACE = "MNI152NLin6Asym"
    volspace_ent = f"space-{VOLSPACE}"
    RES_ENT = "res-2"

    subject_dir_fmriprep = os.path.join(out_dir, sub_ent)

    # get session ids
    session_folders = sorted(glob.glob(os.path.join(in_dir, sub_ent, "s*")))
    ses_entities = [
        os.path.basename(ses_dir) for ses_dir in session_folders if os.path.isdir(ses_dir)
    ]

    # A dictionary of mappings from HCP derivatives to fMRIPrep derivatives.
    # Values will be lists, to allow one-to-many mappings.
    copy_dictionary = {}

    # The identity xform is used in place of any actual ones.
    identity_xfm = pkgrf("xcp_d", "/data/transform/itkIdentityTransform.txt")
    copy_dictionary[identity_xfm] = []

    for ses_ent in ses_entities:
        LOGGER.info(f"Processing {ses_ent}")
        session_dir_fmriprep = os.path.join(subject_dir_fmriprep, ses_ent)

        if os.path.isdir(session_dir_fmriprep):
            LOGGER.info("Converted session folder already exists. Skipping conversion.")
            continue

        anat_dir_orig = os.path.join(in_dir, sub_ent, ses_ent, "files", "MNINonLinear")
        anat_dir_fmriprep = os.path.join(session_dir_fmriprep, "anat")

        # NOTE: Why *was* this set to the *first* session only? (I fixed it)
        # AFAICT, this would copy the first session's files from DCAN into *every*
        # session of the output directory.
        func_dir_orig = os.path.join(anat_dir_orig, "Results")
        func_dir_fmriprep = os.path.join(session_dir_fmriprep, "func")
        work_dir = os.path.join(subject_dir_fmriprep, "work")

        os.makedirs(anat_dir_fmriprep, exist_ok=True)
        os.makedirs(func_dir_fmriprep, exist_ok=True)
        os.makedirs(work_dir, exist_ok=True)

        # We don't actually use any transforms, so we don't need the xfms directory.
        # xforms_dir_orig = os.path.join(anat_dir_orig, "xfms")

        # Collect anatomical files to copy
        t1w_orig = os.path.join(anat_dir_orig, "T1w.nii.gz")
        t1w_fmriprep = os.path.join(
            anat_dir_fmriprep,
            f"{sub_ent}_{ses_ent}_{volspace_ent}_desc-preproc_T1w.nii.gz",
        )
        copy_dictionary[t1w_orig] = [t1w_fmriprep]

        brainmask_orig = os.path.join(anat_dir_orig, "brainmask_fs.nii.gz")
        brainmask_fmriprep = os.path.join(
            anat_dir_fmriprep,
            f"{sub_ent}_{ses_ent}_{volspace_ent}_desc-brain_mask.nii.gz",
        )
        copy_dictionary[brainmask_orig] = [brainmask_fmriprep]

        # NOTE: What is this file for?
        ribbon_orig = os.path.join(anat_dir_orig, "ribbon.nii.gz")
        ribbon_fmriprep = os.path.join(
            anat_dir_fmriprep,
            f"{sub_ent}_{ses_ent}_{volspace_ent}_desc-ribbon_T1w.nii.gz",
        )
        copy_dictionary[ribbon_orig] = [ribbon_fmriprep]

        dseg_orig = os.path.join(anat_dir_orig, "aparc+aseg.nii.gz")
        dseg_fmriprep = os.path.join(
            anat_dir_fmriprep,
            f"{sub_ent}_{ses_ent}_{volspace_ent}_desc-aparcaseg_dseg.nii.gz",
        )
        copy_dictionary[dseg_orig] = [dseg_fmriprep]

        # Grab transforms
        # t1w_to_template_orig = os.path.join(xforms_dir_orig, "ANTS_CombinedWarp.nii.gz")
        t1w_to_template_fmriprep = os.path.join(
            anat_dir_fmriprep,
            f"{sub_ent}_{ses_ent}_from-T1w_to-{VOLSPACE}_mode-image_xfm.txt",
        )
        copy_dictionary[identity_xfm].append(t1w_to_template_fmriprep)

        # template_to_t1w_orig = os.path.join(xforms_dir_orig, "ANTS_CombinedInvWarp.nii.gz")
        template_to_t1w_fmriprep = os.path.join(
            anat_dir_fmriprep,
            f"{sub_ent}_{ses_ent}_from-{VOLSPACE}_to-T1w_mode-image_xfm.txt",
        )
        copy_dictionary[identity_xfm].append(template_to_t1w_fmriprep)

        # Grab surface morphometry files
        fsaverage_dir_orig = os.path.join(anat_dir_orig, "fsaverage_LR32k")

        SURFACE_DICT = {
            "R.midthickness.32k_fs_LR.surf.gii": "hemi-R_desc-hcp_midthickness.surf.gii",
            "L.midthickness.32k_fs_LR.surf.gii": "hemi-L_desc-hcp_midthickness.surf.gii",
            "R.inflated.32k_fs_LR.surf.gii": "hemi-R_desc-hcp_inflated.surf.gii",
            "L.inflated.32k_fs_LR.surf.gii": "hemi-L_desc-hcp_inflated.surf.gii",
            "R.very_inflated.32k_fs_LR.surf.gii": "hemi-R_desc-hcp_vinflated.surf.gii",
            "L.very_inflated.32k_fs_LR.surf.gii": "hemi-L_desc-hcp_vinflated.surf.gii",
            "R.pial.32k_fs_LR.surf.gii": "hemi-R_pial.surf.gii",
            "L.pial.32k_fs_LR.surf.gii": "hemi-L_pial.surf.gii",
            "R.white.32k_fs_LR.surf.gii": "hemi-R_smoothwm.surf.gii",
            "L.white.32k_fs_LR.surf.gii": "hemi-L_smoothwm.surf.gii",
            "R.corrThickness.32k_fs_LR.shape.gii": "hemi-R_thickness.shape.gii",
            "L.corrThickness.32k_fs_LR.shape.gii": "hemi-L_thickness.shape.gii",
            "R.curvature.32k_fs_LR.shape.gii": "hemi-R_curv.shape.gii",
            "L.curvature.32k_fs_LR.shape.gii": "hemi-L_curv.shape.gii",
            "R.sulc.32k_fs_LR.shape.gii": "hemi-R_sulc.shape.gii",
            "L.sulc.32k_fs_LR.shape.gii": "hemi-L_sulc.shape.gii",
        }

        for in_str, out_str in SURFACE_DICT.items():
            surf_orig = os.path.join(fsaverage_dir_orig, f"{sub_id}.{in_str}")
            surf_fmriprep = os.path.join(
                anat_dir_fmriprep,
                f"{sub_ent}_{ses_ent}_space-fsLR_den-32k_{out_str}",
            )
            copy_dictionary[surf_orig] = [surf_fmriprep]

        LOGGER.info("Finished collecting anatomical files")

        # get masks and transforms
        wmmask = os.path.join(anat_dir_orig, f"wm_2mm_{sub_id}_mask_eroded.nii.gz")
        csfmask = os.path.join(anat_dir_orig, f"vent_2mm_{sub_id}_mask_eroded.nii.gz")

        # Collect functional files to copy
        task_dirs_orig = sorted(glob.glob(os.path.join(func_dir_orig, f"{ses_ent}_task-*")))
        task_dirs_orig = [task_dir for task_dir in task_dirs_orig if os.path.isdir(task_dir)]
        task_names = [os.path.basename(task_dir) for task_dir in task_dirs_orig]

        for base_task_name in task_names:
            LOGGER.info(f"Processing {base_task_name}")
            # Names seem to follow ses-X_task-Y_run-Z format.
            found_task_info = re.findall(
                r".*_task-([0-9a-zA-Z]+[a-zA-Z]+)_run-(\d+)",
                base_task_name,
            )
            if len(found_task_info) != 1:
                LOGGER.warning(
                    f"Task name and run number could not be inferred for {base_task_name}. "
                    "Skipping."
                )
                continue

            task_id, run_id = found_task_info[0]
            run_ent = f"run-{run_id}"
            task_ent = f"task-{task_id}"

            task_dir_orig = os.path.join(func_dir_orig, base_task_name)

            # Find original task files
            # This file is the anatomical brain mask downsampled to 2mm3.
            brainmask_orig_temp = os.path.join(task_dir_orig, "brainmask_fs.2.0.nii.gz")

            sbref_orig = os.path.join(task_dir_orig, f"{base_task_name}_SBRef.nii.gz")
            boldref_fmriprep = os.path.join(
                func_dir_fmriprep,
                (
                    f"{sub_ent}_{ses_ent}_{task_ent}_{run_ent}_{volspace_ent}_"
                    f"{RES_ENT}_boldref.nii.gz"
                ),
            )
            copy_dictionary[sbref_orig] = [boldref_fmriprep]

            bold_nifti_orig = os.path.join(task_dir_orig, f"{base_task_name}.nii.gz")
            bold_nifti_fmriprep = os.path.join(
                func_dir_fmriprep,
                (
                    f"{sub_ent}_{ses_ent}_{task_ent}_{run_ent}_"
                    f"{volspace_ent}_{RES_ENT}_desc-preproc_bold.nii.gz"
                ),
            )
            copy_dictionary[bold_nifti_orig] = [bold_nifti_fmriprep]

            bold_cifti_orig = os.path.join(task_dir_orig, f"{base_task_name}_Atlas.dtseries.nii")
            bold_cifti_fmriprep = os.path.join(
                func_dir_fmriprep,
                f"{sub_ent}_{ses_ent}_{task_ent}_{run_ent}_space-fsLR_den-91k_bold.dtseries.nii",
            )
            copy_dictionary[bold_cifti_orig] = [bold_cifti_fmriprep]

            # native_to_t1w_orig = os.path.join(xforms_dir_orig, f"{task_ent}2T1w.nii.gz")
            native_to_t1w_fmriprep = os.path.join(
                func_dir_fmriprep,
                (
                    f"{sub_ent}_{ses_ent}_{task_ent}_{run_ent}_"
                    "from-scanner_to-T1w_mode-image_xfm.txt"
                ),
            )
            copy_dictionary[identity_xfm].append(native_to_t1w_fmriprep)

            # t1w_to_native_orig = os.path.join(xforms_dir_orig, f"T1w2{task_ent}.nii.gz")
            t1w_to_native_fmriprep = os.path.join(
                func_dir_fmriprep,
                (
                    f"{sub_ent}_{ses_ent}_{task_ent}_{run_ent}_"
                    "from-T1w_to-scanner_mode-image_xfm.txt"
                ),
            )
            copy_dictionary[identity_xfm].append(t1w_to_native_fmriprep)

            # Extract metadata for JSON files
            TR = nb.load(bold_nifti_orig).header.get_zooms()[-1]  # repetition time
            bold_nifti_json_dict = {
                "RepetitionTime": float(TR),
                "TaskName": task_id,
            }
            bold_nifti_json_fmriprep = os.path.join(
                func_dir_fmriprep,
                (
                    f"{sub_ent}_{ses_ent}_{task_ent}_{run_ent}_{volspace_ent}_"
                    f"{RES_ENT}_desc-preproc_bold.json"
                ),
            )
            write_json(bold_nifti_json_dict, bold_nifti_json_fmriprep)

            bold_cifti_json_dict = {
                "RepetitionTime": float(TR),
                "TaskName": task_id,
                "grayordinates": "91k",
                "space": "HCP grayordinates",
                "surface": "fsLR",
                "surface_density": "32k",
                "volume": "MNI152NLin6Asym",
            }
            bold_cifti_json_fmriprep = os.path.join(
                func_dir_fmriprep,
                f"{sub_ent}_{ses_ent}_{task_ent}_{run_ent}_space-fsLR_den-91k_bold.dtseries.json",
            )

            write_json(bold_cifti_json_dict, bold_cifti_json_fmriprep)

            # Create confound regressors
            mvreg = pd.read_csv(
                os.path.join(task_dir_orig, "Movement_Regressors.txt"),
                header=None,
                delimiter=r"\s+",
            )

            # Only use the first six columns
            mvreg = mvreg.iloc[:, 0:6]
            mvreg.columns = ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"]

            # convert rotations from degrees to radians
            rot_columns = [c for c in mvreg.columns if c.startswith("rot")]
            for col in rot_columns:
                mvreg[col] = mvreg[col] * np.pi / 180

            # get derivatives of motion columns
            columns = mvreg.columns.tolist()
            for col in columns:
                mvreg[f"{col}_derivative1"] = mvreg[col].diff()

            # get powers
            columns = mvreg.columns.tolist()
            for col in columns:
                mvreg[f"{col}_power2"] = mvreg[col] ** 2

            # Use dummy column for framewise displacement, which will be recalculated by XCP-D.
            mvreg["framewise_displacement"] = 0

            # use masks: brain, csf, and wm mask to extract timeseries
            gsreg = extract_mean_signal(
                mask=brainmask_orig_temp,
                nifti=bold_nifti_orig,
                work_dir=work_dir,
            )
            csfreg = extract_mean_signal(
                mask=csfmask,
                nifti=bold_nifti_orig,
                work_dir=work_dir,
            )
            wmreg = extract_mean_signal(
                mask=wmmask,
                nifti=bold_nifti_orig,
                work_dir=work_dir,
            )
            rsmd = np.loadtxt(os.path.join(task_dir_orig, "Movement_AbsoluteRMS.txt"))

            brainreg = pd.DataFrame(
                {"global_signal": gsreg, "white_matter": wmreg, "csf": csfreg, "rmsd": rsmd}
            )

            # get derivatives and powers
            brainreg["global_signal_derivative1"] = brainreg["global_signal"].diff()
            brainreg["white_matter_derivative1"] = brainreg["white_matter"].diff()
            brainreg["csf_derivative1"] = brainreg["csf"].diff()

            brainreg["global_signal_derivative1_power2"] = (
                brainreg["global_signal_derivative1"] ** 2
            )
            brainreg["global_signal_power2"] = brainreg["global_signal"] ** 2

            brainreg["white_matter_derivative1_power2"] = brainreg["white_matter_derivative1"] ** 2
            brainreg["white_matter_power2"] = brainreg["white_matter"] ** 2

            brainreg["csf_derivative1_power2"] = brainreg["csf_derivative1"] ** 2
            brainreg["csf_power2"] = brainreg["csf"] ** 2

            # Merge the two DataFrames
            regressors = pd.concat([mvreg, brainreg], axis=1)

            # write out the confounds
            regressors_file_base = (
                f"{sub_ent}_{ses_ent}_task-{task_id}_{run_ent}_desc-confounds_timeseries"
            )
            regressors_tsv_fmriprep = os.path.join(
                func_dir_fmriprep,
                f"{regressors_file_base}.tsv",
            )
            regressors.to_csv(regressors_tsv_fmriprep, sep="\t", index=False)

            # NOTE: Is this JSON any good?
            regressors_json_fmriprep = os.path.join(
                func_dir_fmriprep,
                f"{regressors_file_base}.json",
            )
            write_json(bold_cifti_json_dict, regressors_json_fmriprep)

            # Make figures
            figdir = os.path.join(subject_dir_fmriprep, "figures")
            os.makedirs(figdir, exist_ok=True)
            bbref_fig_fmriprep = os.path.join(
                figdir,
                f"{sub_ent}_{ses_ent}_{task_ent}_{run_ent}_desc-bbregister_bold.svg",
            )
            bbref_fig_fmriprep = plot_bbreg(
                fixed_image=t1w_orig,
                moving_image=sbref_orig,
                out_file=bbref_fig_fmriprep,
                contour=ribbon_orig,
            )

            LOGGER.info(f"Finished {base_task_name}")

    LOGGER.info("Finished collecting functional files")

    # Copy ABCD files to fMRIPrep folder
    LOGGER.info("Copying files")
    for file_orig, files_fmriprep in copy_dictionary.items():
        if not isinstance(files_fmriprep, list):
            raise ValueError(
                f"Entry for {file_orig} should be a list, but is a {type(files_fmriprep)}"
            )

        if len(files_fmriprep) > 1:
            LOGGER.warning(f"File used for more than one output: {file_orig}")

        for file_fmriprep in files_fmriprep:
            copy_file(file_orig, file_fmriprep)

    dataset_description_dict = {
        "Name": "ABCD-DCAN",
        "BIDSVersion": "1.4.0",
        "DatasetType": "derivative",
        "GeneratedBy": [
            {
                "Name": "DCAN",
                "Version": "0.0.4",
                "CodeURL": "https://github.com/DCAN-Labs/abcd-hcp-pipeline",
            },
        ],
    }
    dataset_description_fmriprep = os.path.join(out_dir, "dataset_description.json")
    if not os.path.isfile(dataset_description_fmriprep):
        write_json(dataset_description_dict, dataset_description_fmriprep)

    # Write out the mapping from DCAN to fMRIPrep
    scans_dict = {}
    for key, values in copy_dictionary.items():
        for item in values:
            scans_dict[item] = key

    scans_tuple = tuple(scans_dict.items())
    scans_df = pd.DataFrame(scans_tuple, columns=["filename", "source_file"])
    scans_tsv = os.path.join(subject_dir_fmriprep, f"{sub_ent}_scans.tsv")
    scans_df.to_csv(scans_tsv, sep="\t", index=False)
    LOGGER.info("Conversion completed")
