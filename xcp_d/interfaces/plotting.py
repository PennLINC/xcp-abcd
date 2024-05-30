# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Plotting interfaces."""
import json
import os

import matplotlib.pyplot as plt
import nibabel as nb
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec
from nilearn.plotting import plot_anat, plot_surf_stat_map
from nipype import logging
from nipype.interfaces.base import (
    BaseInterfaceInputSpec,
    Directory,
    File,
    InputMultiPath,
    OutputMultiPath,
    SimpleInterface,
    TraitedSpec,
    Undefined,
    isdefined,
    traits,
)
from nipype.interfaces.fsl.base import FSLCommand, FSLCommandInputSpec
from templateflow.api import get as get_template

from xcp_d.utils.confounds import load_motion
from xcp_d.utils.filemanip import fname_presuffix
from xcp_d.utils.modified_data import compute_fd
from xcp_d.utils.plotting import FMRIPlot, plot_fmri_es, surf_data_from_cifti
from xcp_d.utils.qcmetrics import compute_dvars, compute_registration_qc
from xcp_d.utils.write_save import read_ndata

LOGGER = logging.getLogger("nipype.interface")


class _CensoringPlotInputSpec(BaseInterfaceInputSpec):
    fmriprep_confounds_file = File(exists=True, mandatory=True, desc="fMRIPrep confounds file.")
    filtered_motion = File(exists=True, mandatory=True, desc="Filtered motion file.")
    temporal_mask = File(
        exists=True,
        mandatory=True,
        desc="Temporal mask after dummy scan removal.",
    )
    dummy_scans = traits.Int(mandatory=True, desc="Dummy time to drop")
    TR = traits.Float(mandatory=True, desc="Repetition Time")
    head_radius = traits.Float(mandatory=True, desc="Head radius for FD calculation")
    motion_filter_type = traits.Either(None, traits.Str, mandatory=True)
    fd_thresh = traits.Float(mandatory=True, desc="Framewise displacement threshold.")


class _CensoringPlotOutputSpec(TraitedSpec):
    out_file = File(exists=True, mandatory=True, desc="Censoring plot.")


class CensoringPlot(SimpleInterface):
    """Generate a censoring figure.

    This is a line plot showing both the raw and filtered framewise displacement time series,
    with vertical lines/bands indicating volumes removed by the post-processing workflow.

    """

    input_spec = _CensoringPlotInputSpec
    output_spec = _CensoringPlotOutputSpec

    def _run_interface(self, runtime):
        # Load confound matrix and load motion with motion filtering
        confounds_df = pd.read_table(self.inputs.fmriprep_confounds_file)
        preproc_motion_df = load_motion(
            confounds_df.copy(),
            TR=self.inputs.TR,
            motion_filter_type=None,
        )
        preproc_fd_timeseries = compute_fd(
            confound=preproc_motion_df,
            head_radius=self.inputs.head_radius,
        )

        # Load temporal mask
        censoring_df = pd.read_table(self.inputs.temporal_mask)

        # The number of colors in the palette depends on whether there are random censors or not
        palette = sns.color_palette("colorblind", 4 + censoring_df.shape[1])

        time_array = np.arange(preproc_fd_timeseries.size) * self.inputs.TR

        with sns.axes_style("whitegrid"):
            fig, ax = plt.subplots(figsize=(8, 4))

            ax.plot(
                time_array,
                preproc_fd_timeseries,
                label="Raw Framewise Displacement",
                color=palette[0],
            )
            ax.axhline(self.inputs.fd_thresh, label="Outlier Threshold", color="salmon", alpha=0.5)

        dummy_scans = self.inputs.dummy_scans
        # This check is necessary, because init_prepare_confounds_wf connects dummy_scans from the
        # inputnode, forcing it to be undefined instead of using the default when not set.
        if not isdefined(dummy_scans):
            dummy_scans = 0

        if dummy_scans:
            ax.axvspan(
                0,
                dummy_scans * self.inputs.TR,
                label="Dummy Volumes",
                alpha=0.5,
                color=palette[1],
            )
            # Prepend dummy scans to the temporal mask
            dummy_df = pd.DataFrame(0, index=np.arange(dummy_scans), columns=censoring_df.columns)
            censoring_df = pd.concat([dummy_df, censoring_df])

        # Compute filtered framewise displacement to plot censoring
        if self.inputs.motion_filter_type:
            filtered_fd_timeseries = pd.read_table(self.inputs.filtered_motion)[
                "framewise_displacement"
            ]

            ax.plot(
                time_array,
                filtered_fd_timeseries.values,
                label="Filtered Framewise Displacement",
                color=palette[2],
            )
        else:
            filtered_fd_timeseries = preproc_fd_timeseries.copy()

        # Set axis limits
        ax.set_xlim(0, max(time_array))
        y_max = (
            np.max(
                np.hstack(
                    (
                        preproc_fd_timeseries,
                        filtered_fd_timeseries,
                        [self.inputs.fd_thresh],
                    )
                )
            )
            * 1.5
        )
        ax.set_ylim(0, y_max)

        # Plot randomly censored volumes as well
        # These vertical lines start at the top and only go 20% of the way down the plot.
        # They are plotted in non-overlapping segments.
        exact_columns = [col for col in censoring_df.columns if col.startswith("exact_")]
        vline_ymax = 1
        for i_col, exact_col in enumerate(exact_columns):
            tmask_arr = censoring_df[exact_col].values
            tmask_idx = np.where(tmask_arr)[0]
            vline_yspan = 0.2 / len(exact_columns)
            vline_ymin = vline_ymax - vline_yspan

            for j_idx, idx in enumerate(tmask_idx):
                label = f"Randomly Censored Volumes {exact_col}" if j_idx == 0 else ""
                ax.axvline(
                    idx * self.inputs.TR,
                    ymin=vline_ymin,
                    ymax=vline_ymax,
                    label=label,
                    color=palette[4 + i_col],
                    alpha=0.8,
                )

            vline_ymax = vline_ymin

        # Plot motion-censored volumes as vertical lines
        tmask_arr = censoring_df["framewise_displacement"].values
        assert preproc_fd_timeseries.size == tmask_arr.size
        tmask_idx = np.where(tmask_arr)[0]
        for i_idx, idx in enumerate(tmask_idx):
            label = "Motion-Censored Volumes" if i_idx == 0 else ""
            ax.axvline(
                idx * self.inputs.TR,
                label=label,
                color=palette[3],
                alpha=0.5,
            )

        ax.set_xlabel("Time (seconds)", fontsize=10)
        ax.set_ylabel("Movement (millimeters)", fontsize=10)
        ax.legend(fontsize=10)
        fig.tight_layout()

        self._results["out_file"] = fname_presuffix(
            "censoring",
            suffix="_motion.svg",
            newpath=runtime.cwd,
            use_ext=False,
        )

        fig.savefig(self._results["out_file"])
        plt.close(fig)
        return runtime


