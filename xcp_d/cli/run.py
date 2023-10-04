#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The xcp_d preprocessing worklow."""
from xcp_d import config


def _main(args=None, namespace=None):
    from multiprocessing import set_start_method

    set_start_method("forkserver")

    main(args=args, namespace=namespace)


def main(args=None, namespace=None):
    """Run the main workflow."""
    from multiprocessing import Manager, Process

    from xcp_d.cli.parser import get_parser

    opts = get_parser().parse_args(args, namespace)
    config.execution.log_level = int(max(25 - 5 * opts.verbose_count, logging.DEBUG))
    config.from_dict(vars(opts))

    # Retrieve logging level
    build_log = config.loggers.cli

    # Load base plugin_settings from file if --use-plugin
    if opts.use_plugin is not None:
        import yaml

        with open(opts.use_plugin) as f:
            plugin_settings = yaml.load(f, Loader=yaml.FullLoader)
        _plugin = plugin_settings.get("plugin")
        if _plugin:
            config.nipype.plugin = _plugin
            config.nipype.plugin_args = plugin_settings.get("plugin_args", {})
            config.nipype.nprocs = opts.nprocs or config.nipype.plugin_args.get(
                "n_procs", config.nipype.nprocs
            )

    # Resource management options
    # Note that we're making strong assumptions about valid plugin args
    # This may need to be revisited if people try to use batch plugins
    if 1 < config.nipype.nprocs < config.nipype.omp_nthreads:
        build_log.warning(
            f"Per-process threads (--omp-nthreads={config.nipype.omp_nthreads}) exceed "
            f"total threads (--nthreads/--n_cpus={config.nipype.nprocs})"
        )

    fmri_dir = config.execution.fmri_dir
    output_dir = config.execution.output_dir
    work_dir = config.execution.work_dir
    version = config.environment.version

    # Wipe out existing work_dir
    if opts.clean_workdir and work_dir.exists():
        from niworkflows.utils.misc import clean_directory

        build_log.info(f"Clearing previous aslprep working directory: {work_dir}")
        if not clean_directory(work_dir):
            build_log.warning(f"Could not clear all contents of working directory: {work_dir}")

    # Ensure input and output folders are not the same
    if output_dir == bids_dir:
        rec_path = bids_dir / "derivatives" / f"aslprep-{version.split('+')[0]}"
        parser.error(
            "The selected output folder is the same as the input BIDS folder. "
            f"Please modify the output path (suggestion: {rec_path})."
        )

    if bids_dir in work_dir.parents:
        parser.error(
            "The selected working directory is a subdirectory of the input BIDS folder. "
            "Please modify the output path."
        )

    # Setup directories
    config.execution.log_dir = output_dir / "aslprep" / "logs"
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
            "One or more participant labels were not found in the BIDS directory: "
            f"{', '.join(missing_subjects)}."
        )

    config.execution.participant_label = sorted(participant_label)

    # OLD
    exec_env = os.name

    sentry_sdk = None
    if not opts.notrack:
        import sentry_sdk

        from xcp_d.utils.sentry import sentry_setup

        sentry_setup(opts, exec_env)

    # Call build_workflow(opts, retval)
    with Manager() as mgr:
        retval = mgr.dict()
        p = Process(target=build_workflow, args=(opts, retval))
        p.start()
        p.join()

        retcode = p.exitcode or retval.get("return_code", 0)

        work_dir = Path(retval.get("work_dir"))
        fmri_dir = Path(retval.get("fmri_dir"))
        output_dir = Path(retval.get("output_dir"))
        plugin_settings = retval.get("plugin_settings", None)
        subject_list = retval.get("subject_list", None)
        run_uuid = retval.get("run_uuid", None)
        xcpd_wf = retval.get("workflow", None)

    retcode = retcode or int(xcpd_wf is None)
    if retcode != 0:
        sys.exit(retcode)

    # Check workflow for missing commands
    missing = check_deps(xcpd_wf)
    if missing:
        print("Cannot run xcp_d. Missing dependencies:", file=sys.stderr)
        for iface, cmd in missing:
            print(f"\t{cmd} (Interface: {iface})")
        sys.exit(2)

    # Clean up master process before running workflow, which may create forks
    gc.collect()

    # Track start of workflow with sentry
    if not opts.notrack:
        from xcp_d.utils.sentry import start_ping

        start_ping(run_uuid, len(subject_list))

    errno = 1  # Default is error exit unless otherwise set
    try:
        xcpd_wf.run(**plugin_settings)

    except Exception as e:
        if not opts.notrack:
            from xcp_d.utils.sentry import process_crashfile

            crashfolders = [
                output_dir / "xcp_d" / f"sub-{s}" / "log" / run_uuid for s in subject_list
            ]
            for crashfolder in crashfolders:
                for crashfile in crashfolder.glob("crash*.*"):
                    process_crashfile(crashfile)

        if "Workflow did not execute cleanly" not in str(e):
            sentry_sdk.capture_exception(e)

        logger.critical("xcp_d failed: %s", e)
        raise

    else:
        errno = 0
        logger.log(25, "xcp_d finished without errors")
        if not opts.notrack:
            sentry_sdk.capture_message("xcp_d finished without errors", level="info")

    finally:
        from shutil import copyfile
        from subprocess import CalledProcessError, TimeoutExpired, check_call

        from pkg_resources import resource_filename as pkgrf

        from xcp_d.interfaces.report_core import generate_reports

        citation_files = {
            ext: output_dir / "xcp_d" / "logs" / f"CITATION.{ext}"
            for ext in ("bib", "tex", "md", "html")
        }

        if citation_files["md"].exists():
            # Generate HTML file resolving citations
            cmd = [
                "pandoc",
                "-s",
                "--bibliography",
                pkgrf("xcp_d", "data/boilerplate.bib"),
                "--filter",
                "pandoc-citeproc",
                "--metadata",
                'pagetitle="xcp_d citation boilerplate"',
                str(citation_files["md"]),
                "-o",
                str(citation_files["html"]),
            ]
            logger.info("Generating an HTML version of the citation boilerplate...")
            try:
                check_call(cmd, timeout=10)
            except (FileNotFoundError, CalledProcessError, TimeoutExpired):
                logger.warning(f"Could not generate CITATION.html file:\n{' '.join(cmd)}")

            # Generate LaTex file resolving citations
            cmd = [
                "pandoc",
                "-s",
                "--bibliography",
                pkgrf("xcp_d", "data/boilerplate.bib"),
                "--natbib",
                str(citation_files["md"]),
                "-o",
                str(citation_files["tex"]),
            ]
            logger.info("Generating a LaTeX version of the citation boilerplate...")
            try:
                check_call(cmd, timeout=10)
            except (FileNotFoundError, CalledProcessError, TimeoutExpired):
                logger.warning(f"Could not generate CITATION.tex file:\n{' '.join(cmd)}")
            else:
                copyfile(pkgrf("xcp_d", "data/boilerplate.bib"), citation_files["bib"])

        else:
            logger.warning(
                "xcp_d could not find the markdown version of "
                f"the citation boilerplate ({citation_files['md']}). "
                "HTML and LaTeX versions of it will not be available"
            )

        # Generate reports phase
        failed_reports = generate_reports(
            subject_list=subject_list,
            fmri_dir=fmri_dir,
            work_dir=work_dir,
            output_dir=output_dir,
            run_uuid=run_uuid,
            config=pkgrf("xcp_d", "data/reports.yml"),
            packagename="xcp_d",
        )

        if failed_reports and not opts.notrack:
            sentry_sdk.capture_message(
                f"Report generation failed for {failed_reports} subjects", level="error"
            )
        sys.exit(int((errno + failed_reports) > 0))


