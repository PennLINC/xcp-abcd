"""Tests for the xcp_d.workflows.anatomical module."""
import os
import shutil

from xcp_d.tests.utils import get_nodes
from xcp_d.workflows import anatomical


def test_warp_anats_to_template_wf(fmriprep_with_freesurfer_data, tmp_path_factory):
    """Test xcp_d.workflows.anatomical.init_warp_anats_to_template_wf."""
    tmpdir = tmp_path_factory.mktemp("test_nifti_conn")

    t1w_to_template_xform = fmriprep_with_freesurfer_data["t1w_to_template_xform"]
    t1w = fmriprep_with_freesurfer_data["t1w"]
    t1seg = fmriprep_with_freesurfer_data["t1seg"]
    t2w = os.path.join(tmpdir, "sub-01_desc-preproc_T2w.nii.gz")  # pretend t1w is t2w
    shutil.copyfile(t1w, t2w)

    wf = anatomical.init_warp_anats_to_template_wf(
        output_dir=tmpdir,
        input_type="fmriprep",
        t2w_available=True,
        target_space="MNI152NLin2009cAsym",
        omp_nthreads=1,
        mem_gb=0.1,
        name="warp_anats_to_template_wf",
    )
    wf.inputs.inputnode.t1w_to_template = t1w_to_template_xform
    wf.inputs.inputnode.t1w = t1w
    wf.inputs.inputnode.t1seg = t1seg
    wf.inputs.inputnode.t2w = t2w
    wf.base_dir = tmpdir
    wf_res = wf.run()
    wf_nodes = get_nodes(wf_res)

    out_anat_dir = os.path.join(tmpdir, "xcp_d", "sub-01", "anat")
    out_t1w = wf_nodes["warp_anats_to_template_wf.ds_t1w_std"].get_output("out_file")
    assert os.path.isfile(out_t1w), os.listdir(out_anat_dir)

    out_t2w = wf_nodes["warp_anats_to_template_wf.ds_t2w_std"].get_output("out_file")
    assert os.path.isfile(out_t2w), os.listdir(out_anat_dir)

    out_t1seg = wf_nodes["warp_anats_to_template_wf.ds_t1seg_std"].get_output("out_file")
    assert os.path.isfile(out_t1seg), os.listdir(out_anat_dir)