class _QCPlotsInputSpec(BaseInterfaceInputSpec):
    name_source = File(
        exists=False,
        mandatory=True,
        desc=(
            "Preprocessed BOLD file. Used to find files. "
            "In the case of the concatenation workflow, "
            "this may be a nonexistent file "
            "(i.e., the preprocessed BOLD file, with the run entity removed)."
        ),
    )
    bold_file = File(
        exists=True,
        mandatory=True,
        desc="Preprocessed BOLD file, after dummy scan removal. Used in carpet plot.",
    )
    dummy_scans = traits.Int(mandatory=True, desc="Dummy time to drop")
    temporal_mask = traits.Either(
        File(exists=True),
        Undefined,
        desc="Temporal mask",
    )
    fmriprep_confounds_file = File(
        exists=True,
        mandatory=True,
        desc="fMRIPrep confounds file, after dummy scans removal",
    )
    cleaned_file = File(
        exists=True,
        mandatory=True,
        desc="Processed file, after denoising and censoring.",
    )
    TR = traits.Float(mandatory=True, desc="Repetition Time")
    head_radius = traits.Float(mandatory=True, desc="Head radius for FD calculation")
    mask_file = traits.Either(
        None,
        File(exists=True),
        mandatory=True,
        desc="Mask file from nifti. May be None, for CIFTI processing.",
    )

    # Inputs used only for nifti data
    seg_file = File(exists=True, mandatory=False, desc="Seg file for nifti")
    anat_brainmask = File(exists=True, mandatory=False, desc="Mask in T1W")
    template_mask = File(exists=True, mandatory=False, desc="Template mask")
    bold2T1w_mask = File(exists=True, mandatory=False, desc="Bold mask in MNI")
    bold2temp_mask = File(exists=True, mandatory=False, desc="Bold mask in T1W")


class _QCPlotsOutputSpec(TraitedSpec):
    qc_file = File(exists=True, desc="QC TSV file.")
    qc_metadata = File(exists=True, desc="Sidecar JSON for QC TSV file.")
    raw_qcplot = File(exists=True, desc="qc plot before regression")
    clean_qcplot = File(exists=True, desc="qc plot after regression")