def _validate_parameters(opts, build_log):
    """Validate parameters.

    This function was abstracted out of build_workflow to make testing easier.
    """
    opts.fmri_dir = opts.fmri_dir.resolve()
    opts.output_dir = opts.output_dir.resolve()
    opts.work_dir = opts.work_dir.resolve()

    return_code = 0

    # Set the FreeSurfer license
    if opts.fs_license_file is not None:
        opts.fs_license_file = opts.fs_license_file.resolve()
        if opts.fs_license_file.is_file():
            os.environ["FS_LICENSE"] = str(opts.fs_license_file)

        else:
            build_log.error(f"Freesurfer license DNE: {opts.fs_license_file}.")
            return_code = 1

    # Check the validity of inputs
    if opts.output_dir == opts.fmri_dir:
        rec_path = (
            opts.fmri_dir / "derivatives" / f"xcp_d-{config.environment.version.split('+')[0]}"
        )
        build_log.error(
            "The selected output folder is the same as the input fmri input. "
            "Please modify the output path "
            f"(suggestion: {rec_path})."
        )
        return_code = 1

    if opts.analysis_level != "participant":
        build_log.error('Please select analysis level "participant"')
        return_code = 1

    # Bandpass filter parameters
    if opts.lower_bpf <= 0 and opts.upper_bpf <= 0:
        opts.bandpass_filter = False

    if (
        opts.bandpass_filter
        and (opts.lower_bpf >= opts.upper_bpf)
        and (opts.lower_bpf > 0 and opts.upper_bpf > 0)
    ):
        build_log.error(
            f"'--lower-bpf' ({opts.lower_bpf}) must be lower than "
            f"'--upper-bpf' ({opts.upper_bpf})."
        )
        return_code = 1
    elif not opts.bandpass_filter:
        build_log.warning("Bandpass filtering is disabled. ALFF outputs will not be generated.")

    # Scrubbing parameters
    if opts.fd_thresh <= 0:
        ignored_params = "\n\t".join(
            [
                "--min-time",
                "--motion-filter-type",
                "--band-stop-min",
                "--band-stop-max",
                "--motion-filter-order",
                "--head_radius",
            ]
        )
        build_log.warning(
            "Framewise displacement-based scrubbing is disabled. "
            f"The following parameters will have no effect:\n\t{ignored_params}"
        )
        opts.min_time = 0
        opts.motion_filter_type = None
        opts.band_stop_min = None
        opts.band_stop_max = None
        opts.motion_filter_order = None

    # Motion filtering parameters
    if opts.motion_filter_type == "notch":
        if not (opts.band_stop_min and opts.band_stop_max):
            build_log.error(
                "Please set both '--band-stop-min' and '--band-stop-max' if you want to apply "
                "the 'notch' motion filter."
            )
            return_code = 1
        elif opts.band_stop_min >= opts.band_stop_max:
            build_log.error(
                f"'--band-stop-min' ({opts.band_stop_min}) must be lower than "
                f"'--band-stop-max' ({opts.band_stop_max})."
            )
            return_code = 1
        elif opts.band_stop_min < 1 or opts.band_stop_max < 1:
            build_log.warning(
                f"Either '--band-stop-min' ({opts.band_stop_min}) or "
                f"'--band-stop-max' ({opts.band_stop_max}) is suspiciously low. "
                "Please remember that these values should be in breaths-per-minute."
            )

    elif opts.motion_filter_type == "lp":
        if not opts.band_stop_min:
            build_log.error(
                "Please set '--band-stop-min' if you want to apply the 'lp' motion filter."
            )
            return_code = 1
        elif opts.band_stop_min < 1:
            build_log.warning(
                f"'--band-stop-min' ({opts.band_stop_max}) is suspiciously low. "
                "Please remember that this value should be in breaths-per-minute."
            )

        if opts.band_stop_max:
            build_log.warning("'--band-stop-max' is ignored when '--motion-filter-type' is 'lp'.")

    elif opts.band_stop_min or opts.band_stop_max:
        build_log.warning(
            "'--band-stop-min' and '--band-stop-max' are ignored if '--motion-filter-type' "
            "is not set."
        )

    # Some parameters are automatically set depending on the input type.
    if opts.input_type in ("dcan", "hcp"):
        if not opts.cifti:
            build_log.warning(
                f"With input_type {opts.input_type}, cifti processing (--cifti) will be "
                "enabled automatically."
            )
            opts.cifti = True

        if not opts.process_surfaces:
            build_log.warning(
                f"With input_type {opts.input_type}, surface normalization "
                "(--warp-surfaces-native2std) will be enabled automatically."
            )
            opts.process_surfaces = True

    # process_surfaces and nifti processing are incompatible.
    if opts.process_surfaces and not opts.cifti:
        build_log.error(
            "In order to perform surface normalization (--warp-surfaces-native2std), "
            "you must enable cifti processing (--cifti)."
        )
        return_code = 1

    return opts, return_code


