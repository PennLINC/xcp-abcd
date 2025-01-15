"""The XCP-D preprocessing worklow.

XCP-D preprocessing workflow
============================
"""

import os
import sys

from xcp_d import config
from xcp_d.data import load as load_data


def _build_parser():
    """Build parser object."""
    from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
    from functools import partial
    from pathlib import Path

    from packaging.version import Version

    from xcp_d.cli import parser_utils
    from xcp_d.cli.version import check_latest, is_flagged
    from xcp_d.utils.atlas import select_atlases

    verstr = f'XCP-D v{config.environment.version}'
    currentv = Version(config.environment.version)
    is_release = not any((currentv.is_devrelease, currentv.is_prerelease, currentv.is_postrelease))

    parser = ArgumentParser(
        description=f'XCP-D: Postprocessing Workflow of fMRI Data v{config.environment.version}',
        epilog='See https://xcp-d.readthedocs.io/en/latest/workflows.html',
        formatter_class=ArgumentDefaultsHelpFormatter,
    )
    PathExists = partial(parser_utils._path_exists, parser=parser)
    IsFile = partial(parser_utils._is_file, parser=parser)
    PositiveInt = partial(parser_utils._min_one, parser=parser)
    BIDSFilter = partial(parser_utils._bids_filter, parser=parser)

    # important parameters required
    parser.add_argument(
        'fmri_dir',
        action='store',
        type=PathExists,
        help=(
            'The root folder of fMRI preprocessing derivatives. '
            "For example, '/path/to/dset/derivatives/fmriprep'."
        ),
    )
    parser.add_argument(
        'output_dir',
        action='store',
        type=Path,
        help=(
            'The output path for XCP-D derivatives. '
            "For example, '/path/to/dset/derivatives/xcp_d'. "
            "As of version 0.7.0, 'xcp_d' will not be appended to the output directory."
        ),
    )
    parser.add_argument(
        'analysis_level',
        action='store',
        choices=['participant'],
        help="The analysis level for XCP-D. Must be specified as 'participant'.",
    )

    # Required "mode" argument
    required = parser.add_argument_group('required arguments')
    required.add_argument(
        '--mode',
        dest='mode',
        action='store',
        choices=['abcd', 'hbcd', 'linc', 'nichart', 'none'],
        required=True,
        help=(
            'The mode of operation for XCP-D. '
            'The mode sets several parameters, with values specific to different pipelines. '
            'For more information, see the documentation at '
            'https://xcp-d.readthedocs.io/en/latest/workflows.html#modes'
        ),
    )

    # optional arguments
    parser.add_argument('--version', action='version', version=verstr)

    g_bids = parser.add_argument_group('Options for filtering BIDS queries')
    g_bids.add_argument(
        '--participant-label',
        '--participant_label',
        dest='participant_label',
        action='store',
        nargs='+',
        type=lambda label: label.removeprefix('sub-'),
        help=(
            'A space-delimited list of participant identifiers, or a single identifier. '
            "The 'sub-' prefix can be removed."
        ),
    )
    g_bids.add_argument(
        '-t',
        '--task-id',
        '--task_id',
        dest='task_id',
        action='store',
        help=(
            'The name of a specific task to postprocess. '
            'By default, all tasks will be postprocessed. '
            'If you want to select more than one task to postprocess (but not all of them), '
            'you can either run XCP-D with the --task-id parameter, separately for each task, '
            'or you can use the --bids-filter-file to specify the tasks to postprocess.'
        ),
    )
    g_bids.add_argument(
        '--bids-filter-file',
        '--bids_filter_file',
        dest='bids_filters',
        action='store',
        type=BIDSFilter,
        default=None,
        metavar='FILE',
        help=(
            'A JSON file describing custom BIDS input filters using PyBIDS. '
            'For further details, please check out '
            'https://xcp-d.readthedocs.io/en/'
            f'{currentv.base_version if is_release else "latest"}/usage.html#'
            'filtering-inputs-with-bids-filter-files'
        ),
    )
    g_bids.add_argument(
        '-d',
        '--datasets',
        action=parser_utils.ToDict,
        metavar='PACKAGE=PATH',
        type=str,
        nargs='+',
        help=(
            'Search PATH(s) for derivatives or atlas datasets. '
            'These may be provided as named folders '
            '(e.g., `--datasets smriprep=/path/to/smriprep`).'
        ),
    )
    g_bids.add_argument(
        '--bids-database-dir',
        metavar='PATH',
        type=Path,
        help=(
            'Path to a PyBIDS database folder, for faster indexing '
            '(especially useful for large datasets). '
            'Will be created if not present.'
        ),
    )

    g_perfm = parser.add_argument_group('Options for resource management')
    g_perfm.add_argument(
        '--nprocs',
        '--nthreads',
        '--n-cpus',
        '--n_cpus',
        dest='nprocs',
        action='store',
        type=int,
        default=2,
        help='Maximum number of threads across all processes.',
    )
    g_perfm.add_argument(
        '--omp-nthreads',
        '--omp_nthreads',
        dest='omp_nthreads',
        action='store',
        type=int,
        default=1,
        help='Maximum number of threads per process.',
    )
    g_perfm.add_argument(
        '--mem-gb',
        '--mem_gb',
        dest='memory_gb',
        action='store',
        type=int,
        help='Upper bound memory limit, in gigabytes, for XCP-D processes.',
    )
    g_perfm.add_argument(
        '--low-mem',
        dest='low_mem',
        action='store_true',
        help='Attempt to reduce memory usage (will increase disk usage in working directory).',
    )
    g_perfm.add_argument(
        '--use-plugin',
        '--use_plugin',
        '--nipype-plugin-file',
        '--nipype_plugin_file',
        dest='use_plugin',
        action='store',
        default=None,
        type=IsFile,
        help=(
            'Nipype plugin configuration file. '
            'For more information, see https://nipype.readthedocs.io/en/0.11.0/users/plugins.html.'
        ),
    )
    g_perfm.add_argument(
        '-v',
        '--verbose',
        dest='verbose_count',
        action='count',
        default=0,
        help="Increases log verbosity for each occurrence. Debug level is '-vvv'.",
    )

    g_outputoption = parser.add_argument_group('Input flags')
    g_outputoption.add_argument(
        '--input-type',
        '--input_type',
        dest='input_type',
        required=False,
        default='auto',
        choices=['fmriprep', 'dcan', 'hcp', 'nibabies', 'ukb'],
        help=(
            'The pipeline used to generate the preprocessed derivatives. '
            "The default pipeline is 'fmriprep'. "
            "The 'dcan', 'hcp', 'nibabies', and 'ukb' pipelines are also supported. "
            "'nibabies' assumes the same structure as 'fmriprep'."
        ),
    )
    g_outputoption.add_argument(
        '--file-format',
        dest='file_format',
        action='store',
        default='auto',
        choices=['auto', 'cifti', 'nifti'],
        help=(
            'The file format of the input data. '
            "If 'auto', the file format will be inferred from the processing mode. "
            "If 'cifti', the input data are assumed to be in CIFTI format. "
            "If 'nifti', the input data are assumed to be in NIfTI format."
        ),
    )

    g_param = parser.add_argument_group('Postprocessing parameters')
    g_param.add_argument(
        '--dummy-scans',
        '--dummy_scans',
        dest='dummy_scans',
        default=0,
        type=parser_utils._int_or_auto,
        metavar='{{auto,INT}}',
        help=(
            'Number of volumes to remove from the beginning of each run. '
            "If set to 'auto', XCP-D will extract non-steady-state volume indices from the "
            "preprocessing derivatives' confounds file."
        ),
    )
    g_param.add_argument(
        '--despike',
        dest='despike',
        nargs='?',
        const=None,
        default='auto',
        choices=['y', 'n'],
        action=parser_utils.YesNoAction,
        help=(
            'Despike the BOLD data before postprocessing. '
            "If not defined, the despike option will be inferred from the 'mode'. "
            'If defined without an argument, despiking will be enabled. '
            'If defined with an argument (y or n), the value of the argument will be used. '
            "'y' enables despiking. 'n' disables despiking."
        ),
    )
    g_param.add_argument(
        '-p',
        '--nuisance-regressors',
        '--nuisance_regressors',
        dest='confounds_config',
        required=False,
        action=parser_utils.ConfoundsAction,
        default='auto',
        help=(
            'Nuisance parameters to be selected. '
            "This may be a string indicating one of XCP-D's built-in nuisance regression "
            "strategies (e.g., '36P') or a path to a YAML file formatted according to XCP-D's "
            'confound configuration file format. '
            "Descriptions of each of the built-in options are included in XCP-D's documentation. "
        ),
    )
    g_param.add_argument(
        '--smoothing',
        dest='smoothing',
        default='auto',
        action='store',
        type=parser_utils._float_or_auto,
        metavar='{{auto,FLOAT}}',
        help=(
            'FWHM, in millimeters, of the Gaussian smoothing kernel to apply to the denoised BOLD '
            'data. '
            'Set to 0 to disable smoothing.'
        ),
    )
    g_param.add_argument(
        '-m',
        '--combine-runs',
        '--combine_runs',
        dest='combine_runs',
        nargs='?',
        const=None,
        default='auto',
        choices=['y', 'n'],
        action=parser_utils.YesNoAction,
        help='After denoising, concatenate each derivative from each task across runs.',
    )

    g_motion_filter = parser.add_argument_group(
        title='Motion filtering parameters',
        description=(
            'These parameters enable and control a filter that will be applied to motion '
            'parameters. '
            'Motion parameters may be contaminated by non-motion noise, and applying a filter '
            'may reduce the impact of that contamination.'
        ),
    )
    g_motion_filter.add_argument(
        '--motion-filter-type',
        '--motion_filter_type',
        dest='motion_filter_type',
        action='store',
        type=str,
        default=None,
        choices=['lp', 'notch', 'none'],
        help="""\
Type of filter to use for removing respiratory artifact from motion regressors.
If not set, no filter will be applied.

If the filter type is set to "notch", then both ``band-stop-min`` and ``band-stop-max``
must be defined.
If the filter type is set to "lp", then only ``band-stop-min`` must be defined.
If the filter type is set to "none", then no filter will be applied.
""",
    )
    g_motion_filter.add_argument(
        '--band-stop-min',
        '--band_stop_min',
        dest='band_stop_min',
        default=None,
        type=float,
        metavar='BPM',
        help="""\
Lower frequency for the motion parameter filter, in breaths-per-minute (bpm).
Motion filtering is only performed if ``motion-filter-type`` is not None.
If used with the "lp" ``motion-filter-type``, this parameter essentially corresponds to a
low-pass filter (the maximum allowed frequency in the filtered data).
This parameter is used in conjunction with ``motion-filter-order`` and ``band-stop-max``.

When ``motion-filter-type`` is set to "lp" (low-pass filter), another commonly-used value for
this parameter is 6 BPM (equivalent to 0.1 Hertz), based on Gratton et al. (2020).
""",
    )
    g_motion_filter.add_argument(
        '--band-stop-max',
        '--band_stop_max',
        dest='band_stop_max',
        default=None,
        type=float,
        metavar='BPM',
        help="""\
Upper frequency for the band-stop motion filter, in breaths-per-minute (bpm).
Motion filtering is only performed if ``motion-filter-type`` is not None.
This parameter is only used if ``motion-filter-type`` is set to "notch".
This parameter is used in conjunction with ``motion-filter-order`` and ``band-stop-min``.
""",
    )
    g_motion_filter.add_argument(
        '--motion-filter-order',
        '--motion_filter_order',
        dest='motion_filter_order',
        default=4,
        type=int,
        help=(
            'Number of filter coefficients for the motion parameter filter. '
            "If the motion filter type is 'lp', the order is divided by 2 as filtfilt applies "
            'the filter twice. '
            "If the motion filter type is 'notch', the order is divided by 4 as iirnotch is a "
            'second-order filter and filtfilt applies the filter twice. '
            "Make sure to set this parameter to a multiple of 2 if you choose the 'lp' filter and "
            "a multiple of 4 if you choose the 'notch' filter."
        ),
    )

    g_censor = parser.add_argument_group('Censoring and scrubbing options')
    g_censor.add_argument(
        '-r',
        '--head-radius',
        '--head_radius',
        dest='head_radius',
        default=50,
        type=parser_utils._float_or_auto,
        help=(
            'Head radius used to calculate framewise displacement, in mm. '
            'The default value is 50 mm, which is recommended for adults. '
            'For infants, we recommend a value of 35 mm. '
            "A value of 'auto' is also supported, in which case the brain radius is "
            'estimated from the preprocessed brain mask by treating the mask as a sphere.'
        ),
    )
    g_censor.add_argument(
        '-f',
        '--fd-thresh',
        '--fd_thresh',
        dest='fd_thresh',
        default='auto',
        type=parser_utils._float_or_auto,
        help=(
            'Framewise displacement threshold for censoring. '
            'Any volumes with an FD value greater than the threshold will be removed from the '
            'denoised BOLD data. '
            'A threshold of <=0 will disable censoring completely.'
        ),
    )
    g_censor.add_argument(
        '--min-time',
        '--min_time',
        dest='min_time',
        required=False,
        default=240,
        type=float,
        help="""\
Post-scrubbing threshold to apply to individual runs in the dataset.
This threshold determines the minimum amount of time, in seconds,
needed to post-process a given run, once high-motion outlier volumes are removed.
This will have no impact if scrubbing is disabled
(i.e., if the FD threshold is zero or negative).
This parameter can be disabled by providing a zero or a negative value.

The default is 240 (4 minutes).
""",
    )
    g_censor.add_argument(
        '--output-type',
        '--output_type',
        dest='output_type',
        default='auto',
        action='store',
        choices=['auto', 'censored', 'interpolated'],
        help=(
            'The type of output to generate. '
            "If 'auto', the output type will be inferred from the processing mode. "
            "If 'censored', the BOLD outputs (dense and parcellated time series) will be "
            'censored. '
            "If 'interpolated', the BOLD outputs (dense and parcellated time series) will be "
            'interpolated.'
        ),
    )

    g_temporal_filter = parser.add_argument_group(
        title='Data filtering parameters',
        description=(
            'These parameters determine whether a bandpass filter will be applied to the BOLD '
            'data, after the censoring, denoising, and interpolation steps of the pipeline, '
            'but before recensoring.'
        ),
    )
    g_temporal_filter.add_argument(
        '--disable-bandpass-filter',
        '--disable_bandpass_filter',
        dest='bandpass_filter',
        action='store_false',
        help=(
            'Disable bandpass filtering. '
            'If bandpass filtering is disabled, then ALFF derivatives will not be calculated.'
        ),
    )
    g_temporal_filter.add_argument(
        '--lower-bpf',
        '--lower_bpf',
        action='store',
        default=0.01,
        dest='high_pass',
        type=float,
        help=(
            'Lower cut-off frequency (Hz) for the Butterworth bandpass filter to be applied to '
            'the denoised BOLD data. Set to 0.0 or negative to disable high-pass filtering. '
            'See Satterthwaite et al. (2013).'
        ),
    )
    g_temporal_filter.add_argument(
        '--upper-bpf',
        '--upper_bpf',
        action='store',
        default=0.08,
        dest='low_pass',
        type=float,
        help=(
            'Upper cut-off frequency (Hz) for the Butterworth bandpass filter to be applied to '
            'the denoised BOLD data. Set to 0.0 or negative to disable low-pass filtering. '
            'See Satterthwaite et al. (2013).'
        ),
    )
    g_temporal_filter.add_argument(
        '--bpf-order',
        '--bpf_order',
        dest='bpf_order',
        action='store',
        default=2,
        type=int,
        help='Number of filter coefficients for the Butterworth bandpass filter.',
    )

    g_parcellation = parser.add_argument_group('Parcellation options')

    g_atlases = g_parcellation.add_mutually_exclusive_group(required=False)
    all_atlases = select_atlases(atlases=None, subset='all')
    g_atlases.add_argument(
        '--atlases',
        action='store',
        nargs='+',
        metavar='ATLAS',
        default=all_atlases,
        dest='atlases',
        help=(
            'Selection of atlases to apply to the data. '
            "All of XCP-D's built-in atlases are used by default."
        ),
    )
    g_atlases.add_argument(
        '--skip-parcellation',
        '--skip_parcellation',
        action='store_const',
        const=[],
        dest='atlases',
        help='Skip parcellation and correlation steps.',
    )

    g_parcellation.add_argument(
        '--min-coverage',
        '--min_coverage',
        dest='min_coverage',
        required=False,
        default='auto',
        type=parser_utils._restricted_float,
        metavar='{auto,FLOAT}',
        help=(
            'Coverage threshold to apply to parcels in each atlas. '
            'Any parcels with lower coverage than the threshold will be replaced with NaNs. '
            'Must be a value between zero and one, indicating proportion of the parcel.'
        ),
    )

    g_dcan = parser.add_argument_group('abcd/hbcd mode options')
    g_dcan.add_argument(
        '--create-matrices',
        '--create_matrices',
        dest='correlation_lengths',
        required=False,
        default=None,
        nargs='+',
        type=parser_utils._float_or_auto_or_none,
        help="""\
If used, this parameter will produce correlation matrices limited to each requested amount of time.
If there is more than the required amount of low-motion data,
then volumes will be randomly selected to produce denoised outputs with the exact
amounts of time requested.
If there is less than the required amount of 'good' data,
then the corresponding correlation matrix will not be produced.

This option is only allowed for the "abcd" and "hbcd" modes.
""",
    )
    g_dcan.add_argument(
        '--random-seed',
        '--random_seed',
        dest='random_seed',
        default=None,
        type=int,
        metavar='_RANDOM_SEED',
        help="Initialize the random seed for the '--create-matrices' option.",
    )
    g_dcan.add_argument(
        '--linc-qc',
        '--linc_qc',
        nargs='?',
        const=None,
        default='auto',
        choices=['y', 'n'],
        action=parser_utils.YesNoAction,
        dest='linc_qc',
        help="""\
Run LINC QC.

This will calculate QC metrics from the LINC pipeline.
""",
    )

    g_linc = parser.add_argument_group('linc mode options')
    g_linc.add_argument(
        '--abcc-qc',
        '--abcc_qc',
        nargs='?',
        const=None,
        default='auto',
        choices=['y', 'n'],
        action=parser_utils.YesNoAction,
        dest='abcc_qc',
        help="""\
Run ABCC QC.

This will create the DCAN executive summary, including a brainsprite visualization of the
anatomical tissue segmentation, and an HDF5 file containing motion levels at different thresholds.
""",
    )

    g_other = parser.add_argument_group('Other options')
    g_other.add_argument(
        '--aggregate-session-reports',
        dest='aggr_ses_reports',
        action='store',
        type=PositiveInt,
        default=4,
        help=(
            "Maximum number of sessions aggregated in one subject's visual report. "
            'If exceeded, visual reports are split by session.'
        ),
    )
    g_other.add_argument(
        '-w',
        '--work-dir',
        '--work_dir',
        dest='work_dir',
        action='store',
        type=Path,
        default=Path('working_dir'),
        help='Path to working directory, where intermediate results should be stored.',
    )
    g_other.add_argument(
        '--clean-workdir',
        '--clean_workdir',
        dest='clean_workdir',
        action='store_true',
        default=False,
        help=(
            'Clears working directory of contents. '
            'Use of this flag is not recommended when running concurrent processes of XCP-D.'
        ),
    )
    g_other.add_argument(
        '--resource-monitor',
        '--resource_monitor',
        dest='resource_monitor',
        action='store_true',
        default=False,
        help="Enable Nipype's resource monitoring to keep track of memory and CPU usage.",
    )
    g_other.add_argument(
        '--config-file',
        '--config_file',
        dest='config_file',
        action='store',
        metavar='FILE',
        help=(
            'Use pre-generated configuration file. '
            'Values in file will be overridden by command-line arguments.'
        ),
    )
    g_other.add_argument(
        '--write-graph',
        dest='write_graph',
        action='store_true',
        default=False,
        help='Write workflow graph.',
    )
    g_other.add_argument(
        '--stop-on-first-crash',
        dest='stop_on_first_crash',
        action='store_true',
        default=False,
        help='Force stopping on first crash, even if a work directory was specified.',
    )
    g_other.add_argument(
        '--notrack',
        dest='notrack',
        action='store_true',
        default=False,
        help='Opt out of sending tracking information.',
    )
    g_other.add_argument(
        '--debug',
        dest='debug',
        action='store',
        nargs='+',
        choices=config.DEBUG_MODES + ('all',),
        help="Debug mode(s) to enable. 'all' is alias for all available modes.",
    )
    g_other.add_argument(
        '--fs-license-file',
        dest='fs_license_file',
        metavar='FILE',
        type=PathExists,
        help=(
            'Path to FreeSurfer license key file. Get it (for free) by registering '
            'at https://surfer.nmr.mgh.harvard.edu/registration.html. '
            'This is not currently required, but may be in the future.'
        ),
    )
    g_other.add_argument(
        '--md-only-boilerplate',
        dest='md_only_boilerplate',
        action='store_true',
        default=False,
        help='Skip generation of HTML and LaTeX formatted citation with pandoc',
    )
    g_other.add_argument(
        '--boilerplate-only',
        '--boilerplate_only',
        dest='boilerplate_only',
        action='store_true',
        default=False,
        help='generate boilerplate only',
    )
    g_other.add_argument(
        '--reports-only',
        dest='reports_only',
        action='store_true',
        default=False,
        help=(
            "only generate reports, don't run workflows. This will only rerun report "
            'aggregation, not reportlet generation for specific nodes.'
        ),
    )

    g_experimental = parser.add_argument_group('Experimental options')

    g_experimental.add_argument(
        '--warp-surfaces-native2std',
        '--warp_surfaces_native2std',
        dest='process_surfaces',
        nargs='?',
        const=None,
        default='auto',
        choices=['y', 'n'],
        action=parser_utils.YesNoAction,
        help="""\
If used, a workflow will be run to warp native-space (``fsnative``) reconstructed cortical
surfaces (``surf.gii`` files) produced by Freesurfer into standard (``fsLR``) space.
Additionally, the fsLR-space surfaces will be warped such that they can be overlaid on the
MNI152NLin6Asym template.
These surface files are primarily used for visual quality assessment.

**IMPORTANT**: This parameter can only be run if the --file-format flag is set to cifti.
""",
    )

    latest = check_latest()
    if latest is not None and currentv < latest:
        print(
            f"""\
You are using XCP-D v{currentv}, and a newer version of XCP-D is available: v{latest}.
Please check out our documentation about how and when to upgrade:
https://xcp-d.readthedocs.io/en/latest/faq.html#upgrading""",
            file=sys.stderr,
        )

    _blist = is_flagged()
    if _blist[0]:
        _reason = _blist[1] or 'unknown'
        print(
            f"""\
WARNING: Version {config.environment.version} of XCP-D (current) has been FLAGGED
(reason: {_reason}).
That means some severe flaw was found in it and we strongly
discourage its usage.""",
            file=sys.stderr,
        )

    return parser