class QCPlots(SimpleInterface):
    """Generate pre- and post-processing quality control (QC) figures.

    Examples
    --------
    .. testsetup::
    >>> from tempfile import TemporaryDirectory
    >>> tmpdir = TemporaryDirectory()
    >>> os.chdir(tmpdir.name)
    .. doctest::
    qcplots = QCPlots()
    qcplots.inputs.cleaned_file = datafile
    qcplots.inputs.name_source = rawbold
    qcplots.inputs.bold_file = rawbold
    qcplots.inputs.TR = TR
    qcplots.inputs.temporal_mask = temporalmask
    qcplots.inputs.mask_file = mask
    qcplots.inputs.dummy_scans = dummy_scans
    qcplots.run()
    .. testcleanup::
    >>> tmpdir.cleanup()
    """

    input_spec = _QCPlotsInputSpec
    output_spec = _QCPlotsOutputSpec

    def _run_interface(self, runtime):
        # Load confound matrix and load motion without motion filtering
        confounds_df = pd.read_table(self.inputs.fmriprep_confounds_file)
        preproc_motion_df = load_motion(
            confounds_df.copy(),
            TR=self.inputs.TR,
            motion_filter_type=None,
        )
        preproc_fd_timeseries = compute_fd(
            confound=preproc_motion_df,
            head_radius=self.inputs.head_radius,
        )

        # Get rmsd
        rmsd = confounds_df["rmsd"].to_numpy()

        # Determine number of dummy volumes and load temporal mask
        dummy_scans = self.inputs.dummy_scans
        if isdefined(self.inputs.temporal_mask):
            censoring_df = pd.read_table(self.inputs.temporal_mask)
            tmask_arr = censoring_df["framewise_displacement"].values
        else:
            tmask_arr = np.zeros(preproc_fd_timeseries.size, dtype=int)

        num_censored_volumes = int(tmask_arr.sum())
        num_retained_volumes = int((tmask_arr == 0).sum())

        # Apply temporal mask to interpolated/full data
        rmsd_censored = rmsd[tmask_arr == 0]
        postproc_fd_timeseries = preproc_fd_timeseries[tmask_arr == 0]

        # get QC plot names
        self._results["raw_qcplot"] = fname_presuffix(
            "preprocess",
            suffix="_raw_qcplot.svg",
            newpath=runtime.cwd,
            use_ext=False,
        )
        self._results["clean_qcplot"] = fname_presuffix(
            "postprocess",
            suffix="_clean_qcplot.svg",
            newpath=runtime.cwd,
            use_ext=False,
        )

        dvars_before_processing = compute_dvars(
            datat=read_ndata(
                datafile=self.inputs.bold_file,
                maskfile=self.inputs.mask_file,
            ),
        )[1]
        dvars_after_processing = compute_dvars(
            datat=read_ndata(
                datafile=self.inputs.cleaned_file,
                maskfile=self.inputs.mask_file,
            ),
        )[1]
        if preproc_fd_timeseries.size != dvars_before_processing.size:
            raise ValueError(
                f"FD {preproc_fd_timeseries.size} != DVARS {dvars_before_processing.size}\n"
            )
        preproc_confounds = pd.DataFrame(
            {
                "FD": preproc_fd_timeseries,
                "DVARS": dvars_before_processing,
            }
        )

        preproc_fig = FMRIPlot(
            func_file=self.inputs.bold_file,
            seg_file=self.inputs.seg_file,
            data=preproc_confounds,
            mask_file=self.inputs.mask_file,
        ).plot(labelsize=8)

        preproc_fig.savefig(
            self._results["raw_qcplot"],
            bbox_inches="tight",
        )
        plt.close(preproc_fig)

        postproc_confounds = pd.DataFrame(
            {
                "FD": postproc_fd_timeseries,
                "DVARS": dvars_after_processing,
            }
        )

        postproc_fig = FMRIPlot(
            func_file=self.inputs.cleaned_file,
            seg_file=self.inputs.seg_file,
            data=postproc_confounds,
            mask_file=self.inputs.mask_file,
        ).plot(labelsize=8)

        postproc_fig.savefig(
            self._results["clean_qcplot"],
            bbox_inches="tight",
        )
        plt.close(postproc_fig)

        # Get the different components in the bold file name
        # eg: ['sub-colornest001', 'ses-1'], etc.
        _, bold_file_name = os.path.split(self.inputs.name_source)
        bold_file_name_components = bold_file_name.split("_")

        # Fill out dictionary with entities from filename
        qc_values_dict = {}
        for entity in bold_file_name_components[:-1]:
            qc_values_dict[entity.split("-")[0]] = entity.split("-")[1]

        # Calculate QC measures
        mean_fd = np.mean(preproc_fd_timeseries)
        mean_fd_post_censoring = np.mean(postproc_fd_timeseries)
        mean_relative_rms = np.nanmean(rmsd_censored)  # first value can be NaN if no dummy scans
        mean_dvars_before_processing = np.mean(dvars_before_processing)
        mean_dvars_after_processing = np.mean(dvars_after_processing)
        fd_dvars_correlation_initial = np.corrcoef(preproc_fd_timeseries, dvars_before_processing)[
            0, 1
        ]
        fd_dvars_correlation_final = np.corrcoef(postproc_fd_timeseries, dvars_after_processing)[
            0, 1
        ]
        rmsd_max_value = np.nanmax(rmsd_censored)

        # A summary of all the values
        qc_values_dict.update(
            {
                "mean_fd": [mean_fd],
                "mean_fd_post_censoring": [mean_fd_post_censoring],
                "mean_relative_rms": [mean_relative_rms],
                "max_relative_rms": [rmsd_max_value],
                "mean_dvars_initial": [mean_dvars_before_processing],
                "mean_dvars_final": [mean_dvars_after_processing],
                "num_dummy_volumes": [dummy_scans],
                "num_censored_volumes": [num_censored_volumes],
                "num_retained_volumes": [num_retained_volumes],
                "fd_dvars_correlation_initial": [fd_dvars_correlation_initial],
                "fd_dvars_correlation_final": [fd_dvars_correlation_final],
            }
        )

        qc_metadata = {
            "mean_fd": {
                "LongName": "Mean Framewise Displacement",
                "Description": (
                    "Average framewise displacement without any motion parameter filtering. "
                    "This value includes high-motion outliers, but not dummy volumes. "
                    "FD is calculated according to the Power definition."
                ),
                "Units": "mm / volume",
                "Term URL": "https://doi.org/10.1016/j.neuroimage.2011.10.018",
            },
            "mean_fd_post_censoring": {
                "LongName": "Mean Framewise Displacement After Censoring",
                "Description": (
                    "Average framewise displacement without any motion parameter filtering. "
                    "This value does not include high-motion outliers or dummy volumes. "
                    "FD is calculated according to the Power definition."
                ),
                "Units": "mm / volume",
                "Term URL": "https://doi.org/10.1016/j.neuroimage.2011.10.018",
            },
            "mean_relative_rms": {
                "LongName": "Mean Relative Root Mean Squared",
                "Description": (
                    "Average relative root mean squared calculated from motion parameters, "
                    "after removal of dummy volumes and high-motion outliers. "
                    "Relative in this case means 'relative to the previous scan'."
                ),
                "Units": "arbitrary",
            },
            "max_relative_rms": {
                "LongName": "Maximum Relative Root Mean Squared",
                "Description": (
                    "Maximum relative root mean squared calculated from motion parameters, "
                    "after removal of dummy volumes and high-motion outliers. "
                    "Relative in this case means 'relative to the previous scan'."
                ),
                "Units": "arbitrary",
            },
            "mean_dvars_initial": {
                "LongName": "Mean DVARS Before Postprocessing",
                "Description": (
                    "Average DVARS (temporal derivative of root mean squared variance over "
                    "voxels) calculated from the preprocessed BOLD file, after dummy scan removal."
                ),
                "TermURL": "https://doi.org/10.1016/j.neuroimage.2011.02.073",
            },
            "mean_dvars_final": {
                "LongName": "Mean DVARS After Postprocessing",
                "Description": (
                    "Average DVARS (temporal derivative of root mean squared variance over "
                    "voxels) calculated from the denoised BOLD file."
                ),
                "TermURL": "https://doi.org/10.1016/j.neuroimage.2011.02.073",
            },
            "num_dummy_volumes": {
                "LongName": "Number of Dummy Volumes",
                "Description": (
                    "The number of non-steady state volumes removed from the time series by XCP-D."
                ),
            },
            "num_censored_volumes": {
                "LongName": "Number of Censored Volumes",
                "Description": (
                    "The number of high-motion outlier volumes censored by XCP-D. "
                    "This does not include dummy volumes."
                ),
            },
            "num_retained_volumes": {
                "LongName": "Number of Retained Volumes",
                "Description": (
                    "The number of volumes retained in the denoised dataset. "
                    "This does not include dummy volumes or high-motion outliers."
                ),
            },
            "fd_dvars_correlation_initial": {
                "LongName": "FD-DVARS Correlation Before Postprocessing",
                "Description": (
                    "The Pearson correlation coefficient between framewise displacement and DVARS "
                    "(temporal derivative of root mean squared variance over voxels), "
                    "after removal of dummy volumes, but before removal of high-motion outliers."
                ),
            },
            "fd_dvars_correlation_final": {
                "LongName": "FD-DVARS Correlation After Postprocessing",
                "Description": (
                    "The Pearson correlation coefficient between framewise displacement and DVARS "
                    "(temporal derivative of root mean squared variance over voxels), "
                    "after postprocessing. "
                    "The FD time series is unfiltered, but censored. "
                    "The DVARS time series is calculated from the denoised BOLD data."
                ),
            },
        }

        if self.inputs.bold2T1w_mask:  # If a bold mask in T1w is provided
            # Compute quality of registration
            registration_qc, registration_metadata = compute_registration_qc(
                bold2t1w_mask=self.inputs.bold2T1w_mask,
                anat_brainmask=self.inputs.anat_brainmask,
                bold2template_mask=self.inputs.bold2temp_mask,
                template_mask=self.inputs.template_mask,
            )
            qc_values_dict.update(registration_qc)  # Add values to dictionary
            qc_metadata.update(registration_metadata)

        # Convert dictionary to df and write out the qc file
        df = pd.DataFrame(qc_values_dict)
        self._results["qc_file"] = fname_presuffix(
            self.inputs.cleaned_file,
            suffix="qc_bold.tsv",
            newpath=runtime.cwd,
            use_ext=False,
        )
        df.to_csv(self._results["qc_file"], index=False, header=True, sep="\t")

        # Write out the metadata file
        self._results["qc_metadata"] = fname_presuffix(
            self.inputs.cleaned_file,
            suffix="qc_bold.json",
            newpath=runtime.cwd,
            use_ext=False,
        )
        with open(self._results["qc_metadata"], "w") as fo:
            json.dump(qc_metadata, fo, indent=4, sort_keys=True)

        return runtime


