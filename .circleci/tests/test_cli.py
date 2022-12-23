"""Command-line interface tests."""
import os

import pytest

from xcp_d.cli.run import main


@pytest.mark.skip(reason="Not set up yet.")
def test_ds001491_nifti():
    """Run xcp_d on ds001491 fMRIPrep derivatives, with nifti options."""
    data_dir = "/bids-input/data/ds001419-fmriprep"
    out_dir = "/tmp/data/test_ds001491_nifti"
    derivatives_dir = os.path.join(out_dir, "derivatives")
    parameters = [
        data_dir,
        derivatives_dir,
        "participant",
        f"-w={os.path.join(derivatives_dir, 'work')}",
        "--nthreads=2",
        "--omp-nthreads=2",
        "--bids-filter-file=data/ds001419-fmriprep_nifti_filter.json",
        "--nuisance-regressors=aroma_gsr",
        "--despike",
        "--dummytime=8",
        "--fd-thresh=0.04",
        "--head_radius=40",
        "--smoothing=6",
        "-vvv",
        "--motion-filter-type=notch",
        "--band-stop-min=12",
        "--band-stop-max=18",
        "--warp-surfaces-native2std",
        "--nthreads=1",
        "--omp-nthreads=1",
    ]
    main(parameters)


@pytest.mark.skip(reason="Not set up yet.")
def test_ds001491_cifti():
    """Run xcp_d on ds001491 fMRIPrep derivatives, with cifti options."""
    data_dir = "/bids-input/data/ds001419-fmriprep"
    out_dir = "/tmp/data/test_ds001491_cifti"
    derivatives_dir = os.path.join(out_dir, "derivatives")
    parameters = [
        data_dir,
        derivatives_dir,
        "participant",
        f"-w={os.path.join(derivatives_dir, 'work')}",
        "--nthreads=2",
        "--omp-nthreads=2",
        "--bids-filter-file=data/ds001419-fmriprep_cifti_filter.json",
        "--despike",
        "--head_radius=40",
        "--smoothing=6",
        "-vvv",
        "--motion-filter-type=lp",
        "--band-stop-min=6",
        "--warp-surfaces-native2std",
        "--cifti",
        "--combineruns",
        "--dcan-qc",
        "--dummy-scans=auto",
        "--fd-thresh=0.04",
    ]
    main(parameters)


@pytest.mark.skip(reason="Not set up yet.")
def test_fmriprep_without_freesurfer():
    """Run xcp_d on fMRIPrep derivatives without FreeSurfer, with nifti options."""
    data_dir = "/bids-input/data/fmriprep_without_freesurfer"
    out_dir = "/tmp/data/test_fmriprep_without_freesurfer"
    derivatives_dir = os.path.join(out_dir, "derivatives")
    parameters = [
        data_dir,
        derivatives_dir,
        "participant",
        f"-w={os.path.join(derivatives_dir, 'work')}",
        "--nthreads=2",
        "--omp-nthreads=2",
        "--despike",
        "--head_radius=40",
        "--smoothing=6",
        "-f=100",
        "-vv",
        "--nuisance-regressors=27P",
        "--disable-bandpass-filter",
        "--dcan-qc",
        "--dummy-scans=1",
    ]
    main(parameters)