def parse_args(args=None, namespace=None):
    """Parse args and run further checks on the command line."""
    import logging

    parser = _build_parser()
    opts = parser.parse_args(args, namespace)
    if opts.config_file:
        skip = {} if opts.reports_only else {'execution': ('run_uuid',)}
        config.load(opts.config_file, skip=skip, init=False)
        config.loggers.cli.info(f'Loaded previous configuration file {opts.config_file}')

    opts = _validate_parameters(opts=opts, build_log=config.loggers.cli, parser=parser)

    # Wipe out existing work_dir
    if opts.clean_workdir and opts.work_dir.exists():
        from niworkflows.utils.misc import clean_directory

        config.loggers.cli.info(f'Clearing previous XCP-D working directory: {opts.work_dir}')
        if not clean_directory(opts.work_dir):
            config.loggers.cli.warning(
                f'Could not clear all contents of working directory: {opts.work_dir}'
            )

    # First check that fmriprep_dir looks like a BIDS folder
    if opts.input_type in ('dcan', 'hcp', 'ukb'):
        if opts.input_type == 'dcan':
            from xcp_d.ingression.abcdbids import convert_dcan2bids as convert_to_bids
        elif opts.input_type == 'hcp':
            from xcp_d.ingression.hcpya import convert_hcp2bids as convert_to_bids
        elif opts.input_type == 'ukb':
            from xcp_d.ingression.ukbiobank import convert_ukb2bids as convert_to_bids

        converted_fmri_dir = opts.work_dir / f'dset_bids/derivatives/{opts.input_type}'
        converted_fmri_dir.mkdir(exist_ok=True, parents=True)

        convert_to_bids(
            opts.fmri_dir,
            out_dir=str(converted_fmri_dir),
            participant_ids=opts.participant_label,
        )

        opts.fmri_dir = converted_fmri_dir
        assert converted_fmri_dir.exists(), f'Conversion to BIDS failed: {converted_fmri_dir}'

    if not os.path.isfile(os.path.join(opts.fmri_dir, 'dataset_description.json')):
        config.loggers.cli.error(
            'No dataset_description.json file found in input directory. '
            "Make sure to point to the specific pipeline's derivatives folder. "
            "For example, use '/dset/derivatives/fmriprep', not /dset/derivatives'."
        )

    config.execution.log_level = int(max(25 - 5 * opts.verbose_count, logging.DEBUG))
    config.from_dict(vars(opts), init=['nipype'])
    assert config.execution.fmri_dir.exists(), (
        f'Conversion to BIDS failed: {config.execution.fmri_dir}',
    )

    # Retrieve logging level
    build_log = config.loggers.cli

    # Load base plugin_settings from file if --use-plugin
    if opts.use_plugin is not None:
        import yaml

        with open(opts.use_plugin) as f:
            plugin_settings = yaml.safe_load(f)

        _plugin = plugin_settings.get('plugin')
        if _plugin:
            config.nipype.plugin = _plugin
            config.nipype.plugin_args = plugin_settings.get('plugin_args', {})
            config.nipype.nprocs = opts.nprocs or config.nipype.plugin_args.get(
                'n_procs', config.nipype.nprocs
            )

    # Resource management options
    # Note that we're making strong assumptions about valid plugin args
    # This may need to be revisited if people try to use batch plugins
    if 1 < config.nipype.nprocs < config.nipype.omp_nthreads:
        build_log.warning(
            f'Per-process threads (--omp-nthreads={config.nipype.omp_nthreads}) exceed '
            f'total threads (--nthreads/--n_cpus={config.nipype.nprocs})'
        )

    fmri_dir = config.execution.fmri_dir
    output_dir = config.execution.output_dir
    work_dir = config.execution.work_dir
    version = config.environment.version

    # Update the config with an empty dict to trigger initialization of all config
    # sections (we used `init=False` above).
    # This must be done after cleaning the work directory, or we could delete an
    # open SQLite database
    config.from_dict({})

    # Ensure input and output folders are not the same
    if output_dir == fmri_dir:
        rec_path = fmri_dir / 'derivatives' / f'xcp_d-{version.split("+")[0]}'
        parser.error(
            'The selected output folder is the same as the input BIDS folder. '
            f'Please modify the output path (suggestion: {rec_path}).'
        )

    if fmri_dir in work_dir.parents:
        parser.error(
            'The selected working directory is a subdirectory of the input BIDS folder. '
            'Please modify the output path.'
        )

    # Setup directories
    config.execution.log_dir = config.execution.output_dir / 'logs'
    # Check and create output and working directories
    config.execution.log_dir.mkdir(exist_ok=True, parents=True)
    output_dir.mkdir(exist_ok=True, parents=True)
    work_dir.mkdir(exist_ok=True, parents=True)

    # Force initialization of the BIDSLayout
    config.execution.init()
    all_subjects = config.execution.layout.get_subjects()
    if config.execution.participant_label is None:
        config.execution.participant_label = all_subjects

    participant_label = set(config.execution.participant_label)
    missing_subjects = participant_label - set(all_subjects)
    if missing_subjects:
        parser.error(
            'One or more participant labels were not found in the BIDS directory: '
            f'{", ".join(missing_subjects)}.'
        )

    config.execution.participant_label = sorted(participant_label)