class _QCPlotsESInputSpec(BaseInterfaceInputSpec):
    preprocessed_bold = File(
        exists=True,
        mandatory=True,
        desc=(
            "Preprocessed BOLD file, after mean-centering and detrending "
            "*using only the low-motion volumes*."
        ),
    )
    denoised_interpolated_bold = File(
        exists=True,
        mandatory=True,
        desc="Data after filtering, interpolation, etc. This is not plotted.",
    )
    filtered_motion = File(
        exists=True,
        mandatory=True,
        desc="TSV file with filtered motion parameters.",
    )
    temporal_mask = traits.Either(
        File(exists=True),
        Undefined,
        desc="TSV file with temporal mask.",
    )
    TR = traits.Float(default_value=1, desc="Repetition time")
    standardize = traits.Bool(
        mandatory=True,
        desc=(
            "Whether to standardize the data or not. "
            "If False, then the preferred DCAN version of the plot will be generated, "
            "where the BOLD data are not rescaled, and the carpet plot has color limits from "
            "the 2.5th percentile to the 97.5th percentile. "
            "If True, then the BOLD data will be z-scored and the color limits will be -2 and 2."
        ),
    )

    # Optional inputs
    mask = File(exists=True, mandatory=False, desc="Bold mask")
    seg_data = File(exists=True, mandatory=False, desc="Segmentation file")
    run_index = traits.Either(
        traits.List(traits.Int()),
        Undefined,
        mandatory=False,
        desc=(
            "An index indicating splits between runs, for concatenated data. "
            "If not Undefined, this should be a list of integers, indicating the volumes."
        ),
    )


