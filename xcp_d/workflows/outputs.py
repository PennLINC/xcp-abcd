# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Workflows for collecting and saving xcp_d outputs."""
from nipype.interfaces import utility as niu
from nipype.pipeline import engine as pe
from niworkflows.engine.workflows import LiterateWorkflow as Workflow

from xcp_d.interfaces.bids import DerivativesDataSink
from xcp_d.interfaces.utils import FilterUndefined
from xcp_d.utils.bids import (
    _make_custom_uri,
    _make_preproc_uri,
    _make_xcpd_uri,
    get_entity,
)
from xcp_d.utils.doc import fill_doc
from xcp_d.utils.utils import _make_dictionary


@fill_doc
def init_copy_inputs_to_outputs_wf(output_dir, name="copy_inputs_to_outputs_wf"):
    """Copy files from the preprocessing derivatives to the output folder, with no modifications.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from xcp_d.workflows.outputs import init_copy_inputs_to_outputs_wf

            wf = init_copy_inputs_to_outputs_wf(
                output_dir=".",
                name="copy_inputs_to_outputs_wf",
            )

    Parameters
    ----------
    %(output_dir)s
    %(name)s
        Default is "copy_inputs_to_outputs_wf".

    Inputs
    ------
    lh_pial_surf
    rh_pial_surf
    lh_wm_surf
    rh_wm_surf
    sulcal_depth
    sulcal_curv
    cortical_thickness
    cortical_thickness_corr
    myelin
    myelin_smoothed
    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "lh_pial_surf",
                "rh_pial_surf",
                "lh_wm_surf",
                "rh_wm_surf",
                "sulcal_depth",
                "sulcal_curv",
                "cortical_thickness",
                "cortical_thickness_corr",
                "myelin",
                "myelin_smoothed",
            ],
        ),
        name="inputnode",
    )

    # Place the surfaces in a single node.
    collect_files = pe.Node(
        niu.Merge(10),
        name="collect_files",
    )
    # fmt:off
    workflow.connect([
        (inputnode, collect_files, [
            # fsLR-space surface mesh files
            ("lh_pial_surf", "in1"),
            ("rh_pial_surf", "in2"),
            ("lh_wm_surf", "in3"),
            ("rh_wm_surf", "in4"),
            # fsLR-space surface shape files
            ("sulcal_depth", "in5"),
            ("sulcal_curv", "in6"),
            ("cortical_thickness", "in7"),
            ("cortical_thickness_corr", "in8"),
            ("myelin", "in9"),
            ("myelin_smoothed", "in10"),
        ]),
    ])
    # fmt:on

    filter_out_undefined = pe.Node(
        FilterUndefined(),
        name="filter_out_undefined",
    )
    workflow.connect([(collect_files, filter_out_undefined, [("out", "inlist")])])

    ds_copied_outputs = pe.MapNode(
        DerivativesDataSink(
            base_directory=output_dir,
            check_hdr=False,
        ),
        name="ds_copied_outputs",
        run_without_submitting=True,
        mem_gb=1,
        iterfield=["in_file", "source_file"],
    )
    # fmt:off
    workflow.connect([
        (filter_out_undefined, ds_copied_outputs, [
            ("outlist", "in_file"),
            ("outlist", "source_file"),
        ]),
    ])
    # fmt:on

    return workflow


@fill_doc
def init_postproc_derivatives_wf(
    name_source,
    source_metadata,
    fmri_dir,
    bandpass_filter,
    low_pass,
    high_pass,
    bpf_order,
    fd_thresh,
    motion_filter_type,
    smoothing,
    params,
    exact_scans,
    atlases,
    cifti,
    dcan_qc,
    output_dir,
    custom_confounds_file,
    name="postproc_derivatives_wf",
):
    """Write out the xcp_d derivatives in BIDS format.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from xcp_d.workflows.outputs import init_postproc_derivatives_wf

            wf = init_postproc_derivatives_wf(
                name_source="/path/to/file.nii.gz",
                source_metadata={},
                fmri_dir="/path/to",
                bandpass_filter=True,
                low_pass=0.1,
                high_pass=0.008,
                bpf_order=2,
                fd_thresh=0.3,
                motion_filter_type=None,
                smoothing=6,
                params="36P",
                exact_scans=[],
                atlases=["Glasser"],
                cifti=False,
                dcan_qc=True,
                output_dir=".",
                custom_confounds_file=None,
                name="postproc_derivatives_wf",
            )

    Parameters
    ----------
    name_source : :obj:`str`
        bold or cifti files
    source_metadata : :obj:`dict`
    fmri_dir : :obj:`str`
        Path to the preprocessing derivatives.
    low_pass : float
        low pass filter
    high_pass : float
        high pass filter
    bpf_order
    %(fd_thresh)s
    %(motion_filter_type)s
    %(smoothing)s
    %(params)s
    %(exact_scans)s
    %(atlases)s
    %(cifti)s
    %(dcan_qc)s
    output_dir : :obj:`str`
        output directory
    custom_confounds_file
        Only used for Sources metadata.
    %(name)s
        Default is "connectivity_wf".

    Inputs
    ------
    atlas_files
    %(timeseries)s
    %(correlations)s
    %(coverage)s
    %(timeseries_ciftis)s
    %(correlation_ciftis)s
    %(coverage_ciftis)s
    qc_file
        LINC-style quality control file
    %(interpolated_filtered_bold)s
    %(censored_denoised_bold)s
    %(smoothed_denoised_bold)s
    alff
        alff nifti
    parcellated_alff
    smoothed_alff
        smoothed alff
    reho
    parcellated_reho
    confounds_file
    confounds_metadata
    %(filtered_motion)s
    motion_metadata
    %(temporal_mask)s
    temporal_mask_metadata
    %(dummy_scans)s
    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                # preprocessing files to use as sources
                "fmriprep_confounds_file",
                # postprocessed outputs
                "atlas_files",  # for Sources
                "confounds_file",
                "confounds_metadata",
                "coverage",
                "timeseries",
                "correlations",
                "correlations_exact",
                "qc_file",
                "censored_denoised_bold",
                "smoothed_denoised_bold",
                "interpolated_filtered_bold",
                "alff",
                "parcellated_alff",
                "smoothed_alff",
                "reho",
                "parcellated_reho",
                "filtered_motion",
                "motion_metadata",
                "temporal_mask",
                "temporal_mask_metadata",
                "dummy_scans",
                # cifti-only inputs
                "coverage_ciftis",
                "timeseries_ciftis",
                "correlation_ciftis",
                "correlation_ciftis_exact",
            ],
        ),
        name="inputnode",
    )

    # Outputs that may be used by the concatenation workflow, in which case we want the actual
    # output filenames for the Sources metadata field.
    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                "filtered_motion",
                "temporal_mask",
                "interpolated_filtered_bold",
                "censored_denoised_bold",
                "smoothed_denoised_bold",
                "timeseries",
                "timeseries_ciftis",
            ],
        ),
        name="outputnode",
    )

    # Create dictionary of basic information
    cleaned_data_dictionary = {
        "nuisance parameters": params,
        **source_metadata,
    }
    software_filters = None
    if bandpass_filter:
        software_filters = {}
        if low_pass > 0 and high_pass > 0:
            software_filters["Bandpass filter"] = {
                "Low-pass cutoff (Hz)": low_pass,
                "High-pass cutoff (Hz)": high_pass,
                "Filter order": bpf_order,
            }
        elif high_pass > 0:
            software_filters["High-pass filter"] = {
                "cutoff (Hz)": high_pass,
                "Filter order": bpf_order,
            }
        elif low_pass > 0:
            software_filters["Low-pass filter"] = {
                "cutoff (Hz)": low_pass,
                "Filter order": bpf_order,
            }

    # Determine cohort (if there is one) in the original data
    cohort = get_entity(name_source, "cohort")

    preproc_bold_src = _make_preproc_uri(name_source, fmri_dir)

    ds_filtered_motion = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            source_file=name_source,
            dismiss_entities=["segmentation", "den", "res", "space", "cohort", "desc"],
            desc="filtered" if motion_filter_type else None,
            suffix="motion",
            extension=".tsv",
        ),
        name="ds_filtered_motion",
        run_without_submitting=True,
        mem_gb=1,
    )
    # fmt:off
    workflow.connect([
        (inputnode, ds_filtered_motion, [
            ("motion_metadata", "meta_dict"),
            ("filtered_motion", "in_file"),
            (("fmriprep_confounds_file", _make_preproc_uri, fmri_dir), "Sources"),
        ]),
        (ds_filtered_motion, outputnode, [("out_file", "filtered_motion")]),
    ])
    # fmt:on

    merge_dense_src = pe.Node(
        niu.Merge(numinputs=(1 + (1 if fd_thresh > 0 else 0) + (1 if params != "none" else 0))),
        name="merge_dense_src",
        run_without_submitting=True,
        mem_gb=1,
    )
    merge_dense_src.inputs.in1 = preproc_bold_src

    if fd_thresh > 0:
        ds_temporal_mask = pe.Node(
            DerivativesDataSink(
                base_directory=output_dir,
                dismiss_entities=["segmentation", "den", "res", "space", "cohort", "desc"],
                suffix="outliers",
                extension=".tsv",
                source_file=name_source,
                # Metadata
                Threshold=fd_thresh,
            ),
            name="ds_temporal_mask",
            run_without_submitting=True,
            mem_gb=1,
        )
        # fmt:off
        workflow.connect([
            (inputnode, ds_temporal_mask, [
                ("temporal_mask_metadata", "meta_dict"),
                ("temporal_mask", "in_file"),
            ]),
            (ds_filtered_motion, ds_temporal_mask, [
                (("out_file", _make_xcpd_uri, output_dir), "Sources"),
            ]),
            (ds_temporal_mask, outputnode, [("out_file", "temporal_mask")]),
            (ds_temporal_mask, merge_dense_src, [
                (("out_file", _make_xcpd_uri, output_dir), "in2"),
            ]),
        ])
        # fmt:on

    if params != "none":
        confounds_src = pe.Node(
            niu.Merge(
                numinputs=(1 + (1 if fd_thresh > 0 else 0) + (1 if custom_confounds_file else 0))
            ),
            name="confounds_src",
            run_without_submitting=True,
            mem_gb=1,
        )
        workflow.connect([(inputnode, confounds_src, [("fmriprep_confounds_file", "in1")])])
        if fd_thresh > 0:
            # fmt:off
            workflow.connect([
                (ds_temporal_mask, confounds_src, [
                    (("out_file", _make_xcpd_uri, output_dir), "in2"),
                ]),
            ])
            # fmt:on

            if custom_confounds_file:
                confounds_src.inputs.in3 = _make_custom_uri(custom_confounds_file)

        elif custom_confounds_file:
            confounds_src.inputs.in2 = _make_custom_uri(custom_confounds_file)

        ds_confounds = pe.Node(
            DerivativesDataSink(
                base_directory=output_dir,
                source_file=name_source,
                dismiss_entities=["space", "cohort", "den", "res"],
                datatype="func",
                suffix="design",
                extension=".tsv",
            ),
            name="ds_confounds",
            run_without_submitting=False,
        )
        # fmt:off
        workflow.connect([
            (inputnode, ds_confounds, [
                ("confounds_file", "in_file"),
                ("confounds_metadata", "meta_dict"),
            ]),
            (confounds_src, ds_confounds, [("out", "Sources")]),
            (ds_confounds, merge_dense_src, [
                (("out_file", _make_xcpd_uri, output_dir), f"in{3 if fd_thresh > 0 else 2}"),
            ]),
        ])
        # fmt:on

    # Write out derivatives via DerivativesDataSink
    ds_denoised_bold = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            source_file=name_source,
            dismiss_entities=["den"],
            cohort=cohort,
            desc="denoised",
            den="91k" if cifti else None,
            extension=".dtseries.nii" if cifti else ".nii.gz",
            # Metadata
            meta_dict=cleaned_data_dictionary,
            SoftwareFilters=software_filters,
        ),
        name="ds_denoised_bold",
        run_without_submitting=True,
        mem_gb=2,
    )
    # fmt:off
    workflow.connect([
        (inputnode, ds_denoised_bold, [("censored_denoised_bold", "in_file")]),
        (merge_dense_src, ds_denoised_bold, [("out", "Sources")]),
        (ds_denoised_bold, outputnode, [("out_file", "censored_denoised_bold")]),
    ])
    # fmt:on

    if dcan_qc and (fd_thresh > 0):
        ds_interpolated_denoised_bold = pe.Node(
            DerivativesDataSink(
                base_directory=output_dir,
                source_file=name_source,
                dismiss_entities=["den"],
                desc="interpolated",
                den="91k" if cifti else None,
                extension=".dtseries.nii" if cifti else ".nii.gz",
                # Metadata
                meta_dict=cleaned_data_dictionary,
            ),
            name="ds_interpolated_denoised_bold",
            run_without_submitting=True,
            mem_gb=2,
        )
        # fmt:off
        workflow.connect([
            (inputnode, ds_interpolated_denoised_bold, [
                ("interpolated_filtered_bold", "in_file"),
            ]),
            (ds_denoised_bold, ds_interpolated_denoised_bold, [
                (("out_file", _make_xcpd_uri, output_dir), "Sources"),
            ]),
            (ds_interpolated_denoised_bold, outputnode, [
                ("out_file", "interpolated_filtered_bold"),
            ]),
        ])
        # fmt:on

    else:
        # fmt:off
        workflow.connect([
            (inputnode, outputnode, [
                ("interpolated_filtered_bold", "interpolated_filtered_bold"),
            ]),
        ])
        # fmt:on

    ds_qc_file = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            source_file=name_source,
            dismiss_entities=["desc", "den"],
            cohort=cohort,
            den="91k" if cifti else None,
            desc="linc",
            suffix="qc",
            extension=".csv",
        ),
        name="ds_qc_file",
        run_without_submitting=True,
        mem_gb=1,
    )
    workflow.connect([(inputnode, ds_qc_file, [("qc_file", "in_file")])])

    if smoothing:
        # Write out derivatives via DerivativesDataSink
        ds_smoothed_bold = pe.Node(
            DerivativesDataSink(
                base_directory=output_dir,
                source_file=name_source,
                dismiss_entities=["den"],
                cohort=cohort,
                den="91k" if cifti else None,
                desc="denoisedSmoothed",
                extension=".dtseries.nii" if cifti else ".nii.gz",
                check_hdr=False,
                # Metadata
                SoftwareFilters=software_filters,
                FWHM=smoothing,
            ),
            name="ds_smoothed_bold",
            run_without_submitting=True,
            mem_gb=2,
        )
        # fmt:off
        workflow.connect([
            (inputnode, ds_smoothed_bold, [("smoothed_denoised_bold", "in_file")]),
            (ds_denoised_bold, ds_smoothed_bold, [
                (("out_file", _make_xcpd_uri, output_dir), "Sources"),
            ]),
            (ds_smoothed_bold, outputnode, [("out_file", "smoothed_denoised_bold")]),
        ])
        # fmt:on

    # Connectivity workflow outputs
    if atlases:
        make_atlas_dict = pe.MapNode(
            niu.Function(
                function=_make_dictionary,
                input_names=["Sources"],
                output_names=["metadata"],
            ),
            run_without_submitting=True,
            mem_gb=1,
            name="make_atlas_dict",
            iterfield=["Sources"],
        )
        workflow.connect([
            (inputnode, make_atlas_dict, [
                (("atlas_files", _make_xcpd_uri, output_dir), "Sources"),
            ]),
        ])  # fmt:skip

        # Convert Sources to a dictionary, to play well with parcellation MapNodes.
        add_denoised_to_src = pe.MapNode(
            niu.Function(
                function=_make_dictionary,
                input_names=["metadata", "Sources"],
                output_names=["metadata"],
            ),
            run_without_submitting=True,
            mem_gb=1,
            name="add_denoised_to_src",
            iterfield=["metadata"],
        )
        # fmt:off
        workflow.connect([
            (make_atlas_dict, add_denoised_to_src, [("metadata", "metadata")]),
            (ds_denoised_bold, add_denoised_to_src, [
                (("out_file", _make_xcpd_uri, output_dir), "Sources"),
            ]),
        ])
        # fmt:on

        # TODO: Add brain mask to Sources (for NIfTIs).
        ds_coverage = pe.MapNode(
            DerivativesDataSink(
                base_directory=output_dir,
                source_file=name_source,
                dismiss_entities=["desc"],
                cohort=cohort,
                statistic="coverage",
                suffix="bold",
                extension=".tsv",
            ),
            name="ds_coverage",
            run_without_submitting=True,
            mem_gb=1,
            iterfield=["segmentation", "in_file", "meta_dict"],
        )
        ds_coverage.inputs.segmentation = atlases
        # fmt:off
        workflow.connect([
            (inputnode, ds_coverage, [("coverage", "in_file")]),
            (make_atlas_dict, ds_coverage, [("metadata", "meta_dict")]),
        ])
        # fmt:on

        add_coverage_to_src = pe.MapNode(
            niu.Function(
                function=_make_dictionary,
                input_names=["metadata", "Sources"],
                output_names=["metadata"],
            ),
            run_without_submitting=True,
            mem_gb=1,
            name="add_coverage_to_src",
            iterfield=["metadata", "Sources"],
        )
        # fmt:off
        workflow.connect([
            (add_denoised_to_src, add_coverage_to_src, [("metadata", "metadata")]),
            (ds_coverage, add_coverage_to_src, [
                (("out_file", _make_xcpd_uri, output_dir), "Sources"),
            ]),
        ])
        # fmt:on

        ds_timeseries = pe.MapNode(
            DerivativesDataSink(
                base_directory=output_dir,
                source_file=name_source,
                dismiss_entities=["desc"],
                cohort=cohort,
                statistic="mean",
                suffix="timeseries",
                extension=".tsv",
                # Metadata
                SamplingFrequency="TR",
            ),
            name="ds_timeseries",
            run_without_submitting=True,
            mem_gb=1,
            iterfield=["segmentation", "in_file", "meta_dict"],
        )
        ds_timeseries.inputs.segmentation = atlases
        # fmt:off
        workflow.connect([
            (inputnode, ds_timeseries, [("timeseries", "in_file")]),
            (add_coverage_to_src, ds_timeseries, [("metadata", "meta_dict")]),
            (ds_timeseries, outputnode, [("out_file", "timeseries")]),
        ])
        # fmt:on

        make_corrs_meta_dict = pe.MapNode(
            niu.Function(
                function=_make_dictionary,
                input_names=["Sources"],
                output_names=["metadata"],
            ),
            run_without_submitting=True,
            mem_gb=1,
            name="make_corrs_meta_dict",
            iterfield=["Sources"],
        )
        workflow.connect([(ds_timeseries, make_corrs_meta_dict, [("out_file", "Sources")])])

        ds_correlations = pe.MapNode(
            DerivativesDataSink(
                base_directory=output_dir,
                source_file=name_source,
                dismiss_entities=["desc"],
                cohort=cohort,
                statistic="pearsoncorrelation",
                suffix="relmat",
                extension=".tsv",
            ),
            name="ds_correlations",
            run_without_submitting=True,
            mem_gb=1,
            iterfield=["segmentation", "in_file", "meta_dict"],
        )
        ds_correlations.inputs.segmentation = atlases
        # fmt:off
        workflow.connect([
            (inputnode, ds_correlations, [("correlations", "in_file")]),
            (make_corrs_meta_dict, ds_correlations, [("metadata", "meta_dict")]),
        ])
        # fmt:on

        if cifti:
            ds_coverage_ciftis = pe.MapNode(
                DerivativesDataSink(
                    base_directory=output_dir,
                    source_file=name_source,
                    check_hdr=False,
                    dismiss_entities=["desc"],
                    cohort=cohort,
                    statistic="coverage",
                    suffix="boldmap",
                    extension=".pscalar.nii",
                ),
                name="ds_coverage_ciftis",
                run_without_submitting=True,
                mem_gb=1,
                iterfield=["segmentation", "in_file", "meta_dict"],
            )
            ds_coverage_ciftis.inputs.segmentation = atlases
            # fmt:off
            workflow.connect([
                (inputnode, ds_coverage_ciftis, [("coverage_ciftis", "in_file")]),
                (add_denoised_to_src, ds_coverage_ciftis, [("metadata", "meta_dict")]),
            ])
            # fmt:on

            add_ccoverage_to_src = pe.MapNode(
                niu.Function(
                    function=_make_dictionary,
                    input_names=["metadata", "Sources"],
                    output_names=["metadata"],
                ),
                run_without_submitting=True,
                mem_gb=1,
                name="add_ccoverage_to_src",
                iterfield=["metadata", "Sources"],
            )
            # fmt:off
            workflow.connect([
                (add_denoised_to_src, add_ccoverage_to_src, [("metadata", "metadata")]),
                (ds_coverage_ciftis, add_ccoverage_to_src, [
                    (("out_file", _make_xcpd_uri, output_dir), "Sources"),
                ]),
            ])
            # fmt:on

            ds_timeseries_ciftis = pe.MapNode(
                DerivativesDataSink(
                    base_directory=output_dir,
                    source_file=name_source,
                    check_hdr=False,
                    dismiss_entities=["desc", "den"],
                    cohort=cohort,
                    den="91k" if cifti else None,
                    statistic="mean",
                    suffix="timeseries",
                    extension=".ptseries.nii",
                ),
                name="ds_timeseries_ciftis",
                run_without_submitting=True,
                mem_gb=1,
                iterfield=["segmentation", "in_file", "meta_dict"],
            )
            ds_timeseries_ciftis.inputs.segmentation = atlases
            # fmt:off
            workflow.connect([
                (inputnode, ds_timeseries_ciftis, [("timeseries_ciftis", "in_file")]),
                (add_ccoverage_to_src, ds_timeseries_ciftis, [("metadata", "meta_dict")]),
                (ds_timeseries_ciftis, outputnode, [("out_file", "timeseries_ciftis")]),
            ])
            # fmt:on

            make_ccorrs_meta_dict = pe.MapNode(
                niu.Function(
                    function=_make_dictionary,
                    input_names=["Sources"],
                    output_names=["metadata"],
                ),
                run_without_submitting=True,
                mem_gb=1,
                name="make_ccorrs_meta_dict",
                iterfield=["Sources"],
            )
            # fmt:off
            workflow.connect([
                (ds_timeseries_ciftis, make_ccorrs_meta_dict, [("out_file", "Sources")]),
            ])
            # fmt:on

            ds_correlation_ciftis = pe.MapNode(
                DerivativesDataSink(
                    base_directory=output_dir,
                    source_file=name_source,
                    check_hdr=False,
                    dismiss_entities=["desc", "den"],
                    cohort=cohort,
                    den="91k" if cifti else None,
                    statistic="pearsoncorrelation",
                    suffix="boldmap",
                    extension=".pconn.nii",
                ),
                name="ds_correlation_ciftis",
                run_without_submitting=True,
                mem_gb=1,
                iterfield=["segmentation", "in_file", "meta_dict"],
            )
            ds_correlation_ciftis.inputs.segmentation = atlases
            # fmt:off
            workflow.connect([
                (inputnode, ds_correlation_ciftis, [("correlation_ciftis", "in_file")]),
                (make_ccorrs_meta_dict, ds_correlation_ciftis, [("metadata", "meta_dict")]),
            ])
            # fmt:on

        for i_exact_scan, exact_scan in enumerate(exact_scans):
            select_exact_scan_files = pe.MapNode(
                niu.Select(index=i_exact_scan),
                name=f"select_exact_scan_files_{i_exact_scan}",
                iterfield=["inlist"],
            )
            # fmt:off
            workflow.connect([
                (inputnode, select_exact_scan_files, [("correlations_exact", "inlist")]),
            ])
            # fmt:on

            ds_correlations_exact = pe.MapNode(
                DerivativesDataSink(
                    base_directory=output_dir,
                    source_file=name_source,
                    dismiss_entities=["desc"],
                    cohort=cohort,
                    statistic="pearsoncorrelation",
                    desc=f"{exact_scan}volumes",
                    suffix="relmat",
                    extension=".tsv",
                ),
                name=f"ds_correlations_exact_{i_exact_scan}",
                run_without_submitting=True,
                mem_gb=1,
                iterfield=["segmentation", "in_file"],
            )
            ds_correlations_exact.inputs.segmentation = atlases
            # fmt:off
            workflow.connect([
                (select_exact_scan_files, ds_correlations_exact, [("out", "in_file")]),
            ])
            # fmt:on

    # Resting state metric outputs
    ds_reho = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            source_file=name_source,
            check_hdr=False,
            dismiss_entities=["desc", "den"],
            cohort=cohort,
            den="91k" if cifti else None,
            statistic="reho",
            suffix="boldmap",
            extension=".dscalar.nii" if cifti else ".nii.gz",
            # Metadata
            SoftwareFilters=software_filters,
            Neighborhood="vertices",
        ),
        name="ds_reho",
        run_without_submitting=True,
        mem_gb=1,
    )
    # fmt:off
    workflow.connect([
        (inputnode, ds_reho, [("reho", "in_file")]),
        (ds_denoised_bold, ds_reho, [(("out_file", _make_xcpd_uri, output_dir), "Sources")]),
    ])
    # fmt:on

    if atlases:
        add_reho_to_src = pe.MapNode(
            niu.Function(
                function=_make_dictionary,
                input_names=["metadata", "Sources"],
                output_names=["metadata"],
            ),
            run_without_submitting=True,
            mem_gb=1,
            name="add_reho_to_src",
            iterfield=["metadata"],
        )
        # fmt:off
        workflow.connect([
            (make_atlas_dict, add_reho_to_src, [("metadata", "metadata")]),
            (ds_reho, add_reho_to_src, [(("out_file", _make_xcpd_uri, output_dir), "Sources")]),
        ])
        # fmt:on

        ds_parcellated_reho = pe.MapNode(
            DerivativesDataSink(
                base_directory=output_dir,
                source_file=name_source,
                dismiss_entities=["desc"],
                cohort=cohort,
                statistic="reho",
                suffix="bold",
                extension=".tsv",
                # Metadata
                SoftwareFilters=software_filters,
                Neighborhood="vertices",
            ),
            name="ds_parcellated_reho",
            run_without_submitting=True,
            mem_gb=1,
            iterfield=["segmentation", "in_file", "meta_dict"],
        )
        ds_parcellated_reho.inputs.segmentation = atlases
        # fmt:off
        workflow.connect([
            (inputnode, ds_parcellated_reho, [("parcellated_reho", "in_file")]),
            (add_reho_to_src, ds_parcellated_reho, [("metadata", "meta_dict")]),
        ])
        # fmt:on

    if bandpass_filter:
        ds_alff = pe.Node(
            DerivativesDataSink(
                base_directory=output_dir,
                source_file=name_source,
                check_hdr=False,
                dismiss_entities=["desc", "den"],
                cohort=cohort,
                den="91k" if cifti else None,
                statistic="alff",
                suffix="boldmap",
                extension=".dscalar.nii" if cifti else ".nii.gz",
                # Metadata
                SoftwareFilters=software_filters,
            ),
            name="ds_alff",
            run_without_submitting=True,
            mem_gb=1,
        )
        # fmt:off
        workflow.connect([
            (inputnode, ds_alff, [("alff", "in_file")]),
            (ds_denoised_bold, ds_alff, [(("out_file", _make_xcpd_uri, output_dir), "Sources")]),
        ])
        # fmt:on

        if smoothing:
            ds_smoothed_alff = pe.Node(
                DerivativesDataSink(
                    base_directory=output_dir,
                    source_file=name_source,
                    dismiss_entities=["den"],
                    cohort=cohort,
                    desc="smooth",
                    den="91k" if cifti else None,
                    statistic="alff",
                    suffix="boldmap",
                    extension=".dscalar.nii" if cifti else ".nii.gz",
                    check_hdr=False,
                    # Metadata
                    SoftwareFilters=software_filters,
                    FWHM=smoothing,
                ),
                name="ds_smoothed_alff",
                run_without_submitting=True,
                mem_gb=1,
            )
            # fmt:off
            workflow.connect([
                (inputnode, ds_smoothed_alff, [("smoothed_alff", "in_file")]),
                (ds_alff, ds_smoothed_alff, [
                    (("out_file", _make_xcpd_uri, output_dir), "Sources"),
                ]),
            ])
            # fmt:on

        if atlases:
            add_alff_to_src = pe.MapNode(
                niu.Function(
                    function=_make_dictionary,
                    input_names=["metadata", "Sources"],
                    output_names=["metadata"],
                ),
                run_without_submitting=True,
                mem_gb=1,
                name="add_alff_to_src",
                iterfield=["metadata"],
            )
            # fmt:off
            workflow.connect([
                (make_atlas_dict, add_alff_to_src, [("metadata", "metadata")]),
                (ds_alff, add_alff_to_src, [
                    (("out_file", _make_xcpd_uri, output_dir), "Sources"),
                ]),
            ])
            # fmt:on

            ds_parcellated_alff = pe.MapNode(
                DerivativesDataSink(
                    base_directory=output_dir,
                    source_file=name_source,
                    dismiss_entities=["desc"],
                    cohort=cohort,
                    statistic="alff",
                    suffix="bold",
                    extension=".tsv",
                ),
                name="ds_parcellated_alff",
                run_without_submitting=True,
                mem_gb=1,
                iterfield=["segmentation", "in_file", "meta_dict"],
            )
            ds_parcellated_alff.inputs.segmentation = atlases
            # fmt:off
            workflow.connect([
                (inputnode, ds_parcellated_alff, [("parcellated_alff", "in_file")]),
                (add_alff_to_src, ds_parcellated_alff, [("metadata", "meta_dict")]),
            ])
            # fmt:on

    return workflow