def _validate_parameters(opts, build_log, parser):
    """Validate parameters.

    This function was abstracted out of build_workflow to make testing easier.
    """
    import os
    from pathlib import Path

    opts.fmri_dir = opts.fmri_dir.resolve()
    opts.output_dir = opts.output_dir.resolve()
    opts.work_dir = opts.work_dir.resolve()

    error_messages = []

    # Set the FreeSurfer license
    if opts.fs_license_file is not None:
        opts.fs_license_file = opts.fs_license_file.resolve()
        if opts.fs_license_file.is_file():
            os.environ['FS_LICENSE'] = str(opts.fs_license_file)

        else:
            build_log.warning(f'Freesurfer license DNE: {opts.fs_license_file}.')
    else:
        fs_license_file = os.environ.get('FS_LICENSE', '/opt/freesurfer/license.txt')
        if not Path(fs_license_file).is_file():
            build_log.warning(
                'A valid FreeSurfer license file is recommended. '
                "Set the FS_LICENSE environment variable or use the '--fs-license-file' flag."
            )
        else:
            os.environ['FS_LICENSE'] = str(fs_license_file)

    # Check parameter value types/valid values
    assert opts.abcc_qc in (True, False, 'auto')
    assert opts.combine_runs in (True, False, 'auto')
    assert opts.despike in (True, False, 'auto')
    assert opts.file_format in ('nifti', 'cifti', 'auto')
    assert opts.linc_qc in (True, False, 'auto')
    assert opts.mode in (
        'abcd',
        'hbcd',
        'linc',
        'nichart',
        'none',
    ), f'Unsupported mode "{opts.mode}".'
    assert opts.output_type in ('censored', 'interpolated', 'auto')
    assert opts.process_surfaces in (True, False, 'auto')

    # Add internal atlas datasets to the list of datasets
    opts.datasets = opts.datasets or {}
    if opts.atlases:
        if 'xcpdatlases' not in opts.datasets:
            opts.datasets['xcpdatlases'] = load_data('atlases')

        if any(atlas.startswith('4S') for atlas in opts.atlases):
            if 'xcpd4s' not in opts.datasets:
                opts.datasets['xcpd4s'] = Path('/AtlasPack')

    # Check parameters based on the mode
    if opts.mode == 'abcd':
        opts.abcc_qc = True if (opts.abcc_qc == 'auto') else opts.abcc_qc
        opts.combine_runs = True if (opts.combine_runs == 'auto') else opts.combine_runs
        opts.confounds_config = (
            '36P' if (opts.confounds_config == 'auto') else opts.confounds_config
        )
        opts.correlation_lengths = opts.correlation_lengths if opts.correlation_lengths else []
        opts.despike = True if (opts.despike == 'auto') else opts.despike
        opts.fd_thresh = 0.3 if (opts.fd_thresh == 'auto') else opts.fd_thresh
        opts.file_format = 'cifti' if (opts.file_format == 'auto') else opts.file_format
        opts.input_type = 'fmriprep' if opts.input_type == 'auto' else opts.input_type
        opts.linc_qc = True if (opts.linc_qc == 'auto') else opts.linc_qc
        opts.min_coverage = 0.5 if opts.min_coverage == 'auto' else opts.min_coverage
        if opts.motion_filter_type is None:
            error_messages.append(f"'--motion-filter-type' is required for '{opts.mode}' mode.")
        if opts.output_type == 'censored':
            error_messages.append(f"'--output-type' cannot be 'censored' for '{opts.mode}' mode.")
        opts.output_type = 'interpolated'
        opts.process_surfaces = True if opts.process_surfaces == 'auto' else opts.process_surfaces
        opts.smoothing = 6 if opts.smoothing == 'auto' else opts.smoothing
    elif opts.mode == 'hbcd':
        opts.abcc_qc = True if (opts.abcc_qc == 'auto') else opts.abcc_qc
        opts.combine_runs = True if (opts.combine_runs == 'auto') else opts.combine_runs
        opts.confounds_config = (
            '36P' if (opts.confounds_config == 'auto') else opts.confounds_config
        )
        opts.correlation_lengths = opts.correlation_lengths if opts.correlation_lengths else []
        opts.despike = True if (opts.despike == 'auto') else opts.despike
        opts.fd_thresh = 0.3 if (opts.fd_thresh == 'auto') else opts.fd_thresh
        opts.file_format = 'cifti' if (opts.file_format == 'auto') else opts.file_format
        opts.input_type = 'nibabies' if opts.input_type == 'auto' else opts.input_type
        opts.linc_qc = True if (opts.linc_qc == 'auto') else opts.linc_qc
        opts.min_coverage = 0.5 if opts.min_coverage == 'auto' else opts.min_coverage
        if opts.motion_filter_type is None:
            error_messages.append(f"'--motion-filter-type' is required for '{opts.mode}' mode.")
        if opts.output_type == 'censored':
            error_messages.append(f"'--output-type' cannot be 'censored' for '{opts.mode}' mode.")
        opts.output_type = 'interpolated'
        opts.process_surfaces = True if opts.process_surfaces == 'auto' else opts.process_surfaces
        opts.smoothing = 6 if opts.smoothing == 'auto' else opts.smoothing
    elif opts.mode == 'linc':
        opts.abcc_qc = False if (opts.abcc_qc == 'auto') else opts.abcc_qc
        opts.combine_runs = False if opts.combine_runs == 'auto' else opts.combine_runs
        opts.confounds_config = (
            '36P' if (opts.confounds_config == 'auto') else opts.confounds_config
        )
        opts.despike = True if (opts.despike == 'auto') else opts.despike
        opts.fd_thresh = 0 if (opts.fd_thresh == 'auto') else opts.fd_thresh
        opts.file_format = 'cifti' if (opts.file_format == 'auto') else opts.file_format
        opts.input_type = 'fmriprep' if opts.input_type == 'auto' else opts.input_type
        opts.linc_qc = True if (opts.linc_qc == 'auto') else opts.linc_qc
        opts.min_coverage = 0.5 if opts.min_coverage == 'auto' else opts.min_coverage
        if opts.output_type == 'interpolated':
            error_messages.append(
                f"'--output-type' cannot be 'interpolated' for '{opts.mode}' mode."
            )
        opts.output_type = 'censored'
        opts.process_surfaces = False if opts.process_surfaces == 'auto' else opts.process_surfaces
        opts.smoothing = 6 if opts.smoothing == 'auto' else opts.smoothing
        if opts.correlation_lengths is not None:
            error_messages.append(f"'--create-matrices' is not supported for '{opts.mode}' mode.")
        # Patch 'all' into the list of correlation lengths
        opts.correlation_lengths = ['all']
    elif opts.mode == 'nichart':
        opts.abcc_qc = False if (opts.abcc_qc == 'auto') else opts.abcc_qc
        opts.combine_runs = False if opts.combine_runs == 'auto' else opts.combine_runs
        opts.confounds_config = (
            '36P' if (opts.confounds_config == 'auto') else opts.confounds_config
        )
        opts.correlation_lengths = opts.correlation_lengths if opts.correlation_lengths else 'all'
        opts.despike = True if (opts.despike == 'auto') else opts.despike
        opts.fd_thresh = 0 if (opts.fd_thresh == 'auto') else opts.fd_thresh
        opts.file_format = 'nifti' if (opts.file_format == 'auto') else opts.file_format
        opts.input_type = 'fmriprep' if opts.input_type == 'auto' else opts.input_type
        opts.linc_qc = True if (opts.linc_qc == 'auto') else opts.linc_qc
        opts.min_coverage = 0.4 if opts.min_coverage == 'auto' else opts.min_coverage
        opts.output_type = 'censored' if opts.output_type == 'auto' else opts.output_type
        opts.process_surfaces = False if opts.process_surfaces == 'auto' else opts.process_surfaces
        opts.smoothing = 0 if opts.smoothing == 'auto' else opts.smoothing
    elif opts.mode == 'none':
        if opts.abcc_qc == 'auto':
            error_messages.append("'--abcc-qc' (y or n) is required for 'none' mode.")

        if opts.combine_runs == 'auto':
            error_messages.append("'--combine-runs' (y or n) is required for 'none' mode.")

        if opts.confounds_config == 'auto':
            error_messages.append("'--nuisance-regressors' is required for 'none' mode.")

        opts.correlation_lengths = opts.correlation_lengths if opts.correlation_lengths else []

        if opts.despike == 'auto':
            error_messages.append("'--despike' (y or n) is required for 'none' mode.")

        if opts.fd_thresh == 'auto':
            error_messages.append("'--fd-thresh' is required for 'none' mode.")
            opts.fd_thresh = 0  # just to satisfy later checks, not to actually use

        if opts.file_format == 'auto':
            error_messages.append("'--file-format' is required for 'none' mode.")

        if opts.input_type == 'auto':
            error_messages.append("'--input-type' is required for 'none' mode.")

        if opts.linc_qc == 'auto':
            error_messages.append("'--linc-qc' (y or n) is required for 'none' mode.")

        if opts.min_coverage == 'auto':
            error_messages.append("'--min-coverage' is required for 'none' mode.")

        if opts.motion_filter_type is None:
            error_messages.append("'--motion-filter-type' is required for 'none' mode.")

        if opts.output_type == 'auto':
            error_messages.append("'--output-type' is required for 'none' mode.")

        if opts.process_surfaces == 'auto':
            error_messages.append(
                "'--warp-surfaces-native2std' (y or n) is required for 'none' mode."
            )

        if opts.smoothing == 'auto':
            error_messages.append("'--smoothing' is required for 'none' mode.")

    # Load the confound configuration file
    if opts.confounds_config == 'none':
        opts.confounds_config = None
    elif isinstance(opts.confounds_config, str):  # A builtin confound config
        opts.confounds_config = load_data.readable(f'nuisance/{opts.confounds_config}.yml')
    else:  # An external confound config
        opts.confounds_config = Path(opts.confounds_config).resolve()

    # Bandpass filter parameters
    if opts.high_pass <= 0 and opts.low_pass <= 0:
        opts.bandpass_filter = False

    if (
        opts.bandpass_filter
        and (opts.high_pass >= opts.low_pass)
        and (opts.high_pass > 0 and opts.low_pass > 0)
    ):
        parser.error(
            f"'--lower-bpf' ({opts.high_pass}) must be lower than '--upper-bpf' ({opts.low_pass})."
        )
    elif not opts.bandpass_filter:
        build_log.warning('Bandpass filtering is disabled. ALFF outputs will not be generated.')

    # Scrubbing parameters
    if opts.fd_thresh <= 0 and opts.min_time > 0:
        ignored_params = '\n\t'.join(['--min-time'])
        build_log.warning(
            'Framewise displacement-based scrubbing is disabled. '
            f'The following parameters will have no effect:\n\t{ignored_params}'
        )
        opts.min_time = 0

    opts.output_interpolated = True if opts.output_type == 'interpolated' else False

    # Motion filtering parameters
    if opts.motion_filter_type == 'none':
        opts.motion_filter_type = None

    if opts.motion_filter_type == 'notch':
        if not (opts.band_stop_min and opts.band_stop_max):
            error_messages.append(
                "Please set both '--band-stop-min' and '--band-stop-max' if you want to apply "
                "the 'notch' motion filter."
            )
        elif opts.band_stop_min >= opts.band_stop_max:
            error_messages.append(
                f"'--band-stop-min' ({opts.band_stop_min}) must be lower than "
                f"'--band-stop-max' ({opts.band_stop_max})."
            )
        elif opts.band_stop_min < 1 or opts.band_stop_max < 1:
            build_log.warning(
                f"Either '--band-stop-min' ({opts.band_stop_min}) or "
                f"'--band-stop-max' ({opts.band_stop_max}) is suspiciously low. "
                'Please remember that these values should be in breaths-per-minute.'
            )

    elif opts.motion_filter_type == 'lp':
        if not opts.band_stop_min:
            error_messages.append(
                "Please set '--band-stop-min' if you want to apply the 'lp' motion filter."
            )
        elif opts.band_stop_min < 1:
            build_log.warning(
                f"'--band-stop-min' ({opts.band_stop_max}) is suspiciously low. "
                'Please remember that this value should be in breaths-per-minute.'
            )

        if opts.band_stop_max:
            build_log.warning("'--band-stop-max' is ignored when '--motion-filter-type' is 'lp'.")

    elif opts.band_stop_min or opts.band_stop_max:
        build_log.warning(
            "'--band-stop-min' and '--band-stop-max' are ignored if '--motion-filter-type' "
            'is not set.'
        )

    # Parcellation parameters
    if not opts.atlases and opts.min_coverage != 0.5:
        build_log.warning(
            'When no atlases are selected or parcellation is explicitly skipped '
            "('--skip-parcellation'), '--min-coverage' will have no effect."
        )

    # Some parameters are automatically set depending on the input type.
    if opts.input_type == 'ukb':
        if opts.file_format == 'cifti':
            error_messages.append(
                "In order to process UK Biobank data, the file format must be set to 'nifti'."
            )

        if opts.process_surfaces:
            error_messages.append(
                '--warp-surfaces-native2std is not supported for UK Biobank data.'
            )

    for cifti_only_atlas in ['MIDB', 'MyersLabonte']:
        if (cifti_only_atlas in opts.atlases) and (opts.file_format == 'nifti'):
            build_log.warning(
                f"Atlas '{cifti_only_atlas}' requires CIFTI processing. Skipping atlas."
            )
            opts.atlases = [atlas for atlas in opts.atlases if atlas != cifti_only_atlas]

    # process_surfaces and nifti processing are incompatible.
    if opts.process_surfaces and (opts.file_format == 'nifti'):
        error_messages.append(
            'In order to perform surface normalization (--warp-surfaces-native2std), '
            'you must enable cifti processing (--file-format cifti).'
        )

    if error_messages:
        error_message_str = 'Errors detected in parameter parsing:\n\t- ' + '\n\t- '.join(
            error_messages
        )
        parser.error(error_message_str)

    return opts