class _QCPlotsESOutputSpec(TraitedSpec):
    before_process = File(exists=True, mandatory=True, desc=".SVG file before processing")
    after_process = File(exists=True, mandatory=True, desc=".SVG file after processing")


class QCPlotsES(SimpleInterface):
    """Plot fd, dvars, and carpet plots of the bold data before and after regression/filtering.

    This is essentially equivalent to the QCPlots
    (which are paired pre- and post-processing FMRIPlots), but adapted for the executive summary.

    It takes in the data that's regressed, the data that's filtered and regressed,
    as well as the segmentation files, TR, FD, bold_mask and unprocessed data.

    It outputs the .SVG files before after processing has taken place.
    """

    input_spec = _QCPlotsESInputSpec
    output_spec = _QCPlotsESOutputSpec

    def _run_interface(self, runtime):
        preprocessed_figure = fname_presuffix(
            "carpetplot_before_",
            suffix="file.svg",
            newpath=runtime.cwd,
            use_ext=False,
        )

        denoised_figure = fname_presuffix(
            "carpetplot_after_",
            suffix="file.svg",
            newpath=runtime.cwd,
            use_ext=False,
        )

        mask_file = self.inputs.mask
        mask_file = mask_file if isdefined(mask_file) else None

        segmentation_file = self.inputs.seg_data
        segmentation_file = segmentation_file if isdefined(segmentation_file) else None

        run_index = self.inputs.run_index
        run_index = np.array(run_index) if isdefined(run_index) else None

        self._results["before_process"], self._results["after_process"] = plot_fmri_es(
            preprocessed_bold=self.inputs.preprocessed_bold,
            denoised_interpolated_bold=self.inputs.denoised_interpolated_bold,
            TR=self.inputs.TR,
            filtered_motion=self.inputs.filtered_motion,
            temporal_mask=self.inputs.temporal_mask,
            preprocessed_figure=preprocessed_figure,
            denoised_figure=denoised_figure,
            standardize=self.inputs.standardize,
            temporary_file_dir=runtime.cwd,
            mask=mask_file,
            seg_data=segmentation_file,
            run_index=run_index,
        )

        return runtime


