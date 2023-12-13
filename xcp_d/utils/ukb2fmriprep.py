"""Functions to convert preprocessed UK Biobank BOLD data to BIDS derivatives format."""
import glob
import json
import os

import numpy as np
import pandas as pd
from nipype import logging
from nipype.interfaces.fsl.preprocess import ApplyWarp
from niworkflows.interfaces.confounds import NormalizeMotionParams
from pkg_resources import resource_filename as pkgrf
from templateflow.api import get as get_template

from xcp_d.utils.filemanip import ensure_list
from xcp_d.utils.ingestion import copy_files_in_dict, extract_mean_signal, write_json

LOGGER = logging.getLogger("nipype.utils")


def convert_ukb2bids(in_dir, out_dir, participant_ids=None, bids_filters={}):
    """Convert UK Biobank derivatives to BIDS-compliant derivatives.

    Parameters
    ----------
    in_dir : str
        Path to UK Biobank derivatives.
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
    LOGGER.warning("convert_ukb2bids is an experimental function.")
    in_dir = os.path.abspath(in_dir)
    out_dir = os.path.abspath(out_dir)

    if participant_ids is None:
        subject_folders = sorted(glob.glob(os.path.join(in_dir, "*_*_2_0")))
        subject_folders = [
            subject_folder for subject_folder in subject_folders if os.path.isdir(subject_folder)
        ]
        participant_ids = [
            os.path.basename(subject_folder).split("_")[0] for subject_folder in subject_folders
        ]
        all_subject_ids = []
        for subject_id in participant_ids:
            if subject_id not in all_subject_ids:
                all_subject_ids.append(f"sub-{subject_id}")

            participant_ids = all_subject_ids

        if len(participant_ids) == 0:
            raise ValueError(f"No subject found in {in_dir}")

    else:
        participant_ids = ensure_list(participant_ids)

    for subject_id in participant_ids:
        LOGGER.info(f"Converting {subject_id}")
        session_ids = ensure_list(bids_filters.get("bold", {}).get("session", "*"))
        subject_dirs = []
        for session_id in session_ids:
            subject_dir = sorted(glob.glob(os.path.join(in_dir, f"{subject_id}_{session_id}_2_0")))
            subject_dirs += subject_dir

        for subject_dir in subject_dirs:
            session_id = os.path.basename(subject_dir).split("_")[1]
            convert_ukb_to_bids_single_subject(
                in_dir=subject_dirs[0],
                out_dir=out_dir,
                sub_id=subject_id,
                ses_id=session_id,
            )

    return participant_ids


def convert_ukb_to_bids_single_subject(in_dir, out_dir, sub_id, ses_id):
    """Convert UK Biobank derivatives to BIDS-compliant derivatives for a single subject.

    Parameters
    ----------
    in_dir : str
        Path to the subject's UK Biobank derivatives.
    out_dir : str
        Path to the output fMRIPrep-style derivatives folder.
    sub_id : str
        Subject identifier, without "sub-" prefix.
    ses_id : str
        Session identifier, without "ses-" prefix.

    Notes
    -----
    The BOLD and brain mask files are in boldref space, so they must be warped to standard
    (MNI152NLin6Asym) space with FNIRT.
    Since the T1w is in standard space already, we use identity transforms instead of the
    individual transforms available in the DCAN derivatives.
    """
    assert isinstance(in_dir, str)
    assert os.path.isdir(in_dir), f"Folder DNE: {in_dir}"
    assert isinstance(out_dir, str)
    assert isinstance(sub_id, str)
    assert isinstance(ses_id, str)
    subses_ents = f"sub-{sub_id}_ses-{ses_id}"

    task_dir_orig = os.path.join(in_dir, "fMRI", "rfMRI.ica")
    bold_file = os.path.join(task_dir_orig, "filtered_func_data_clean.nii.gz")
    assert os.path.isfile(bold_file), os.listdir(task_dir_orig)
    bold_json = os.path.join(in_dir, "fMRI", "rfMRI.json")
    assert os.path.isfile(bold_json), os.listdir(task_dir_orig)
    boldref_file = os.path.join(in_dir, "fMRI", "rfMRI_SBREF.nii.gz")
    assert os.path.isfile(boldref_file), boldref_file
    brainmask_file = os.path.join(task_dir_orig, "mask.nii.gz")
    assert os.path.isfile(brainmask_file), os.listdir(task_dir_orig)
    t1w = os.path.join(in_dir, "T1", "T1_brain_to_MNI.nii.gz")
    assert os.path.isfile(t1w), os.listdir(in_dir)
    warp_file = os.path.join(task_dir_orig, "reg", "example_func2standard_warp.nii.gz")
    assert os.path.isfile(warp_file), os.listdir(in_dir)

    base_task_ents = f"sub-{sub_id}_ses-{ses_id}_task-rest"
    subject_dir_fmriprep = os.path.join(out_dir, f"sub-{sub_id}", f"ses-{ses_id}")
    anat_dir_fmriprep = os.path.join(subject_dir_fmriprep, "anat")
    func_dir_fmriprep = os.path.join(subject_dir_fmriprep, "func")
    work_dir = os.path.join(subject_dir_fmriprep, "work")
    os.makedirs(anat_dir_fmriprep, exist_ok=True)
    os.makedirs(func_dir_fmriprep, exist_ok=True)
    os.makedirs(work_dir, exist_ok=True)

    create_confounds(
        task_dir_orig,
        func_dir_fmriprep,
        base_task_ents,
        work_dir,
        bold_file,
        brainmask_file,
    )

    dataset_description_fmriprep = os.path.join(out_dir, "dataset_description.json")

    if os.path.isfile(dataset_description_fmriprep):
        LOGGER.info("Converted dataset already exists. Skipping conversion.")
        return

    VOLSPACE = "MNI152NLin6Asym"

    # Warp BOLD, T1w, and brainmask to MNI152NLin6Asym
    template_file = str(get_template(template=VOLSPACE, resolution="02", suffix="T1w", desc=None))

    copy_dictionary = {}

    warp_bold_to_std = ApplyWarp(
        interp="spline",
        output_type="NIFTI_GZ",
        ref_file=template_file,
        in_file=bold_file,
        field_file=warp_file,
    )
    warp_bold_to_std_results = warp_bold_to_std.run()
    bold_nifti_fmriprep = os.path.join(
        func_dir_fmriprep,
        f"{base_task_ents}_space-{VOLSPACE}_desc-preproc_bold.nii.gz",
    )
    copy_dictionary[warp_bold_to_std_results.outputs.out_file] = [bold_nifti_fmriprep]

    # Extract metadata for JSON file
    with open(bold_json, "r") as fo:
        bold_metadata = json.load(fo)

    # Keep only the relevant fields
    keep_keys = [
        "FlipAngle",
        "EchoTime",
        "Manufacturer",
        "ManufacturersModelName",
        "EffectiveEchoSpacing",
        "RepetitionTime",
        "PhaseEncodingDirection",
    ]
    bold_metadata = {k: bold_metadata[k] for k in keep_keys if k in bold_metadata}
    bold_metadata["TaskName"] = "resting state"
    bold_nifti_json_fmriprep = bold_nifti_fmriprep.replace(".nii.gz", ".json")
    write_json(bold_metadata, bold_nifti_json_fmriprep)

    warp_brainmask_to_std = ApplyWarp(
        interp="nn",
        output_type="NIFTI_GZ",
        ref_file=template_file,
        in_file=brainmask_file,
        field_file=warp_file,
    )
    warp_brainmask_to_std_results = warp_brainmask_to_std.run()
    copy_dictionary[warp_brainmask_to_std_results.outputs.out_file] = [
        os.path.join(
            func_dir_fmriprep,
            f"{base_task_ents}_space-{VOLSPACE}_desc-brain_mask.nii.gz",
        )
    ]
    # Use the brain mask as the anatomical brain mask too.
    copy_dictionary[warp_brainmask_to_std_results.outputs.out_file].append(
        os.path.join(
            anat_dir_fmriprep,
            f"{subses_ents}_space-{VOLSPACE}_desc-brain_mask.nii.gz",
        )
    )
    # Use the brain mask as the "aparcaseg" dseg too.
    copy_dictionary[warp_brainmask_to_std_results.outputs.out_file].append(
        os.path.join(
            anat_dir_fmriprep,
            f"{subses_ents}_space-{VOLSPACE}_desc-aparcaseg_dseg.nii.gz",
        )
    )

    # Warp the sbref file to MNI space.
    warp_boldref_to_std = ApplyWarp(
        interp="spline",
        output_type="NIFTI_GZ",
        ref_file=template_file,
        in_file=boldref_file,
        field_file=warp_file,
    )
    warp_boldref_to_std_results = warp_boldref_to_std.run()
    boldref_nifti_fmriprep = os.path.join(
        func_dir_fmriprep,
        f"{base_task_ents}_space-{VOLSPACE}_boldref.nii.gz",
    )
    copy_dictionary[warp_boldref_to_std_results.outputs.out_file] = [boldref_nifti_fmriprep]

    # The MNI-space anatomical image.
    copy_dictionary[t1w] = [
        os.path.join(anat_dir_fmriprep, f"{subses_ents}_space-{VOLSPACE}_desc-preproc_T1w.nii.gz")
    ]

    # The identity xform is used in place of any actual ones.
    identity_xfm = pkgrf("xcp_d", "/data/transform/itkIdentityTransform.txt")
    copy_dictionary[identity_xfm] = []

    t1w_to_template_fmriprep = os.path.join(
        anat_dir_fmriprep,
        f"{subses_ents}_from-T1w_to-{VOLSPACE}_mode-image_xfm.txt",
    )
    copy_dictionary[identity_xfm].append(t1w_to_template_fmriprep)

    template_to_t1w_fmriprep = os.path.join(
        anat_dir_fmriprep,
        f"{subses_ents}_from-{VOLSPACE}_to-T1w_mode-image_xfm.txt",
    )
    copy_dictionary[identity_xfm].append(template_to_t1w_fmriprep)

    LOGGER.info("Finished collecting functional files")

    # Copy UK Biobank files to fMRIPrep folder
    LOGGER.info("Copying files")
    copy_files_in_dict(copy_dictionary)
    LOGGER.info("Finished copying files")

    # Write the dataset description out last
    dataset_description_dict = {
        "Name": "UK Biobank",
        "DatasetType": "derivative",
        "GeneratedBy": [
            {
                "Name": "UK Biobank",
                "Version": "unknown",
            },
        ],
    }

    if not os.path.isfile(dataset_description_fmriprep):
        write_json(dataset_description_dict, dataset_description_fmriprep)

    # Write out the mapping from UK Biobank to fMRIPrep
    scans_dict = {}
    for key, values in copy_dictionary.items():
        for item in values:
            scans_dict[item] = key

    scans_tuple = tuple(scans_dict.items())
    scans_df = pd.DataFrame(scans_tuple, columns=["filename", "source_file"])
    scans_tsv = os.path.join(subject_dir_fmriprep, f"{subses_ents}_scans.tsv")
    scans_df.to_csv(scans_tsv, sep="\t", index=False)
    LOGGER.info("Conversion completed")


def create_confounds(
    task_dir_orig,
    func_dir_fmriprep,
    base_task_ents,
    work_dir,
    bold_file,
    brainmask_file,
):
    """Create motion confounds file."""
    import os

    import pandas as pd

    # Collect motion confounds and their expansions
    par_file = os.path.join(task_dir_orig, "mc", "prefiltered_func_data_mcf.par")
    assert os.path.isfile(par_file), os.listdir(os.path.join(task_dir_orig, "mc"))

    normalize_motion = NormalizeMotionParams(format="FSL", in_file=par_file)
    normalize_motion_results = normalize_motion.run()
    motion_data = np.loadtxt(normalize_motion_results.outputs.out_file)
    confounds_df = pd.DataFrame(
        data=motion_data,
        columns=["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"],
    )

    columns = confounds_df.columns.tolist()
    for col in columns:
        new_col = f"{col}_derivative1"
        confounds_df[new_col] = confounds_df[col].diff()

    columns = confounds_df.columns.tolist()
    for col in columns:
        new_col = f"{col}_power2"
        confounds_df[new_col] = confounds_df[col] ** 2

    # Use dummy column for framewise displacement, which will be recalculated by XCP-D.
    confounds_df["framewise_displacement"] = 0

    # Add RMS
    rmsd_file = os.path.join(task_dir_orig, "mc", "prefiltered_func_data_mcf_abs.rms")
    rmsd = np.loadtxt(rmsd_file)
    confounds_df["rmsd"] = rmsd

    # Collect global signal (the primary regressor used for denoising UKB data,
    # since the data are already denoised).
    confounds_df["global_signal"] = extract_mean_signal(
        mask=brainmask_file,
        nifti=bold_file,
        work_dir=work_dir,
    )
    # get derivatives and powers
    confounds_df["global_signal_derivative1"] = confounds_df["global_signal"].diff()
    confounds_df["global_signal_derivative1_power2"] = (
        confounds_df["global_signal_derivative1"] ** 2
    )
    confounds_df["global_signal_power2"] = confounds_df["global_signal"] ** 2

    # write out the confounds
    regressors_tsv_fmriprep = os.path.join(
        func_dir_fmriprep,
        f"{base_task_ents}_desc-confounds_timeseries.tsv",
    )
    confounds_df.to_csv(regressors_tsv_fmriprep, sep="\t", index=False)

    # NOTE: Is this JSON any good?
    regressors_json_fmriprep = os.path.join(
        func_dir_fmriprep,
        f"{base_task_ents}_desc-confounds_timeseries.json",
    )
    confounds_dict = {col: {"Description": ""} for col in confounds_df.columns}
    with open(regressors_json_fmriprep, "w") as fo:
        json.dump(confounds_dict, fo, sort_keys=True, indent=4)