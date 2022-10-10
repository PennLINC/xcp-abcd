# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Workflows for generating the executive summary."""
import fnmatch
import glob
import os

from nipype import Function
from nipype.interfaces import utility as niu
from nipype.pipeline import engine as pe
from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from templateflow.api import get as get_template

from xcp_d.interfaces.bids import DerivativesDataSink
from xcp_d.interfaces.connectivity import ApplyTransformsx
from xcp_d.interfaces.surfplotting import (
    BrainPlotx,
    PlotImage,
    PlotSVGData,
    RibbontoStatmap,
)
from xcp_d.utils.doc import fill_doc
from xcp_d.utils.utils import get_transformfile


@fill_doc
def init_brainsprite_wf(output_dir, mem_gb, omp_nthreads, name="init_brainsprite_wf"):
    """Create a brainsprite figure from stuff.

    Parameters
    ----------
    %(output_dir)s
    %(mem_gb)s
    %(omp_nthreads)s
    %(name)s
        Default is "init_brainsprite_wf".

    Inputs
    ------
    t1w
    ribbon
    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(fields=["t1w", "ribbon"]),
        name="inputnode",
    )
    ribbon2statmap_wf = pe.Node(
        RibbontoStatmap(),
        name="ribbon2statmap",
        mem_gb=mem_gb,
        n_procs=omp_nthreads,
    )
    generate_brainsprite = pe.Node(
        BrainPlotx(),
        name="brainsprite",
        mem_gb=mem_gb,
        n_procs=omp_nthreads,
    )
    ds_brainspriteplot_wf = pe.Node(
        DerivativesDataSink(
            base_directory=output_dir,
            check_hdr=False,
            dismiss_entities=["desc"],
            desc="brainplot",
            datatype="figures",
        ),
        name="brainspriteplot",
    )

    workflow.connect(
        [
            (inputnode, generate_brainsprite, [("t1w", "template")]),
            (inputnode, ribbon2statmap_wf, [("ribbon", "ribbon")]),
            (ribbon2statmap_wf, generate_brainsprite, [("out_file", "in_file")]),
            (generate_brainsprite, ds_brainspriteplot_wf, [("out_html", "in_file")]),
            (inputnode, ds_brainspriteplot_wf, [("t1w", "source_file")]),
        ]
    )

    return workflow


@fill_doc
def init_execsummary_wf(omp_nthreads,
                        bold_file,
                        output_dir,
                        TR,
                        mem_gb,
                        layout,
                        name='execsummary_wf'):
    """Generate an executive summary.

    Parameters
    ----------
    %(omp_nthreads)s
    bold_file
    %(output_dir)s
    TR
    %(mem_gb)s
    layout
    %(name)s

    Inputs
    ------
    t1w
    t1seg
    regressed_data
    residual_data
    fd
    rawdata
    mask
    %(mni_to_t1w)s
    """
    workflow = Workflow(name=name)

    inputnode = pe.Node(niu.IdentityInterface(fields=[
        't1w', 't1seg', 'regressed_data', 'residual_data', 'fd', 'rawdata', 'mask', 'mni_to_t1w'
    ]),
        name='inputnode')
    inputnode.inputs.bold_file = bold_file

    # Get bb_registration_file prefix from fmriprep
    all_files = list(layout.get_files())
    current_bold_file = os.path.basename(bold_file)
    if '_space' in current_bold_file:
        bb_register_prefix = current_bold_file.split('_space')[0]
    else:
        bb_register_prefix = current_bold_file.split('_desc')[0]

    # check if there is a bb_registration_file or coregister file
    patterns = ('*bbregister_bold.svg', '*coreg_bold.svg', '*bbr_bold.svg')
    registration_file = [
        pat for pat in patterns if fnmatch.filter(all_files, pat)
    ]
    #  Get the T1w registration file
    bold_t1w_registration_file = fnmatch.filter(all_files,
                                                '*' + bb_register_prefix + registration_file[0])[0]

    # Get the nifti reference file
    if bold_file.endswith('.nii.gz'):
        bold_reference_file = bold_file.split(
            'desc-preproc_bold.nii.gz')[0] + 'boldref.nii.gz'

    else:  # Get the cifti reference file
        bb_file_prefix = bold_file.split('space-fsLR_den-91k_bold.dtseries.nii')[0]
        bold_reference_file = glob.glob(bb_file_prefix + '*boldref.nii.gz')[0]
        bold_file = glob.glob(bb_file_prefix + '*preproc_bold.nii.gz')[0]

    # Plot the reference bold image
    plotrefbold_wf = pe.Node(PlotImage(in_file=bold_reference_file), name='plotrefbold_wf')

    # Get the transform file to native space
    get_std2native_transform = pe.Node(
        Function(
            input_names=["bold_file", "mni_to_t1w", "t1w_to_native"],
            output_names=["transform_list"],
            function=get_transformfile,
        ),
        name="get_std2native_transform",
    )
    get_std2native_transform.inputs.bold_file = bold_file
    get_std2native_transform.inputs.t1w_to_native = t1_to_native(bold_file)

    # Transform the file to native space
    resample_parc = pe.Node(ApplyTransformsx(
        dimension=3,
        input_image=str(
            get_template('MNI152NLin2009cAsym',
                         resolution=1,
                         desc='carpet',
                         suffix='dseg',
                         extension=['.nii', '.nii.gz'])),
        interpolation='MultiLabel',
        reference_image=bold_reference_file),
        name='resample_parc',
        n_procs=omp_nthreads,
        mem_gb=mem_gb * 3 * omp_nthreads)

    # Plot the SVG files
    plot_svgx_wf = pe.Node(PlotSVGData(TR=TR, rawdata=bold_file),
                           name='plot_svgx_wf',
                           mem_gb=mem_gb,
                           n_procs=omp_nthreads)

    # Write out the necessary files:
    # Reference file
    ds_plot_bold_reference_file_wf = pe.Node(DerivativesDataSink(base_directory=output_dir,
                                                                 dismiss_entities=['den'],
                                                                 datatype="figures",
                                                                 desc='boldref'),
                                             name='plotbold_reference_file',
                                             run_without_submitting=True)

    # Plot SVG before
    ds_plot_svg_before_wf = pe.Node(DerivativesDataSink(base_directory=output_dir,
                                                        dismiss_entities=['den'],
                                                        datatype="figures",
                                                        desc='precarpetplot'),
                                    name='plot_svgxbe',
                                    run_without_submitting=True)
    # Plot SVG after
    ds_plot_svg_after_wf = pe.Node(DerivativesDataSink(base_directory=output_dir,
                                                       dismiss_entities=['den'],
                                                       datatype="figures",
                                                       desc='postcarpetplot'),
                                   name='plot_svgx_after',
                                   run_without_submitting=True)
    # Bold T1 registration file
    ds_registration_wf = pe.Node(DerivativesDataSink(base_directory=output_dir,
                                                     in_file=bold_t1w_registration_file,
                                                     dismiss_entities=['den'],
                                                     datatype="figures",
                                                     desc='bbregister'),
                                 name='bb_registration_file',
                                 run_without_submitting=True)

    # Connect all the workflows
    workflow.connect([
        (plotrefbold_wf, ds_plot_bold_reference_file_wf, [('out_file', 'in_file')]),
        (inputnode, plot_svgx_wf, [('fd', 'fd'), ('regressed_data', 'regressed_data'),
                                   ('residual_data', 'residual_data'), ('mask', 'mask'),
                                   ('bold_file', 'rawdata')]),
        (inputnode, get_std2native_transform, [('mni_to_t1w', 'mni_to_t1w')]),
        (get_std2native_transform, resample_parc, [('transform_list', 'transforms')]),
        (resample_parc, plot_svgx_wf, [('output_image', 'seg_data')]),
        (plot_svgx_wf, ds_plot_svg_before_wf, [('before_process', 'in_file')]),
        (plot_svgx_wf, ds_plot_svg_after_wf, [('after_process', 'in_file')]),
        (inputnode, ds_plot_svg_before_wf, [('bold_file', 'source_file')]),
        (inputnode, ds_plot_svg_after_wf, [('bold_file', 'source_file')]),
        (inputnode, ds_plot_bold_reference_file_wf, [('bold_file', 'source_file')]),
        (inputnode, ds_registration_wf, [('bold_file', 'source_file')]),
    ])

    return workflow


def t1_to_native(file_name):
    """Get t1 to native transform file."""
    dir_name = os.path.dirname(file_name)
    filename = os.path.basename(file_name)
    file_name_prefix = filename.split('desc-preproc_bold.nii.gz')[0].split('space-')[0]
    t1_to_native_file = dir_name + '/' \
        + file_name_prefix + 'from-T1w_to-scanner_mode-image_xfm.txt'
    return t1_to_native_file