class _AnatomicalPlotInputSpec(BaseInterfaceInputSpec):
    in_file = File(exists=True, mandatory=True, desc="plot image")


class _AnatomicalPlotOutputSpec(TraitedSpec):
    out_file = File(exists=True, desc="out image")


class AnatomicalPlot(SimpleInterface):
    """Python class to plot x,y, and z of image data."""

    input_spec = _AnatomicalPlotInputSpec
    output_spec = _AnatomicalPlotOutputSpec

    def _run_interface(self, runtime):
        self._results["out_file"] = fname_presuffix(
            self.inputs.in_file, suffix="_file.svg", newpath=runtime.cwd, use_ext=False
        )
        img = nb.load(self.inputs.in_file)
        arr = img.get_fdata()

        fig = plt.figure(constrained_layout=False, figsize=(25, 10))
        plot_anat(
            img,
            draw_cross=False,
            figure=fig,
            vmin=np.min(arr),
            vmax=np.max(arr),
            cut_coords=[0, 0, 0],
            annotate=False,
        )
        fig.savefig(self._results["out_file"], bbox_inches="tight", pad_inches=None)
        plt.close(fig)

        return runtime


class _SlicesDirInputSpec(FSLCommandInputSpec):
    is_pairs = traits.Bool(
        argstr="-o",
        position=0,
        desc="filelist is pairs ( <underlying> <red-outline> ) of images",
    )
    outline_image = File(
        exists=True,
        argstr="-p %s",
        position=1,
        desc="use <image> as red-outline image on top of all images in <filelist>",
    )
    edge_threshold = traits.Float(
        argstr="-e %.03f",
        position=2,
        desc=(
            "use the specified threshold for edges (if >0 use this proportion of max-min, "
            "if <0, use the absolute value)"
        ),
    )
    output_odd_axials = traits.Bool(
        argstr="-S",
        position=3,
        desc="output every second axial slice rather than just 9 ortho slices",
    )

    in_files = InputMultiPath(
        File(exists=True),
        argstr="%s",
        mandatory=True,
        position=-1,
        desc="List of files to process.",
    )

    out_extension = traits.Enum(
        (".gif", ".png", ".svg"),
        default=".gif",
        usedefault=True,
        desc="Convenience parameter to let xcp_d select the extension.",
    )


class _SlicesDirOutputSpec(TraitedSpec):
    out_dir = Directory(exists=True, desc="Output directory.")
    out_files = OutputMultiPath(File(exists=True), desc="Concatenated PNG files.")
    slicewise_files = OutputMultiPath(File(exists=True), desc="List of generated PNG files.")


