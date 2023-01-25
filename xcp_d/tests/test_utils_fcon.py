"""Tests for the xcp_d.utils.fcon module."""
import os

import pandas as pd
import pytest
import numpy as np

from xcp_d.tests.utils import chdir
from xcp_d.utils import fcon


@pytest.mark.skip(reason="Not sure how to deal with non-sequential node labels yet.")
def test_extract_timeseries_funct(fmriprep_with_freesurfer_data, tmp_path_factory):
    """Check the output of extract_timeseries_funct."""
    tmpdir = tmp_path_factory.mktemp("test_extract_timeseries_funct")

    nifti_file = fmriprep_with_freesurfer_data["nifti_file"]
    mask_file = fmriprep_with_freesurfer_data["brain_mask_file"]
    atlas_file = fmriprep_with_freesurfer_data["aparcaseg"]
    node_labels_file = fmriprep_with_freesurfer_data["aparcaseg_node_labels"]

    with chdir(tmpdir):
        ts_file = fcon.extract_timeseries_funct(
            nifti_file,
            mask_file,
            atlas_file,
            node_labels_file,
        )

    assert os.path.isfile(ts_file)
    df = pd.read_table(ts_file)
    assert df.shape == (60, 1374)


def test_compute_functional_connectivity(tmp_path_factory):
    """Ensure that compute_functional_connectivity calculates correlations correctly."""
    tmpdir = tmp_path_factory.mktemp("test_compute_functional_connectivity")

    n_nodes, n_timepoints = 10, 1000
    ts_array = np.random.random((n_timepoints, n_nodes))

    # Replace some nodes with all zeros, all NaNs
    ts_array[:, 0] = 0
    ts_array[:, 1] = np.nan

    ts_df = pd.DataFrame(
        columns=list("abcdefghij"),
        data=ts_array,
    )
    ts_file = os.path.join(tmpdir, "timeseries.tsv")
    ts_df.to_csv(ts_file, sep="\t", index=False)

    with chdir(tmpdir):
        corr_file = fcon.compute_functional_connectivity(ts_file)

    assert os.path.isfile(corr_file)
    corr_df = pd.read_table(corr_file, index_col="Node")
    assert corr_df.shape == (n_nodes, n_nodes)
    assert np.isnan(corr_df.loc["a", "a"])
    assert np.isnan(corr_df.loc["b", "b"])
    assert all(np.isnan(corr_df.loc["a", :]))
    assert all(np.isnan(corr_df.loc["b", :]))
    assert corr_df.loc["c", "c"] == 1
    assert not np.isnan(corr_df.loc["c", "d"])
