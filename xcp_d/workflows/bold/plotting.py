"""Workflows for generating plots from functional data."""

import fnmatch
import os

from nipype import Function, logging
from nipype.interfaces import utility as niu
from nipype.pipeline import engine as pe
from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from templateflow.api import get as get_template

from xcp_d import config
from xcp_d.interfaces.ants import ApplyTransforms
from xcp_d.interfaces.bids import DerivativesDataSink
from xcp_d.interfaces.nilearn import BinaryMath, ResampleToImage
from xcp_d.interfaces.plotting import AnatomicalPlot, QCPlots, QCPlotsES
from xcp_d.interfaces.report import FunctionalSummary
from xcp_d.interfaces.utils import ABCCQC, LINCQC
from xcp_d.utils.doc import fill_doc
from xcp_d.utils.utils import get_bold2std_and_t1w_xfms, get_std2bold_xfms
from xcp_d.workflows.plotting import init_plot_overlay_wf

LOGGER = logging.getLogger('nipype.workflow')


@fill_doc
def init_qc_report_wf(
    TR,
    head_radius,
    name='qc_report_wf',
):
    """Generate quality control figures and a QC file.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from xcp_d.tests.tests import mock_config
            from xcp_d import config
            from xcp_d.workflows.bold.plotting import init_qc_report_wf

            with mock_config():
                wf = init_qc_report_wf(
                    TR=0.5,
                    head_radius=50,
                    name="qc_report_wf",
                )

    Parameters
    ----------
    %(TR)s
    %(head_radius)s
    %(name)s
        Default is "qc_report_wf".

    Inputs
    ------
    %(name_source)s
    preprocessed_bold
        The preprocessed BOLD file, after dummy scan removal.
        Used for carpet plots.
    %(denoised_interpolated_bold)s
        Used for DCAN carpet plots.
        Only used if abcc_qc is True.
    %(censored_denoised_bold)s
        Used for LINC carpet plots.
    %(boldref)s
        Only used with non-CIFTI data.
    bold_mask
        Path to the BOLD run's brain mask in the same space as ``preprocessed_bold``.
        Only used with non-CIFTI data.
    anat_brainmask
        Path to the anatomical brain mask in the same standard space as ``bold_mask``.
        Only used with non-CIFTI data.
    %(template_to_anat_xfm)s
        Only used with non-CIFTI data.
    %(dummy_scans)s
    motion_file
    design_matrix
    %(temporal_mask)s

    Outputs
    -------
    qc_file
    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'name_source',
                'preprocessed_bold',
                'denoised_interpolated_bold',
                'censored_denoised_bold',
                'dummy_scans',
                'motion_file',
                'design_matrix',
                'temporal_mask',
                'run_index',  # will only be set for concatenated data
                # nifti-only inputs
                'bold_mask',
                'anat',  # T1w/T2w image in anatomical space
                'anat_brainmask',
                'boldref',
                'template_to_anat_xfm',
            ],
        ),
        name='inputnode',
    )

    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'qc_file',
            ],
        ),
        name='outputnode',
    )

    nlin2009casym_brain_mask = str(
        get_template(
            'MNI152NLin2009cAsym',
            resolution=2,
            desc='brain',
            suffix='mask',
            extension=['.nii', '.nii.gz'],
        )
    )

    if config.workflow.file_format == 'nifti':
        # We need the BOLD mask in T1w and standard spaces for QC metric calculation.
        # This is only possible for nifti inputs.
        get_native2space_transforms = pe.Node(
            Function(
                input_names=['bold_file', 'template_to_anat_xfm'],
                output_names=[
                    'bold_to_std_xfms',
                    'bold_to_std_xfms_invert',
                    'bold_to_t1w_xfms',
                    'bold_to_t1w_xfms_invert',
                ],
                function=get_bold2std_and_t1w_xfms,
            ),
            name='get_native2space_transforms',
        )

        workflow.connect([
            (inputnode, get_native2space_transforms, [
                ('name_source', 'bold_file'),
                ('template_to_anat_xfm', 'template_to_anat_xfm'),
            ]),
        ])  # fmt:skip

        warp_boldmask_to_t1w = pe.Node(
            ApplyTransforms(
                dimension=3,
                interpolation='NearestNeighbor',
                num_threads=config.nipype.omp_nthreads,
            ),
            name='warp_boldmask_to_t1w',
            mem_gb=1,
            n_procs=config.nipype.omp_nthreads,
        )
        workflow.connect([
            (inputnode, warp_boldmask_to_t1w, [
                ('bold_mask', 'input_image'),
                ('anat', 'reference_image'),
            ]),
            (get_native2space_transforms, warp_boldmask_to_t1w, [
                ('bold_to_t1w_xfms', 'transforms'),
                ('bold_to_t1w_xfms_invert', 'invert_transform_flags'),
            ]),
        ])  # fmt:skip

        warp_boldmask_to_mni = pe.Node(
            ApplyTransforms(
                dimension=3,
                reference_image=nlin2009casym_brain_mask,
                interpolation='NearestNeighbor',
                num_threads=config.nipype.omp_nthreads,
            ),
            name='warp_boldmask_to_mni',
            mem_gb=1,
            n_procs=config.nipype.omp_nthreads,
        )
        workflow.connect([
            (inputnode, warp_boldmask_to_mni, [('bold_mask', 'input_image')]),
            (get_native2space_transforms, warp_boldmask_to_mni, [
                ('bold_to_std_xfms', 'transforms'),
                ('bold_to_std_xfms_invert', 'invert_transform_flags'),
            ]),
        ])  # fmt:skip

        # Warp the standard-space anatomical brain mask to the anatomical space
        warp_anatmask_to_t1w = pe.Node(
            ApplyTransforms(
                dimension=3,
                interpolation='NearestNeighbor',
                num_threads=config.nipype.omp_nthreads,
            ),
            name='warp_anatmask_to_t1w',
            mem_gb=1,
            n_procs=config.nipype.omp_nthreads,
        )
        workflow.connect([
            (inputnode, warp_anatmask_to_t1w, [
                ('bold_mask', 'input_image'),
                ('anat', 'reference_image'),
            ]),
            (get_native2space_transforms, warp_anatmask_to_t1w, [
                ('bold_to_t1w_xfms', 'transforms'),
                ('bold_to_t1w_xfms_invert', 'invert_transform_flags'),
            ]),
        ])  # fmt:skip

        # NIFTI files require a tissue-type segmentation in the same space as the BOLD data.
        # Get the set of transforms from MNI152NLin2009cAsym (the dseg) to the BOLD space.
        get_mni_to_bold_xfms = pe.Node(
            Function(
                input_names=['bold_file', 'source_file', 'source_space'],
                output_names=['transforms'],
                function=get_std2bold_xfms,
            ),
            name='get_std2native_transform',
        )
        get_mni_to_bold_xfms.inputs.source_file = None
        get_mni_to_bold_xfms.inputs.source_space = 'MNI152NLin2009cAsym'
        workflow.connect([(inputnode, get_mni_to_bold_xfms, [('name_source', 'bold_file')])])

        # Use MNI152NLin2009cAsym tissue-type segmentation file for carpet plots.
        dseg_file = str(
            get_template(
                'MNI152NLin2009cAsym',
                resolution=1,
                desc='carpet',
                suffix='dseg',
                extension=['.nii', '.nii.gz'],
            )
        )

        # Transform MNI152NLin2009cAsym dseg file to the same space as the BOLD data.
        warp_dseg_to_bold = pe.Node(
            ApplyTransforms(
                dimension=3,
                input_image=dseg_file,
                interpolation='GenericLabel',
                num_threads=config.nipype.omp_nthreads,
            ),
            name='warp_dseg_to_bold',
            mem_gb=3,
            n_procs=config.nipype.omp_nthreads,
        )
        workflow.connect([
            (inputnode, warp_dseg_to_bold, [('boldref', 'reference_image')]),
            (get_mni_to_bold_xfms, warp_dseg_to_bold, [('transforms', 'transforms')]),
        ])  # fmt:skip

    if config.workflow.linc_qc:
        make_linc_qc = pe.Node(
            LINCQC(
                TR=TR,
                head_radius=head_radius,
                template_mask=nlin2009casym_brain_mask,
                high_pass=config.workflow.high_pass,
                low_pass=config.workflow.low_pass,
            ),
            name='make_linc_qc',
            mem_gb=2,
        )
        workflow.connect([
            (inputnode, make_linc_qc, [
                ('name_source', 'name_source'),
                ('preprocessed_bold', 'bold_file'),
                ('censored_denoised_bold', 'cleaned_file'),
                ('motion_file', 'motion_file'),
                ('design_matrix', 'design_matrix'),
                ('temporal_mask', 'temporal_mask'),
                ('dummy_scans', 'dummy_scans'),
            ]),
            (make_linc_qc, outputnode, [('qc_file', 'qc_file')]),
        ])  # fmt:skip

        if config.workflow.file_format == 'nifti':
            workflow.connect([
                (inputnode, make_linc_qc, [('bold_mask', 'bold_mask_inputspace')]),
                (warp_boldmask_to_t1w, make_linc_qc, [('output_image', 'bold_mask_anatspace')]),
                (warp_boldmask_to_mni, make_linc_qc, [('output_image', 'bold_mask_stdspace')]),
                (warp_anatmask_to_t1w, make_linc_qc, [('output_image', 'anat_mask_anatspace')]),
            ])  # fmt:skip
        else:
            make_linc_qc.inputs.bold_mask_inputspace = None

        ds_qc_metadata = pe.Node(
            DerivativesDataSink(
                dismiss_entities=list(DerivativesDataSink._allowed_entities),
                allowed_entities=['desc'],
                desc='linc',
                suffix='qc',
                extension='.json',
            ),
            name='ds_qc_metadata',
            run_without_submitting=True,
        )
        workflow.connect([
            (inputnode, ds_qc_metadata, [('name_source', 'source_file')]),
            (make_linc_qc, ds_qc_metadata, [('qc_metadata', 'in_file')]),
        ])  # fmt:skip

        make_qc_plots_nipreps = pe.Node(
            QCPlots(TR=TR, head_radius=head_radius),
            name='make_qc_plots_nipreps',
            mem_gb=2,
        )
        workflow.connect([
            (inputnode, make_qc_plots_nipreps, [
                ('preprocessed_bold', 'bold_file'),
                ('censored_denoised_bold', 'cleaned_file'),
                ('motion_file', 'motion_file'),
                ('temporal_mask', 'temporal_mask'),
            ]),
        ])  # fmt:skip

        if config.workflow.file_format == 'nifti':
            workflow.connect([
                (inputnode, make_qc_plots_nipreps, [('bold_mask', 'mask_file')]),
                (warp_dseg_to_bold, make_qc_plots_nipreps, [('output_image', 'seg_file')]),
            ])  # fmt:skip
        else:
            make_qc_plots_nipreps.inputs.mask_file = None

        ds_report_preproc_qc_nipreps = pe.Node(
            DerivativesDataSink(desc='preprocessing'),
            name='ds_report_preproc_qc_nipreps',
            run_without_submitting=False,
        )
        workflow.connect([
            (inputnode, ds_report_preproc_qc_nipreps, [('name_source', 'source_file')]),
            (make_qc_plots_nipreps, ds_report_preproc_qc_nipreps, [('raw_qcplot', 'in_file')]),
        ])  # fmt:skip

        ds_report_postproc_qc_nipreps = pe.Node(
            DerivativesDataSink(desc='postprocessing'),
            name='ds_report_postproc_qc_nipreps',
            run_without_submitting=False,
        )
        workflow.connect([
            (inputnode, ds_report_postproc_qc_nipreps, [('name_source', 'source_file')]),
            (make_qc_plots_nipreps, ds_report_postproc_qc_nipreps, [('clean_qcplot', 'in_file')]),
        ])  # fmt:skip

        functional_qc = pe.Node(
            FunctionalSummary(TR=TR),
            name='qcsummary',
            run_without_submitting=False,
            mem_gb=2,
        )
        workflow.connect([
            (inputnode, functional_qc, [('name_source', 'bold_file')]),
            (make_linc_qc, functional_qc, [('qc_file', 'qc_file')]),
        ])  # fmt:skip

        ds_report_qualitycontrol = pe.Node(
            DerivativesDataSink(desc='qualitycontrol'),
            name='ds_report_qualitycontrol',
            run_without_submitting=False,
        )
        workflow.connect([
            (inputnode, ds_report_qualitycontrol, [('name_source', 'source_file')]),
            (functional_qc, ds_report_qualitycontrol, [('out_report', 'in_file')]),
        ])  # fmt:skip
    else:
        # Need to explicitly add the outputnode to the workflow, since it's not set otherwise.
        workflow.add_nodes([outputnode])

    if config.workflow.abcc_qc:
        make_abcc_qc = pe.Node(
            ABCCQC(TR=TR),
            name='make_abcc_qc',
            mem_gb=2,
        )
        workflow.connect([(inputnode, make_abcc_qc, [('motion_file', 'motion_file')])])

        ds_abcc_qc = pe.Node(
            DerivativesDataSink(
                datatype='func',
                desc='abcc',
                suffix='qc',
                extension='hdf5',
            ),
            name='ds_abcc_qc',
            run_without_submitting=True,
        )
        workflow.connect([
            (inputnode, ds_abcc_qc, [('name_source', 'source_file')]),
            (make_abcc_qc, ds_abcc_qc, [('qc_file', 'in_file')]),
        ])  # fmt:skip

        # Generate preprocessing and postprocessing carpet plots.
        make_qc_plots_es = pe.Node(
            QCPlotsES(TR=TR, standardize=config.execution.confounds_config is None),
            name='make_qc_plots_es',
            mem_gb=2,
        )
        workflow.connect([
            (inputnode, make_qc_plots_es, [
                ('preprocessed_bold', 'preprocessed_bold'),
                ('denoised_interpolated_bold', 'denoised_interpolated_bold'),
                ('motion_file', 'motion_file'),
                ('temporal_mask', 'temporal_mask'),
                ('run_index', 'run_index'),
            ]),
        ])  # fmt:skip

        if config.workflow.file_format == 'nifti':
            workflow.connect([
                (inputnode, make_qc_plots_es, [('bold_mask', 'mask')]),
                (warp_dseg_to_bold, make_qc_plots_es, [('output_image', 'seg_data')]),
            ])  # fmt:skip

        ds_report_preproc_qc_es = pe.Node(
            DerivativesDataSink(
                dismiss_entities=['den'],
                desc='preprocESQC',
            ),
            name='ds_report_preproc_qc_es',
            run_without_submitting=True,
        )
        workflow.connect([
            (inputnode, ds_report_preproc_qc_es, [('name_source', 'source_file')]),
            (make_qc_plots_es, ds_report_preproc_qc_es, [('before_process', 'in_file')]),
        ])  # fmt:skip

        ds_report_postproc_qc_es = pe.Node(
            DerivativesDataSink(
                dismiss_entities=['den'],
                desc='postprocESQC',
            ),
            name='ds_report_postproc_qc_es',
            run_without_submitting=True,
        )
        workflow.connect([
            (inputnode, ds_report_postproc_qc_es, [('name_source', 'source_file')]),
            (make_qc_plots_es, ds_report_postproc_qc_es, [('after_process', 'in_file')]),
        ])  # fmt:skip

    if config.workflow.file_format != 'nifti' and not (
        config.workflow.linc_qc or config.workflow.abcc_qc
    ):
        # Need to explicitly add the inputnode to the workflow, since it's not set otherwise.
        workflow.add_nodes([inputnode])

    return workflow


@fill_doc
def init_execsummary_functional_plots_wf(
    preproc_nifti,
    t1w_available,
    t2w_available,
    mem_gb,
    name='execsummary_functional_plots_wf',
):
    """Generate the functional figures for an executive summary.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from xcp_d.tests.tests import mock_config
            from xcp_d import config
            from xcp_d.workflows.bold.plotting import init_execsummary_functional_plots_wf

            with mock_config():
                wf = init_execsummary_functional_plots_wf(
                    preproc_nifti=None,
                    t1w_available=True,
                    t2w_available=True,
                    mem_gb={"resampled": 1},
                    name="execsummary_functional_plots_wf",
                )

    Parameters
    ----------
    preproc_nifti : :obj:`str` or None
        BOLD data before post-processing.
        A NIFTI file, not a CIFTI.
    t1w_available : :obj:`bool`
        Generally True.
    t2w_available : :obj:`bool`
        Generally False.
    mem_gb : :obj:`dict`
        Memory size in GB.
    %(name)s

    Inputs
    ------
    preproc_nifti
        BOLD data before post-processing.
        A NIFTI file, not a CIFTI.
        Set from the parameter.
    %(boldref)s
    t1w
        T1w image in a standard space, taken from the output of init_postprocess_anat_wf.
    t2w
        T2w image in a standard space, taken from the output of init_postprocess_anat_wf.
    """
    workflow = Workflow(name=name)

    layout = config.execution.layout

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=[
                'preproc_nifti',
                'boldref',  # a nifti boldref
                't1w',
                't2w',  # optional
            ],
        ),
        name='inputnode',
    )
    if not preproc_nifti:
        raise ValueError(
            'No preprocessed NIfTI found. Executive summary figures cannot be generated.'
        )

    inputnode.inputs.preproc_nifti = preproc_nifti

    # Get bb_registration_file prefix from fmriprep
    # TODO: Replace with interfaces.
    current_bold_file = os.path.basename(preproc_nifti)
    if '_space' in current_bold_file:
        bb_register_prefix = current_bold_file.split('_space')[0]
    else:
        bb_register_prefix = current_bold_file.split('_desc')[0]

    # TODO: Switch to interface
    bold_t1w_registration_files = layout.get(
        desc=['bbregister', 'coreg', 'bbr', 'flirtbbr', 'flirtnobbr'],
        extension='.svg',
        suffix='bold',
        return_type='file',
    )
    bold_t1w_registration_files = fnmatch.filter(
        bold_t1w_registration_files,
        f'*/{bb_register_prefix}*',
    )
    if not bold_t1w_registration_files:
        LOGGER.warning('No coregistration figure found in preprocessing derivatives.')
    else:
        bold_t1w_registration_file = bold_t1w_registration_files[0]

        ds_report_registration = pe.Node(
            DerivativesDataSink(
                in_file=bold_t1w_registration_file,
                dismiss_entities=['den'],
                desc='bbregister',
            ),
            name='ds_report_registration',
            run_without_submitting=True,
            mem_gb=config.DEFAULT_MEMORY_MIN_GB,
        )

        workflow.connect([(inputnode, ds_report_registration, [('preproc_nifti', 'source_file')])])

    # Calculate the mean bold image
    calculate_mean_bold = pe.Node(
        BinaryMath(expression='np.mean(img, axis=3)'),
        name='calculate_mean_bold',
        mem_gb=mem_gb['timeseries'],
    )
    workflow.connect([(inputnode, calculate_mean_bold, [('preproc_nifti', 'in_file')])])

    # Plot the mean bold image
    plot_meanbold = pe.Node(AnatomicalPlot(), name='plot_meanbold')
    workflow.connect([(calculate_mean_bold, plot_meanbold, [('out_file', 'in_file')])])

    # Write out the figures.
    ds_report_meanbold = pe.Node(
        DerivativesDataSink(
            dismiss_entities=['den'],
            desc='mean',
        ),
        name='ds_report_meanbold',
        run_without_submitting=True,
        mem_gb=config.DEFAULT_MEMORY_MIN_GB,
    )
    workflow.connect([
        (inputnode, ds_report_meanbold, [('preproc_nifti', 'source_file')]),
        (plot_meanbold, ds_report_meanbold, [('out_file', 'in_file')]),
    ])  # fmt:skip

    # Plot the reference bold image
    plot_boldref = pe.Node(AnatomicalPlot(), name='plot_boldref')
    workflow.connect([(inputnode, plot_boldref, [('boldref', 'in_file')])])

    # Write out the figures.
    ds_report_boldref = pe.Node(
        DerivativesDataSink(
            dismiss_entities=['den'],
            desc='boldref',
        ),
        name='ds_report_boldref',
        run_without_submitting=True,
        mem_gb=config.DEFAULT_MEMORY_MIN_GB,
    )
    workflow.connect([
        (inputnode, ds_report_boldref, [('preproc_nifti', 'source_file')]),
        (plot_boldref, ds_report_boldref, [('out_file', 'in_file')]),
    ])  # fmt:skip

    # Start plotting the overlay figures
    # T1 in Task, Task in T1, Task in T2, T2 in Task
    anatomicals = (['t1w'] if t1w_available else []) + (['t2w'] if t2w_available else [])
    for anat in anatomicals:
        # Resample BOLD to match resolution of T1w/T2w data
        resample_bold_to_anat = pe.Node(
            ResampleToImage(),
            name=f'resample_bold_to_{anat}',
            mem_gb=mem_gb['resampled'],
        )
        workflow.connect([
            (inputnode, resample_bold_to_anat, [(anat, 'target_file')]),
            (calculate_mean_bold, resample_bold_to_anat, [('out_file', 'in_file')]),
        ])  # fmt:skip

        plot_anat_on_task_wf = init_plot_overlay_wf(
            desc=f'{anat[0].upper()}{anat[1:]}OnTask',
            name=f'plot_{anat}_on_task_wf',
        )
        workflow.connect([
            (inputnode, plot_anat_on_task_wf, [
                ('preproc_nifti', 'inputnode.name_source'),
                (anat, 'inputnode.overlay_file'),
            ]),
            (resample_bold_to_anat, plot_anat_on_task_wf, [
                ('out_file', 'inputnode.underlay_file'),
            ]),
        ])  # fmt:skip

        plot_task_on_anat_wf = init_plot_overlay_wf(
            desc=f'TaskOn{anat[0].upper()}{anat[1:]}',
            name=f'plot_task_on_{anat}_wf',
        )
        workflow.connect([
            (inputnode, plot_task_on_anat_wf, [
                ('preproc_nifti', 'inputnode.name_source'),
                (anat, 'inputnode.underlay_file'),
            ]),
            (resample_bold_to_anat, plot_task_on_anat_wf, [
                ('out_file', 'inputnode.overlay_file'),
            ]),
        ])  # fmt:skip

    return workflow