class SlicesDir(FSLCommand):
    """Run slicesdir.

    Notes
    -----
    Usage: slicesdir [-o] [-p <image>] [-e <thr>] [-S] <filelist>
    -o         :  filelist is pairs ( <underlying> <red-outline> ) of images
    -p <image> :  use <image> as red-outline image on top of all images in <filelist>
    -e <thr>   :  use the specified threshold for edges (if >0 use this proportion of max-min,
                  if <0, use the absolute value)
    -S         :  output every second axial slice rather than just 9 ortho slices
    """

    _cmd = "slicesdir"
    input_spec = _SlicesDirInputSpec
    output_spec = _SlicesDirOutputSpec

    def _list_outputs(self):
        """Create a Bunch which contains all possible files generated by running the interface.

        Some files are always generated, others depending on which ``inputs`` options are set.

        Returns
        -------
        outputs : Bunch object
            Bunch object containing all possible files generated by
            interface object.
            If None, file was not generated
            Else, contains path, filename of generated outputfile
        """
        outputs = self._outputs().get()

        out_dir = os.path.abspath(os.path.join(os.getcwd(), "slicesdir"))
        outputs["out_dir"] = out_dir
        outputs["out_files"] = [
            self._gen_fname(
                basename=f.replace(os.sep, "_"),
                cwd=out_dir,
                ext=self.inputs.out_extension,
            )
            for f in self.inputs.in_files
        ]
        temp_files = [
            "grota.png",
            "grotb.png",
            "grotc.png",
            "grotd.png",
            "grote.png",
            "grotf.png",
            "grotg.png",
            "groth.png",
            "groti.png",
        ]
        outputs["slicewise_files"] = [os.path.join(out_dir, f) for f in temp_files]
        return outputs

    def _gen_filename(self, name):
        if name == "out_files":
            return self._list_outputs()[name]

        return None


class _PNGAppendInputSpec(FSLCommandInputSpec):
    in_files = InputMultiPath(
        File(exists=True),
        mandatory=True,
        argstr="%s",
        position=0,
        desc="List of files to process.",
    )
    out_file = File(exists=False, mandatory=True, argstr="%s", position=1, desc="Output file.")


class _PNGAppendOutputSpec(TraitedSpec):
    out_file = File(exists=True, desc="Output file.")


class PNGAppend(FSLCommand):
    """Run pngappend.

    Notes
    -----
    pngappend  -  append PNG files horizontally and/or vertically into a new PNG (or GIF) file

    Usage: pngappend <input 1> <+|-> [n] <input 2> [<+|-> [n] <input n>]  output>

    + appends horizontally,
    - appends vertically (i.e. works like a linebreak)
    [n] number ofgap pixels
    note that files with .gif extension will be input/output in GIF format
    """

    _cmd = "pngappend"
    input_spec = _PNGAppendInputSpec
    output_spec = _PNGAppendOutputSpec

    def _format_arg(self, name, spec, value):
        if name == "in_files":
            if isinstance(value, str):
                value = [value]

            return " + ".join(value)

        return super(PNGAppend, self)._format_arg(name, spec, value)

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["out_file"] = os.path.abspath(self.inputs.out_file)
        return outputs


class _PlotCiftiParcellationInputSpec(BaseInterfaceInputSpec):
    in_files = traits.List(
        File(exists=True),
        mandatory=True,
        desc="CIFTI files to plot.",
    )
    cortical_atlases = traits.List(
        traits.Str,
        mandatory=True,
        desc="Atlases to select from 'labels'.",
    )
    labels = traits.List(
        traits.Str,
        mandatory=True,
        desc="Labels for the CIFTI files.",
    )
    out_file = File(
        exists=False,
        mandatory=False,
        desc="Output file.",
        default="plot.svg",
        usedefault=True,
    )
    vmin = traits.Float(
        mandatory=False,
        default_value=0,
        usedefault=True,
        desc="Minimum value for the colormap.",
    )
    vmax = traits.Float(
        mandatory=False,
        default_value=0,
        usedefault=True,
        desc="Maximum value for the colormap.",
    )


class _PlotCiftiParcellationOutputSpec(TraitedSpec):
    out_file = File(exists=True, desc="Output file.")


