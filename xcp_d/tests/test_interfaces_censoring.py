"""Tests for framewise displacement calculation."""
import os

import numpy as np
import pandas as pd

from xcp_d.interfaces import censoring


def test_generate_confounds(fmriprep_with_freesurfer_data, tmp_path_factory):
    """Check results."""
    tmpdir = tmp_path_factory.mktemp("test_generate_confounds")
    in_file = fmriprep_with_freesurfer_data["nifti_file"]
    confounds_file = fmriprep_with_freesurfer_data["confounds_file"]
    confounds_json = fmriprep_with_freesurfer_data["confounds_json"]

    df = pd.read_table(confounds_file)

    # Replace confounds tsv values with values that should be omitted
    df.loc[1:3, "trans_x"] = [6, 8, 9]
    df.loc[4:6, "trans_y"] = [7, 8, 9]
    df.loc[7:9, "trans_z"] = [12, 8, 9]

    # Rename with same convention as initial confounds tsv
    confounds_tsv = os.path.join(tmpdir, "edited_confounds.tsv")
    df.to_csv(confounds_tsv, sep="\t", index=False, header=True)

    # Run workflow
    interface = censoring.GenerateConfounds(
        in_file=in_file,
        params="24P",
        TR=0.8,
        fd_thresh=0.3,
        head_radius=50,
        fmriprep_confounds_file=confounds_tsv,
        fmriprep_confounds_json=confounds_json,
        custom_confounds_file=None,
        motion_filter_type=None,
        motion_filter_order=4,
        band_stop_min=0,
        band_stop_max=0,
    )
    results = interface.run(cwd=tmpdir)

    assert os.path.isfile(results.outputs.filtered_confounds_file)
    assert os.path.isfile(results.outputs.confounds_file)
    assert os.path.isfile(results.outputs.motion_file)
    assert os.path.isfile(results.outputs.temporal_mask)


def test_random_censor(tmp_path_factory):
    """Test RandomCensor."""
    tmpdir = tmp_path_factory.mktemp("test_random_censor")
    n_volumes, n_outliers = 500, 100
    exact_scans = [100, 200, 300, 400]

    outliers_arr = np.zeros(n_volumes, dtype=int)
    rng = np.random.default_rng(0)
    outlier_idx = rng.choice(np.arange(n_volumes, dtype=int), size=n_outliers, replace=False)
    outliers_arr[outlier_idx] = 1
    temporal_mask_df = pd.DataFrame(data=outliers_arr, columns=["framewise_displacement"])
    original_temporal_mask = os.path.join(tmpdir, "orig_tmask.tsv")
    temporal_mask_df.to_csv(original_temporal_mask, index=False, sep="\t")

    # Run the RandomCensor interface without any exact_scans.
    interface = censoring.RandomCensor(
        temporal_mask_metadata={},
        temporal_mask=original_temporal_mask,
        random_seed=0,
    )
    results = interface.run(cwd=tmpdir)
    assert results.outputs.temporal_mask == original_temporal_mask  # same file as input
    assert isinstance(results.outputs.temporal_mask_metadata, dict)

    # Run the interface with exact_scans
    interface = censoring.RandomCensor(
        temporal_mask_metadata={},
        temporal_mask=original_temporal_mask,
        exact_scans=exact_scans,
        random_seed=0,
    )
    results = interface.run(cwd=tmpdir)
    assert os.path.isfile(results.outputs.temporal_mask)
    assert isinstance(results.outputs.temporal_mask_metadata, dict)
    new_temporal_mask_df = pd.read_table(results.outputs.temporal_mask)
    for exact_scan in exact_scans:
        exact_scan_col = f"exact_{exact_scan}"
        assert exact_scan_col in new_temporal_mask_df.columns
        assert new_temporal_mask_df[exact_scan_col].sum() == n_volumes - (n_outliers + exact_scan)