def build_workflow(opts, retval):
    """Create the Nipype workflow that supports the whole execution graph, given the inputs.

    All the checks and the construction of the workflow are done
    inside this function that has pickleable inputs and output
    dictionary (``retval``) to allow isolation using a
    ``multiprocessing.Process`` that allows fmriprep to enforce
    a hard-limited memory-scope.
    """
    from bids import BIDSLayout
    from nipype import config as ncfg
    from nipype import logging as nlogging

    from xcp_d.utils.bids import collect_participants
    from xcp_d.workflows.base import init_xcpd_wf

    log_level = int(max(25 - 5 * opts.verbose_count, logging.DEBUG))

    build_log = nlogging.getLogger("nipype.workflow")
    build_log.setLevel(log_level)
    nlogging.getLogger("nipype.interface").setLevel(log_level)
    nlogging.getLogger("nipype.utils").setLevel(log_level)

    opts, retval["return_code"] = _validate_parameters(opts, build_log)

    if retval["return_code"] == 1:
        return retval

    if opts.clean_workdir:
        from niworkflows.utils.misc import clean_directory

        build_log.info(f"Clearing previous xcp_d working directory: {opts.work_dir}")
        if not clean_directory(opts.work_dir):
            build_log.warning(
                f"Could not clear all contents of working directory: {opts.work_dir}"
            )

    retval["return_code"] = 1
    retval["workflow"] = None
    retval["fmri_dir"] = str(opts.fmri_dir)
    retval["output_dir"] = str(opts.output_dir)
    retval["work_dir"] = str(opts.work_dir)

    # First check that fmriprep_dir looks like a BIDS folder
    if opts.input_type in ("dcan", "hcp"):
        if opts.input_type == "dcan":
            from xcp_d.utils.dcan2fmriprep import convert_dcan2bids as convert_to_bids
        elif opts.input_type == "hcp":
            from xcp_d.utils.hcp2fmriprep import convert_hcp2bids as convert_to_bids

        NIWORKFLOWS_LOG.info(f"Converting {opts.input_type} to fmriprep format")
        converted_fmri_dir = os.path.join(
            opts.work_dir,
            f"dset_bids/derivatives/{opts.input_type}",
        )
        os.makedirs(converted_fmri_dir, exist_ok=True)

        convert_to_bids(
            opts.fmri_dir,
            out_dir=converted_fmri_dir,
            participant_ids=opts.participant_label,
        )

        opts.fmri_dir = Path(converted_fmri_dir)

    if not os.path.isfile((os.path.join(opts.fmri_dir, "dataset_description.json"))):
        build_log.error(
            "No dataset_description.json file found in input directory. "
            "Make sure to point to the specific pipeline's derivatives folder. "
            "For example, use '/dset/derivatives/fmriprep', not /dset/derivatives'."
        )
        retval["return_code"] = 1

    # Set up some instrumental utilities
    run_uuid = f"{strftime('%Y%m%d-%H%M%S')}_{uuid.uuid4()}"
    retval["run_uuid"] = run_uuid

    layout = BIDSLayout(str(opts.fmri_dir), validate=False, derivatives=True)
    subject_list = collect_participants(layout, participant_label=opts.participant_label)
    retval["subject_list"] = subject_list

    # Load base plugin_settings from file if --use-plugin
    if opts.use_plugin is not None:
        from yaml import load as loadyml

        with open(opts.use_plugin) as f:
            plugin_settings = loadyml(f)

        plugin_settings.setdefault("plugin_args", {})

    else:
        # Defaults
        plugin_settings = {
            "plugin": "MultiProc",
            "plugin_args": {
                "raise_insufficient": False,
                "maxtasksperchild": 1,
            },
        }

    # Permit overriding plugin config with specific CLI options
    nthreads = opts.nthreads
    omp_nthreads = opts.omp_nthreads

    if (nthreads == 1) or (omp_nthreads > nthreads):
        omp_nthreads = 1

    plugin_settings["plugin_args"]["n_procs"] = nthreads

    if 1 < nthreads < omp_nthreads:
        build_log.warning(
            f"Per-process threads (--omp-nthreads={omp_nthreads}) exceed total "
            f"threads (--nthreads/--n_cpus={nthreads})"
        )

    if opts.mem_gb:
        plugin_settings["plugin_args"]["memory_gb"] = opts.mem_gb

    retval["plugin_settings"] = plugin_settings

    # Set up directories
    log_dir = opts.output_dir / "xcp_d" / "logs"

    # Check and create output and working directories
    opts.output_dir.mkdir(exist_ok=True, parents=True)
    opts.work_dir.mkdir(exist_ok=True, parents=True)
    log_dir.mkdir(exist_ok=True, parents=True)

    # Nipype config (logs and execution)
    ncfg.update_config(
        {
            "logging": {
                "log_directory": str(log_dir),
                "log_to_file": True,
                "workflow_level": log_level,
                "interface_level": log_level,
                "utils_level": log_level,
            },
            "execution": {
                "crashdump_dir": str(log_dir),
                "crashfile_format": "txt",
                "get_linked_libs": False,
            },
            "monitoring": {
                "enabled": opts.resource_monitor,
                "sample_frequency": "0.5",
                "summary_append": True,
            },
        }
    )

    if opts.resource_monitor:
        ncfg.enable_resource_monitor()

    # Build main workflow
    build_log.log(
        25,
        f"""\
Running xcp_d version {config.environment.version}:
    * fMRI directory path: {opts.fmri_dir}.
    * Participant list: {subject_list}.
    * Run identifier: {run_uuid}.

""",
    )

    retval["workflow"] = init_xcpd_wf(
        subject_list=subject_list,
        name="xcpd_wf",
    )

    boilerplate = retval["workflow"].visit_desc()

    if boilerplate:
        citation_files = {ext: log_dir / f"CITATION.{ext}" for ext in ("bib", "tex", "md", "html")}
        # To please git-annex users and also to guarantee consistency among different renderings
        # of the same file, first remove any existing ones
        for citation_file in citation_files.values():
            try:
                citation_file.unlink()
            except FileNotFoundError:
                pass

        citation_files["md"].write_text(boilerplate)

    build_log.log(
        25,
        (
            "Works derived from this xcp_d execution should include the following boilerplate:\n\n"
            f"{boilerplate}"
        ),
    )

    retval["return_code"] = 0

    return retval


if __name__ == "__main__":
    raise RuntimeError(
        "xcp_d/cli/run.py should not be run directly;\n"
        "Please use the `xcp_d` command-line interface."
    )