class PlotCiftiParcellation(SimpleInterface):
    """Plot a parcellated (.pscalar.nii) CIFTI file."""

    input_spec = _PlotCiftiParcellationInputSpec
    output_spec = _PlotCiftiParcellationOutputSpec

    def _run_interface(self, runtime):
        assert len(self.inputs.in_files) == len(self.inputs.labels)
        assert len(self.inputs.cortical_atlases) > 0

        rh = str(
            get_template(
                template="fsLR",
                hemi="R",
                density="32k",
                suffix="midthickness",
                extension=".surf.gii",
            )
        )
        lh = str(
            get_template(
                template="fsLR",
                hemi="L",
                density="32k",
                suffix="midthickness",
                extension=".surf.gii",
            )
        )

        # Create Figure and GridSpec.
        # One subplot for each file. Each file will then have four subplots, arranged in a square.
        cortical_files = [
            self.inputs.in_files[i]
            for i, atlas in enumerate(self.inputs.labels)
            if atlas in self.inputs.cortical_atlases
        ]
        cortical_atlases = [
            atlas for atlas in self.inputs.labels if atlas in self.inputs.cortical_atlases
        ]
        n_files = len(cortical_files)
        fig = plt.figure(constrained_layout=False)

        if n_files == 1:
            fig.set_size_inches(6.5, 6)
            # Add an additional column for the colorbar
            gs = GridSpec(1, 2, figure=fig, width_ratios=[1, 0.05])
            gs_list = [gs[0, 0]]
            subplots = [fig.add_subplot(gs) for gs in gs_list]
            cbar_gs_list = [gs[0, 1]]
        else:
            nrows = np.ceil(n_files / 2).astype(int)
            fig.set_size_inches(12.5, 6 * nrows)
            # Add an additional column for the colorbar
            gs = GridSpec(nrows, 3, figure=fig, width_ratios=[1, 1, 0.05])
            gs_list = [gs[i, j] for i in range(nrows) for j in range(2)]
            subplots = [fig.add_subplot(gs) for gs in gs_list]
            cbar_gs_list = [gs[i, 2] for i in range(nrows)]

        for subplot in subplots:
            subplot.set_axis_off()

        vmin, vmax = self.inputs.vmin, self.inputs.vmax
        if vmin == vmax:
            # Define vmin and vmax based on all of the files
            vmin, vmax = np.inf, -np.inf
            LOGGER.warning(f"Setting vmin={vmin}, vmax={vmax}")
            for cortical_file in cortical_files:
                img_data = nb.load(cortical_file).get_fdata()
                vmin = np.min([np.nanmin(img_data), vmin])
                vmax = np.max([np.nanmax(img_data), vmax])
                LOGGER.warning(f"Setting vmin={vmin}, vmax={vmax}")

        for i_file in range(n_files):
            subplot = subplots[i_file]
            subplot.set_title(cortical_atlases[i_file])
            subplot_gridspec = gs_list[i_file]

            # Create 4 Axes (2 rows, 2 columns) from the subplot
            gs_inner = GridSpecFromSubplotSpec(2, 2, subplot_spec=subplot_gridspec)
            inner_subplots = [
                fig.add_subplot(gs_inner[i, j], projection="3d")
                for i in range(2)
                for j in range(2)
            ]

            img = nb.load(cortical_files[i_file])
            img_data = img.get_fdata()
            img_axes = [img.header.get_axis(i) for i in range(img.ndim)]
            lh_surf_data = surf_data_from_cifti(
                img_data,
                img_axes[1],
                "CIFTI_STRUCTURE_CORTEX_LEFT",
            )
            rh_surf_data = surf_data_from_cifti(
                img_data,
                img_axes[1],
                "CIFTI_STRUCTURE_CORTEX_RIGHT",
            )

            plot_surf_stat_map(
                lh,
                lh_surf_data,
                vmin=vmin,
                vmax=vmax,
                hemi="left",
                view="lateral",
                engine="matplotlib",
                cmap="cool",
                colorbar=False,
                axes=inner_subplots[0],
                figure=fig,
            )
            plot_surf_stat_map(
                rh,
                rh_surf_data,
                vmin=vmin,
                vmax=vmax,
                hemi="right",
                view="lateral",
                engine="matplotlib",
                cmap="cool",
                colorbar=False,
                axes=inner_subplots[1],
                figure=fig,
            )
            plot_surf_stat_map(
                lh,
                lh_surf_data,
                vmin=vmin,
                vmax=vmax,
                hemi="left",
                view="medial",
                engine="matplotlib",
                cmap="cool",
                colorbar=False,
                axes=inner_subplots[2],
                figure=fig,
            )
            plot_surf_stat_map(
                rh,
                rh_surf_data,
                vmin=vmin,
                vmax=vmax,
                hemi="right",
                view="medial",
                engine="matplotlib",
                cmap="cool",
                colorbar=False,
                axes=inner_subplots[3],
                figure=fig,
            )

            for ax in inner_subplots:
                ax.set_rasterized(True)

        # Create a ScalarMappable with the "cool" colormap and the specified vmin and vmax
        sm = ScalarMappable(cmap="cool", norm=Normalize(vmin=vmin, vmax=vmax))

        for colorbar_gridspec in cbar_gs_list:
            colorbar_ax = fig.add_subplot(colorbar_gridspec)
            # Add a colorbar to colorbar_ax using the ScalarMappable
            fig.colorbar(sm, cax=colorbar_ax)

        self._results["out_file"] = fname_presuffix(
            cortical_files[0],
            suffix="_file.svg",
            newpath=runtime.cwd,
            use_ext=False,
        )
        fig.savefig(
            self._results["out_file"],
            bbox_inches="tight",
            pad_inches=None,
            format="svg",
        )
        plt.close(fig)

        return runtime
