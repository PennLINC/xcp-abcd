# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Workflows for post-processing CIFTI-format BOLD data."""
from nipype import logging
from nipype.interfaces import utility as niu
from nipype.pipeline import engine as pe
from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from num2words import num2words

from xcp_d import config
from xcp_d.interfaces.utils import ConvertTo32
from xcp_d.utils.confounds import get_custom_confounds
from xcp_d.utils.doc import fill_doc
from xcp_d.utils.utils import _create_mem_gb
from xcp_d.workflows.connectivity import init_functional_connectivity_cifti_wf
from xcp_d.workflows.execsummary import init_execsummary_functional_plots_wf
from xcp_d.workflows.outputs import init_postproc_derivatives_wf
from xcp_d.workflows.plotting import init_qc_report_wf
from xcp_d.workflows.postprocessing import (
    init_denoise_bold_wf,
    init_despike_wf,
    init_prepare_confounds_wf,
)
from xcp_d.workflows.restingstate import init_alff_wf, init_reho_cifti_wf

LOGGER = logging.getLogger("nipype.workflow")


@fill_doc
def init_postprocess_cifti_wf(
    bold_file,
    head_radius,
    run_data,
    t1w_available,
    t2w_available,
    n_runs,
    exact_scans,
    name="cifti_postprocess_wf",
):
    """Organize the cifti processing workflow.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            import os

            from xcp_d.tests.tests import mock_config
            from xcp_d import config
            from xcp_d.utils.bids import collect_data, collect_run_data
            from xcp_d.workflows.cifti import init_postprocess_cifti_wf

            with mock_config():
                bold_file = str(
                    config.execution.fmri_dir / "sub-01" / "func" /
                    "sub-01_task-imagery_run-01_space-fsLR_den-91k_bold.dtseries.nii"
                )

                run_data = collect_run_data(
                    layout=layout,
                    input_type="fmriprep",
                    bold_file=bold_file,
                    cifti=True,
                )

                wf = init_postprocess_cifti_wf(
                    bold_file=bold_file,
                    head_radius=50.,
                    run_data=run_data,
                    t1w_available=True,
                    t2w_available=True,
                    n_runs=1,
                    exact_scans=[],
                    name="cifti_postprocess_wf",
                )

    Parameters
    ----------
    bold_file
    %(head_radius)s
        This will already be estimated before this workflow.
    run_data : dict
    t1w_available
    t2w_available
    n_runs
        Number of runs being postprocessed by XCP-D.
        This is just used for the boilerplate, as this workflow only posprocesses one run.
    %(exact_scans)s
    %(name)s
        Default is "cifti_postprocess_wf".

    Inputs
    ------
    bold_file
        CIFTI file
    %(boldref)s
    %(custom_confounds_file)s
    t1w
        Preprocessed T1w image, warped to standard space.
        Fed from the subject workflow.
    t2w
        Preprocessed T2w image, warped to standard space.
        Fed from the subject workflow.
    %(fmriprep_confounds_file)s
    fmriprep_confounds_json
    %(dummy_scans)s

    Outputs
    -------
    %(name_source)s
    preprocessed_bold : :obj:`str`
        The preprocessed BOLD file, after dummy scan removal.
    %(fmriprep_confounds_file)s
        After dummy scan removal.
    %(filtered_motion)s
    %(temporal_mask)s
    %(denoised_interpolated_bold)s
    %(censored_denoised_bold)s
    %(smoothed_denoised_bold)s
    %(boldref)s
    bold_mask
        This will not be defined.
    %(timeseries)s
    %(timeseries_ciftis)s

    References
    ----------
    .. footbibliography::
    """
    workflow = Workflow(name=name)

    bandpass_filter = config.workflow.bandpass_filter
    custom_confounds_folder = config.execution.custom_confounds
    dummy_scans = config.workflow.dummy_scans
    despike = config.workflow.despike
    atlases = config.execution.atlases
    omp_nthreads = config.nipype.omp_nthreads

    TR = run_data["bold_metadata"]["RepetitionTime"]

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "bold_file",
                "boldref",
                "custom_confounds_file",
                "t1w",
                "t2w",
                "fmriprep_confounds_file",
                "fmriprep_confounds_json",
                "dummy_scans",
                # if parcellation is performed
                "atlases",
                "atlas_files",
                "atlas_labels_files",
                "parcellated_atlas_files",
            ],
        ),
        name="inputnode",
    )

    inputnode.inputs.bold_file = bold_file
    inputnode.inputs.boldref = run_data["boldref"]
    inputnode.inputs.fmriprep_confounds_file = run_data["confounds"]
    inputnode.inputs.fmriprep_confounds_json = run_data["confounds_json"]
    inputnode.inputs.dummy_scans = dummy_scans
    inputnode.inputs.atlases = atlases

    # Load custom confounds
    # We need to run this function directly to access information in the confounds that is
    # used for the boilerplate.
    custom_confounds_file = get_custom_confounds(
        custom_confounds_folder,
        run_data["confounds"],
    )

    workflow = Workflow(name=name)

    workflow.__desc__ = f"""\

For each of the {num2words(n_runs)} BOLD runs found per subject (across all tasks and sessions),
the following post-processing was performed.

"""

    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "name_source",
                "preprocessed_bold",
                "fmriprep_confounds_file",
                "filtered_motion",
                "temporal_mask",
                "denoised_interpolated_bold",
                "censored_denoised_bold",
                "smoothed_denoised_bold",
                "boldref",
                "bold_mask",  # will not be defined
                # if parcellation is performed
                "timeseries",
                "timeseries_ciftis",
            ],
        ),
        name="outputnode",
    )

    mem_gbx = _create_mem_gb(bold_file)

    downcast_data = pe.Node(
        ConvertTo32(),
        name="downcast_data",
        mem_gb=mem_gbx["timeseries"],
        n_procs=omp_nthreads,
    )

    workflow.connect([
        (inputnode, outputnode, [
            ("bold_file", "name_source"),
            ("boldref", "boldref"),
        ]),
        (inputnode, downcast_data, [("bold_file", "bold_file")]),
    ])  # fmt:skip

    prepare_confounds_wf = init_prepare_confounds_wf(
        TR=TR,
        exact_scans=exact_scans,
        head_radius=head_radius,
        custom_confounds_file=custom_confounds_file,
    )

    workflow.connect([
        (inputnode, prepare_confounds_wf, [
            ("bold_file", "inputnode.name_source"),
            ("fmriprep_confounds_file", "inputnode.fmriprep_confounds_file"),
            ("fmriprep_confounds_json", "inputnode.fmriprep_confounds_json"),
        ]),
        (downcast_data, prepare_confounds_wf, [
            ("bold_file", "inputnode.preprocessed_bold"),
        ]),
        (prepare_confounds_wf, outputnode, [
            ("outputnode.fmriprep_confounds_file", "fmriprep_confounds_file"),
            ("outputnode.preprocessed_bold", "preprocessed_bold"),
        ]),
    ])  # fmt:skip

    denoise_bold_wf = init_denoise_bold_wf(TR=TR, mem_gb=mem_gbx)

    workflow.connect([
        (prepare_confounds_wf, denoise_bold_wf, [
            ("outputnode.temporal_mask", "inputnode.temporal_mask"),
            ("outputnode.confounds_file", "inputnode.confounds_file"),
        ]),
    ])  # fmt:skip

    if despike:
        despike_wf = init_despike_wf(TR=TR)

        workflow.connect([
            (prepare_confounds_wf, despike_wf, [
                ("outputnode.preprocessed_bold", "inputnode.bold_file"),
            ]),
            (despike_wf, denoise_bold_wf, [
                ("outputnode.bold_file", "inputnode.preprocessed_bold"),
            ]),
        ])  # fmt:skip

    else:
        workflow.connect([
            (prepare_confounds_wf, denoise_bold_wf, [
                ("outputnode.preprocessed_bold", "inputnode.preprocessed_bold"),
            ]),
        ])  # fmt:skip

    if bandpass_filter:
        alff_wf = init_alff_wf(name_source=bold_file, TR=TR, mem_gb=mem_gbx)

        workflow.connect([
            (prepare_confounds_wf, alff_wf, [
                ("outputnode.temporal_mask", "inputnode.temporal_mask"),
            ]),
            (denoise_bold_wf, alff_wf, [
                ("outputnode.censored_denoised_bold", "inputnode.denoised_bold"),
                ("outputnode.smoothed_denoised_bold", "inputnode.smoothed_bold"),
            ]),
        ])  # fmt:skip

    reho_wf = init_reho_cifti_wf(name_source=bold_file, mem_gb=mem_gbx)

    workflow.connect([
        (denoise_bold_wf, reho_wf, [
            ("outputnode.censored_denoised_bold", "inputnode.denoised_bold"),
        ]),
    ])  # fmt:skip

    qc_report_wf = init_qc_report_wf(
        TR=TR,
        head_radius=head_radius,
        name="qc_report_wf",
    )

    workflow.connect([
        (inputnode, qc_report_wf, [("bold_file", "inputnode.name_source")]),
        (prepare_confounds_wf, qc_report_wf, [
            ("outputnode.preprocessed_bold", "inputnode.preprocessed_bold"),
            ("outputnode.dummy_scans", "inputnode.dummy_scans"),
            ("outputnode.fmriprep_confounds_file", "inputnode.fmriprep_confounds_file"),
            ("outputnode.temporal_mask", "inputnode.temporal_mask"),
            ("outputnode.filtered_motion", "inputnode.filtered_motion"),
        ]),
        (denoise_bold_wf, qc_report_wf, [
            ("outputnode.denoised_interpolated_bold", "inputnode.denoised_interpolated_bold"),
            ("outputnode.censored_denoised_bold", "inputnode.censored_denoised_bold"),
        ]),
    ])  # fmt:skip

    postproc_derivatives_wf = init_postproc_derivatives_wf(
        name_source=bold_file,
        source_metadata=run_data["bold_metadata"],
        exact_scans=exact_scans,
        custom_confounds_file=custom_confounds_file,
    )

    workflow.connect([
        (inputnode, postproc_derivatives_wf, [
            ("fmriprep_confounds_file", "inputnode.fmriprep_confounds_file"),
            ("atlas_files", "inputnode.atlas_files"),
        ]),
        (denoise_bold_wf, postproc_derivatives_wf, [
            ("outputnode.denoised_interpolated_bold", "inputnode.denoised_interpolated_bold"),
            ("outputnode.censored_denoised_bold", "inputnode.censored_denoised_bold"),
            ("outputnode.smoothed_denoised_bold", "inputnode.smoothed_denoised_bold"),
        ]),
        (qc_report_wf, postproc_derivatives_wf, [("outputnode.qc_file", "inputnode.qc_file")]),
        (prepare_confounds_wf, postproc_derivatives_wf, [
            ("outputnode.confounds_file", "inputnode.confounds_file"),
            ("outputnode.confounds_metadata", "inputnode.confounds_metadata"),
            ("outputnode.filtered_motion", "inputnode.filtered_motion"),
            ("outputnode.motion_metadata", "inputnode.motion_metadata"),
            ("outputnode.temporal_mask", "inputnode.temporal_mask"),
            ("outputnode.temporal_mask_metadata", "inputnode.temporal_mask_metadata"),
        ]),
        (reho_wf, postproc_derivatives_wf, [("outputnode.reho", "inputnode.reho")]),
        (postproc_derivatives_wf, outputnode, [
            ("outputnode.filtered_motion", "filtered_motion"),
            ("outputnode.temporal_mask", "temporal_mask"),
            ("outputnode.denoised_interpolated_bold", "denoised_interpolated_bold"),
            ("outputnode.censored_denoised_bold", "censored_denoised_bold"),
            ("outputnode.smoothed_denoised_bold", "smoothed_denoised_bold"),
            ("outputnode.timeseries", "timeseries"),
            ("outputnode.timeseries_ciftis", "timeseries_ciftis"),
        ]),
    ])  # fmt:skip

    if bandpass_filter:
        workflow.connect([
            (alff_wf, postproc_derivatives_wf, [
                ("outputnode.alff", "inputnode.alff"),
                ("outputnode.smoothed_alff", "inputnode.smoothed_alff"),
            ]),
        ])  # fmt:skip

    if atlases:
        connectivity_wf = init_functional_connectivity_cifti_wf(mem_gb=mem_gbx)

        workflow.connect([
            (inputnode, connectivity_wf, [
                ("bold_file", "inputnode.name_source"),
                ("atlases", "inputnode.atlases"),
                ("atlas_files", "inputnode.atlas_files"),
                ("atlas_labels_files", "inputnode.atlas_labels_files"),
                ("parcellated_atlas_files", "inputnode.parcellated_atlas_files"),
            ]),
            (prepare_confounds_wf, connectivity_wf, [
                ("outputnode.temporal_mask", "inputnode.temporal_mask"),
            ]),
            (denoise_bold_wf, connectivity_wf, [
                ("outputnode.censored_denoised_bold", "inputnode.denoised_bold"),
            ]),
            (reho_wf, connectivity_wf, [("outputnode.reho", "inputnode.reho")]),
            (connectivity_wf, postproc_derivatives_wf, [
                ("outputnode.coverage_ciftis", "inputnode.coverage_ciftis"),
                ("outputnode.timeseries_ciftis", "inputnode.timeseries_ciftis"),
                ("outputnode.correlation_ciftis", "inputnode.correlation_ciftis"),
                ("outputnode.correlation_ciftis_exact", "inputnode.correlation_ciftis_exact"),
                ("outputnode.coverage", "inputnode.coverage"),
                ("outputnode.timeseries", "inputnode.timeseries"),
                ("outputnode.correlations", "inputnode.correlations"),
                ("outputnode.correlations_exact", "inputnode.correlations_exact"),
                ("outputnode.parcellated_reho", "inputnode.parcellated_reho"),
            ]),
        ])  # fmt:skip

        if bandpass_filter:
            workflow.connect([
                (alff_wf, connectivity_wf, [("outputnode.alff", "inputnode.alff")]),
                (connectivity_wf, postproc_derivatives_wf, [
                    ("outputnode.parcellated_alff", "inputnode.parcellated_alff"),
                ]),
            ])  # fmt:skip

    # executive summary workflow
    execsummary_functional_plots_wf = init_execsummary_functional_plots_wf(
        preproc_nifti=run_data["nifti_file"],
        t1w_available=t1w_available,
        t2w_available=t2w_available,
        mem_gb=mem_gbx,
    )

    workflow.connect([
        # Use inputnode for executive summary instead of downcast_data because T1w is name source.
        (inputnode, execsummary_functional_plots_wf, [
            ("boldref", "inputnode.boldref"),
            ("t1w", "inputnode.t1w"),
            ("t2w", "inputnode.t2w"),
        ]),
    ])  # fmt:skip

    return workflow
