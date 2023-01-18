"""Interfaces for the post-processing workflows."""
import os

import nibabel as nb
import numpy as np
import pandas as pd
from nipype import logging
from nipype.interfaces.base import (
    BaseInterfaceInputSpec,
    File,
    SimpleInterface,
    TraitedSpec,
    traits,
)

from xcp_d.utils.confounds import _infer_dummy_scans, load_motion
from xcp_d.utils.filemanip import fname_presuffix
from xcp_d.utils.modified_data import (
    _drop_dummy_scans,
    compute_fd,
    downcast_to_32,
    generate_mask,
    interpolate_masked_data,
)
from xcp_d.utils.write_save import read_ndata, write_ndata

LOGGER = logging.getLogger("nipype.interface")


class _ConvertTo32InputSpec(BaseInterfaceInputSpec):
    bold_file = traits.Either(
        None,
        File(exists=True),
        desc="BOLD file",
        mandatory=False,
        usedefault=True,
    )
    ref_file = traits.Either(
        None,
        File(exists=True),
        desc="BOLD reference file",
        mandatory=False,
        usedefault=True,
    )
    bold_mask = traits.Either(
        None,
        File(exists=True),
        desc="BOLD mask file",
        mandatory=False,
        usedefault=True,
    )
    t1w = traits.Either(
        None,
        File(exists=True),
        desc="T1-weighted anatomical file",
        mandatory=False,
        usedefault=True,
    )
    t1seg = traits.Either(
        None,
        File(exists=True),
        desc="T1-space segmentation file",
        mandatory=False,
        usedefault=True,
    )
    t1w_mask = traits.Either(
        None,
        File(exists=True),
        desc="T1-space mask file",
        mandatory=False,
        usedefault=True,
    )


class _ConvertTo32OutputSpec(TraitedSpec):
    bold_file = traits.Either(
        None,
        File(exists=True),
        desc="BOLD file",
        mandatory=False,
    )
    ref_file = traits.Either(
        None,
        File(exists=True),
        desc="BOLD reference file",
        mandatory=False,
    )
    bold_mask = traits.Either(
        None,
        File(exists=True),
        desc="BOLD mask file",
        mandatory=False,
    )
    t1w = traits.Either(
        None,
        File(exists=True),
        desc="T1-weighted anatomical file",
        mandatory=False,
    )
    t1seg = traits.Either(
        None,
        File(exists=True),
        desc="T1-space segmentation file",
        mandatory=False,
    )
    t1w_mask = traits.Either(
        None,
        File(exists=True),
        desc="T1-space mask file",
        mandatory=False,
    )


class ConvertTo32(SimpleInterface):
    """Downcast files from >32-bit to 32-bit if necessary."""

    input_spec = _ConvertTo32InputSpec
    output_spec = _ConvertTo32OutputSpec

    def _run_interface(self, runtime):
        self._results["bold_file"] = downcast_to_32(self.inputs.bold_file)
        self._results["ref_file"] = downcast_to_32(self.inputs.ref_file)
        self._results["bold_mask"] = downcast_to_32(self.inputs.bold_mask)
        self._results["t1w"] = downcast_to_32(self.inputs.t1w)
        self._results["t1seg"] = downcast_to_32(self.inputs.t1seg)
        self._results["t1w_mask"] = downcast_to_32(self.inputs.t1w_mask)

        return runtime


class _RemoveTRInputSpec(BaseInterfaceInputSpec):
    bold_file = File(exists=True, mandatory=True, desc="Either cifti or nifti ")
    dummy_scans = traits.Either(
        traits.Int,
        "auto",
        mandatory=True,
        desc=(
            "Number of volumes to drop from the beginning, "
            "calculated in an earlier workflow from dummytime/dummy_scans "
            "and repetition time."
        ),
    )
    confounds_file = File(
        exists=True,
        mandatory=True,
        desc="TSV file with selected confounds for denoising.",
    )
    fmriprep_confounds_file = File(
        exists=True,
        mandatory=True,
        desc="fMRIPrep confounds tsv. Used for motion-based censoring.",
    )


class _RemoveTROutputSpec(TraitedSpec):
    confounds_file_dropped_TR = File(
        exists=True,
        mandatory=True,
        desc="TSV file with selected confounds for denoising, after removing TRs.",
    )

    fmriprep_confounds_file_dropped_TR = File(
        exists=True,
        mandatory=True,
        desc="fMRIPrep confounds tsv after removing TRs. Used for motion-based censoring.",
    )

    bold_file_dropped_TR = File(
        exists=True,
        mandatory=True,
        desc="bold or cifti with volumes dropped",
    )
    dummy_scans = traits.Int(desc="Number of volumes dropped.")


class RemoveTR(SimpleInterface):
    """Removes initial volumes from a nifti or cifti file.

    A bold file and its corresponding confounds TSV (fmriprep format)
    are adjusted to remove the first n seconds of data.
    """

    input_spec = _RemoveTRInputSpec
    output_spec = _RemoveTROutputSpec

    def _run_interface(self, runtime):
        dummy_scans = _infer_dummy_scans(
            dummy_scans=self.inputs.dummy_scans,
            confounds_file=self.inputs.fmriprep_confounds_file,
        )

        self._results["dummy_scans"] = dummy_scans

        # Check if we need to do anything
        if dummy_scans == 0:
            # write the output out
            self._results["bold_file_dropped_TR"] = self.inputs.bold_file
            self._results[
                "fmriprep_confounds_file_dropped_TR"
            ] = self.inputs.fmriprep_confounds_file
            self._results["confounds_file_dropped_TR"] = self.inputs.confounds_file
            return runtime

        # get the file names to output to
        self._results["bold_file_dropped_TR"] = fname_presuffix(
            self.inputs.bold_file,
            newpath=runtime.cwd,
            suffix="_dropped",
            use_ext=True,
        )
        self._results["fmriprep_confounds_file_dropped_TR"] = fname_presuffix(
            self.inputs.fmriprep_confounds_file,
            newpath=runtime.cwd,
            suffix="_fmriprepDropped",
            use_ext=True,
        )
        self._results["confounds_file_dropped_TR"] = fname_presuffix(
            self.inputs.bold_file,
            suffix="_selected_confounds_dropped.tsv",
            newpath=os.getcwd(),
            use_ext=False,
        )

        # Remove the dummy volumes
        dropped_image = _drop_dummy_scans(self.inputs.bold_file, dummy_scans=dummy_scans)
        dropped_image.to_filename(self._results["bold_file_dropped_TR"])

        # Drop the first N rows from the pandas dataframe
        fmriprep_confounds_df = pd.read_table(self.inputs.fmriprep_confounds_file)
        dropped_fmriprep_confounds_df = fmriprep_confounds_df.drop(np.arange(dummy_scans))

        # Drop the first N rows from the confounds file
        confounds_df = pd.read_table(self.inputs.confounds_file)
        confounds_tsv_dropped = confounds_df.drop(np.arange(dummy_scans))

        # Save out results
        dropped_fmriprep_confounds_df.to_csv(
            self._results["fmriprep_confounds_file_dropped_TR"],
            sep="\t",
            index=False,
        )
        confounds_tsv_dropped.to_csv(
            self._results["confounds_file_dropped_TR"],
            sep="\t",
            index=False,
        )

        return runtime


class _CensorScrubInputSpec(BaseInterfaceInputSpec):
    in_file = File(exists=True, mandatory=True, desc=" Partially processed bold or nifti")
    fd_thresh = traits.Float(
        mandatory=False,
        default_value=0.2,
        desc="Framewise displacement threshold. All values above this will be dropped.",
    )
    confounds_file = File(
        exists=True,
        mandatory=True,
        desc="File with selected confounds for denoising.",
    )
    fmriprep_confounds_file = File(
        exists=True,
        mandatory=True,
        desc="fMRIPrep confounds tsv. Used for flagging high-motion volumes.",
    )
    head_radius = traits.Float(mandatory=False, default_value=50, desc="Head radius in mm ")
    motion_filter_type = traits.Either(
        None,
        traits.Str,
        mandatory=True,
    )
    motion_filter_order = traits.Int(mandatory=True)
    TR = traits.Float(mandatory=True, desc="Repetition time in seconds")
    band_stop_min = traits.Either(
        None,
        traits.Float,
        mandatory=True,
        desc="Lower frequency for the band-stop motion filter, in breaths-per-minute (bpm).",
    )
    band_stop_max = traits.Either(
        None,
        traits.Float,
        mandatory=True,
        desc="Upper frequency for the band-stop motion filter, in breaths-per-minute (bpm).",
    )


class _CensorScrubOutputSpec(TraitedSpec):
    bold_censored = File(exists=True, mandatory=True, desc="FD-censored bold file")

    fmriprep_confounds_censored = File(
        exists=True,
        mandatory=True,
        desc="fmriprep_confounds_file censored",
    )
    confounds_censored = File(
        exists=True,
        mandatory=True,
        desc="confounds_file censored",
    )
    tmask = File(
        exists=True,
        mandatory=True,
        desc=(
            "Temporal mask; all values above fd_thresh set to 1. "
            "This is a TSV file with one column: 'framewise_displacement'."
        ),
    )
    filtered_motion = File(
        exists=True,
        mandatory=True,
        desc=(
            "Framewise displacement timeseries. "
            "This is a TSV file with one column: 'framewise_displacement'."
        ),
    )


class CensorScrub(SimpleInterface):
    """Generate a temporal mask based on recalculated FD.

    Takes in confound files, bold file to be censored, and information about filtering-
    including band stop values and motion filter type.
    Then proceeds to create a motion-filtered confounds matrix and recalculates FD from
    filtered motion parameters.
    Finally generates temporal mask with volumes above FD threshold set to 1,
    then dropped from both confounds file and bolds file.
    Outputs temporal mask, framewise displacement timeseries and censored bold files.
    """

    input_spec = _CensorScrubInputSpec
    output_spec = _CensorScrubOutputSpec

    def _run_interface(self, runtime):
        # Read in fmriprep confounds tsv to calculate FD
        fmriprep_confounds_tsv_uncensored = pd.read_table(self.inputs.fmriprep_confounds_file)
        motion_df = load_motion(
            fmriprep_confounds_tsv_uncensored.copy(),
            TR=self.inputs.TR,
            motion_filter_type=self.inputs.motion_filter_type,
            motion_filter_order=self.inputs.motion_filter_order,
            band_stop_min=self.inputs.band_stop_min,
            band_stop_max=self.inputs.band_stop_max,
        )

        fd_timeseries_uncensored = compute_fd(
            confound=motion_df,
            head_radius=self.inputs.head_radius,
        )
        motion_df["framewise_displacement"] = fd_timeseries_uncensored

        # Read in confounds file and bold file to be censored
        confounds_tsv_uncensored = pd.read_table(self.inputs.confounds_file)
        bold_file_uncensored = nb.load(self.inputs.in_file).get_fdata()

        # Generate temporal mask with all timepoints have FD over threshold
        # set to 1 and then dropped.
        tmask = generate_mask(
            fd_res=fd_timeseries_uncensored,
            fd_thresh=self.inputs.fd_thresh,
        )
        if np.sum(tmask) > 0:  # If any FD values exceed the threshold
            if nb.load(self.inputs.in_file).ndim > 2:  # If Nifti
                bold_file_censored = bold_file_uncensored[:, :, :, tmask == 0]
            else:
                bold_file_censored = bold_file_uncensored[tmask == 0, :]

            fmriprep_confounds_tsv_censored = fmriprep_confounds_tsv_uncensored.loc[tmask == 0]
            confounds_tsv_censored = confounds_tsv_uncensored.loc[tmask == 0]

        else:  # No censoring needed
            bold_file_censored = bold_file_uncensored
            fmriprep_confounds_tsv_censored = fmriprep_confounds_tsv_uncensored
            confounds_tsv_censored = confounds_tsv_uncensored

        # Turn censored bold into image
        if nb.load(self.inputs.in_file).ndim > 2:
            # If it's a Nifti image
            bold_file_censored = nb.Nifti1Image(
                bold_file_censored,
                affine=nb.load(self.inputs.in_file).affine,
                header=nb.load(self.inputs.in_file).header,
            )
        else:
            # If it's a Cifti image
            original_image = nb.load(self.inputs.in_file)
            time_axis, brain_model_axis = [
                original_image.header.get_axis(i) for i in range(original_image.ndim)
            ]
            new_total_volumes = bold_file_censored.shape[0]
            censored_time_axis = time_axis[:new_total_volumes]
            # Note: not an error. A time axis cannot be accessed with irregularly
            # spaced values. Since we use the tmask for marking the volumes removed,
            # the time axis also is not used further in XCP.
            censored_header = nb.cifti2.Cifti2Header.from_axes(
                (censored_time_axis, brain_model_axis)
            )
            bold_file_censored = nb.Cifti2Image(
                bold_file_censored,
                header=censored_header,
                nifti_header=original_image.nifti_header,
            )

        # get the output
        self._results["bold_censored"] = fname_presuffix(
            self.inputs.in_file,
            suffix="_censored",
            newpath=runtime.cwd,
            use_ext=True,
        )
        self._results["fmriprep_confounds_censored"] = fname_presuffix(
            self.inputs.in_file,
            suffix="_fmriprep_confounds_censored.tsv",
            newpath=runtime.cwd,
            use_ext=False,
        )
        self._results["confounds_censored"] = fname_presuffix(
            self.inputs.in_file,
            suffix="_selected_confounds_censored.tsv",
            newpath=runtime.cwd,
            use_ext=False,
        )

        self._results["tmask"] = fname_presuffix(
            self.inputs.in_file,
            suffix="_desc-fd_outliers.tsv",
            newpath=runtime.cwd,
            use_ext=False,
        )
        self._results["filtered_motion"] = fname_presuffix(
            self.inputs.in_file,
            suffix="_desc-filtered_motion.tsv",
            newpath=runtime.cwd,
            use_ext=False,
        )

        bold_file_censored.to_filename(self._results["bold_censored"])

        fmriprep_confounds_tsv_censored.to_csv(
            self._results["fmriprep_confounds_censored"],
            index=False,
            header=True,
            sep="\t",
        )
        outliers_df = pd.DataFrame(data=tmask, columns=["framewise_displacement"])
        outliers_df.to_csv(
            self._results["tmask"],
            index=False,
            header=True,
            sep="\t",
        )

        motion_df.to_csv(
            self._results["filtered_motion"],
            index=False,
            header=True,
            sep="\t",
        )
        confounds_tsv_censored.to_csv(
            self._results["confounds_censored"],
            index=False,
            sep="\t",
        )
        return runtime


class _InterpolateInputSpec(BaseInterfaceInputSpec):
    in_file = File(exists=True, mandatory=True, desc=" censored or clean bold")
    bold_file = File(exists=True, mandatory=True, desc=" censored or clean bold")
    tmask = File(exists=True, mandatory=True, desc="temporal mask")
    mask_file = File(exists=True, mandatory=False, desc="required for nifti")
    TR = traits.Float(mandatory=True, desc="repetition time in TR")


class _InterpolateOutputSpec(TraitedSpec):
    bold_interpolated = File(exists=True, mandatory=True, desc=" fmriprep censored")


class Interpolate(SimpleInterface):
    """Interpolates scrubbed/regressed BOLD data based on temporal mask.

    Interpolation takes in the scrubbed/regressed bold file and temporal mask,
    subs in the scrubbed values with 0, and then uses scipy's
    interpolate functionality to interpolate values into these 0s.
    It outputs the interpolated file.
    """

    input_spec = _InterpolateInputSpec
    output_spec = _InterpolateOutputSpec

    def _run_interface(self, runtime):
        # Read in regressed bold data and temporal mask
        # from censorscrub
        bold_data = read_ndata(datafile=self.inputs.in_file, maskfile=self.inputs.mask_file)

        tmask_df = pd.read_table(self.inputs.tmask)
        tmask_arr = tmask_df["framewise_displacement"].values

        # check if any volumes were censored - if they were,
        # put 0s in their place.
        if bold_data.shape[1] != len(tmask_arr):
            data_with_zeros = np.zeros([bold_data.shape[0], len(tmask_arr)])
            data_with_zeros[:, tmask_arr == 0] = bold_data
        else:
            data_with_zeros = bold_data

        # interpolate the data using scipy's interpolation functionality
        interpolated_data = interpolate_masked_data(
            bold_data=data_with_zeros,
            tmask=tmask_arr,
            TR=self.inputs.TR,
        )

        # save out results
        self._results["bold_interpolated"] = fname_presuffix(
            self.inputs.in_file,
            newpath=os.getcwd(),
            use_ext=True,
        )

        write_ndata(
            data_matrix=interpolated_data,
            template=self.inputs.bold_file,
            mask=self.inputs.mask_file,
            TR=self.inputs.TR,
            filename=self._results["bold_interpolated"],
        )

        return runtime


class _CiftiZerosToNaNsInputSpec(BaseInterfaceInputSpec):
    in_file = File(exists=True, mandatory=True, desc="CIFTI file to modify.")
    out_file = File(
        "modified_data.dtseries.nii",
        usedefault=True,
        exists=False,
        desc="The name of the modified file to write out. modified_data.dtseries.nii by default.",
    )


class _CiftiZerosToNaNsOutputSpec(TraitedSpec):
    out_file = File(exists=True, mandatory=True, desc="Output CIFTI file.")


class CiftiZerosToNaNs(SimpleInterface):
    """Convert all all-zero vertices' time series to NaNs in a CIFTI file.

    This is done so that these vertices will be flagged as missing data by wb_command.
    This interface is only designed to work with dtseries CIFTIs where the first axis is time and
    the second is space.
    """

    input_spec = _CiftiZerosToNaNsInputSpec
    output_spec = _CiftiZerosToNaNsOutputSpec

    def _run_interface(self, runtime):
        cifti_obj = nb.load(self.inputs.in_file)
        # load data as memmap
        data = cifti_obj.get_fdata()
        # load it in memory
        data = np.array(data)

        # find all vertices with all zeros or one or more NaNs
        stdevs = np.std(data, axis=0)
        # nan > 0 == False, nan <= 0 == False
        zero_std = ~(stdevs > 0)  # std over time is zero or NaN
        zero_values = ~(data[0, :] > 0)  # first time point's value is zero or NaN
        bad_vertex_idx = np.where(np.logical_and(zero_std, zero_values))[0]

        if bad_vertex_idx.size:
            LOGGER.warning(
                f"{bad_vertex_idx.size}/{zero_std.size} vertices have missing data. "
                "Filling these vertices with NaNs so they will be ignored by parcellation step."
            )

        # replace the bad vertices' values with NaNs
        data[:, bad_vertex_idx] = np.nan

        # make the modified img object
        img = nb.Cifti2Image(
            dataobj=data,
            header=cifti_obj.header,
            file_map=cifti_obj.file_map,
            nifti_header=cifti_obj.nifti_header,
        )

        self._results["out_file"] = os.path.abspath(self.inputs.out_file)
        img.to_filename(self._results["out_file"])

        return runtime


class _CiftiBinarizeCoverageInputSpec(BaseInterfaceInputSpec):
    in_file = File(exists=True, mandatory=True, desc="CIFTI file to modify.")
    masked_binarized_file = File(
        "binarized_data.dtseries.nii",
        usedefault=True,
        exists=False,
        desc="The name of the modified file to write out. binarized_data.dtseries.nii by default.",
    )
    unmasked_binarized_file = File(
        "all_ones.dtseries.nii",
        usedefault=True,
        exists=False,
        desc="The name of the modified file to write out. all_ones.dtseries.nii by default.",
    )


class _CiftiBinarizeCoverageOutputSpec(TraitedSpec):
    masked_binarized_file = File(exists=True, mandatory=True, desc="Output CIFTI file.")
    unmasked_binarized_file = File(exists=True, mandatory=True, desc="Output CIFTI file.")


class CiftiBinarizeCoverage(SimpleInterface):
    """Replace all NaNs with zeros, and all non-NaNs with ones."""

    input_spec = _CiftiBinarizeCoverageInputSpec
    output_spec = _CiftiBinarizeCoverageOutputSpec

    def _run_interface(self, runtime):
        cifti_obj = nb.load(self.inputs.in_file)

        # load data as memmap
        data = cifti_obj.get_fdata()
        # load it in memory
        data = np.array(data)
        # select first volume
        data = data[..., 0]

        new_data = np.zeros_like(data)
        new_data[~np.isnan(data)] = 1

        new_unmasked_data = np.ones_like(data)

        # make the modified img object
        masked_img = nb.Cifti2Image(
            dataobj=new_data,
            header=cifti_obj.header,
            file_map=cifti_obj.file_map,
            nifti_header=cifti_obj.nifti_header,
        )
        unmasked_img = nb.Cifti2Image(
            dataobj=new_unmasked_data,
            header=cifti_obj.header,
            file_map=cifti_obj.file_map,
            nifti_header=cifti_obj.nifti_header,
        )

        self._results["masked_binarized_file"] = os.path.abspath(self.inputs.masked_binarized_file)
        masked_img.to_filename(self._results["masked_binarized_file"])
        self._results["unmasked_binarized_file"] = os.path.abspath(
            self.inputs.unmasked_binarized_file
        )
        unmasked_img.to_filename(self._results["unmasked_binarized_file"])

        return runtime


class _CiftiApplyCoverageThresholdInputSpec(BaseInterfaceInputSpec):
    parc_file = File(exists=True, mandatory=True, desc="Parcellated CIFTI file to modify.")
    masked_coverage_file = File(
        exists=True,
        mandatory=True,
        desc=(
            "Parcellated CIFTI coverage file. "
            "Each parcel's value is the proportion of vertices in the parcel that are covered in "
            "the data."
        ),
    )
    unmasked_coverage_file = File(
        exists=True,
        mandatory=True,
        desc=(
            "Parcellated CIFTI coverage file. "
            "Each parcel's value is the proportion of vertices in the parcel that are covered in "
            "the data."
        ),
    )
    out_file = File(
        "thresholded_timeseries.ptseries.nii",
        usedefault=True,
        exists=False,
        desc=(
            "The name of the modified file to write out. "
            "thresholded_timeseries.ptseries.nii by default."
        ),
    )


class _CiftiApplyCoverageThresholdOutputSpec(TraitedSpec):
    out_file = File(exists=True, mandatory=True, desc="Output CIFTI file.")


class CiftiApplyCoverageThreshold(SimpleInterface):
    """Apply 50% coverage threshold to parcellated data."""

    input_spec = _CiftiApplyCoverageThresholdInputSpec
    output_spec = _CiftiApplyCoverageThresholdOutputSpec

    def _run_interface(self, runtime):
        parc_cifti_obj = nb.load(self.inputs.parc_file)
        masked_cov_cifti_obj = nb.load(self.inputs.masked_coverage_file)
        unmasked_cov_cifti_obj = nb.load(self.inputs.unmasked_coverage_file)

        # load data as memmap
        data = parc_cifti_obj.get_fdata()
        masked_cov_data = masked_cov_cifti_obj.get_fdata()
        unmasked_cov_data = unmasked_cov_cifti_obj.get_fdata()
        # load it in memory
        data = np.array(data)
        masked_cov_data = np.array(masked_cov_data)
        unmasked_cov_data = np.array(unmasked_cov_data)
        # select first volume
        masked_cov_data = np.squeeze(masked_cov_data)
        unmasked_cov_data = np.squeeze(unmasked_cov_data)

        prop_coverage = masked_cov_data / unmasked_cov_data
        coverage_thresholded = prop_coverage < 0.5  # we require 50%+ coverage

        if np.any(coverage_thresholded):
            LOGGER.warning(
                f"{coverage_thresholded.sum()}/{coverage_thresholded.size} of parcels have "
                "<50%% coverage"
            )

        new_data = np.zeros_like(data)
        new_data[coverage_thresholded, :] = 0

        # make the modified img object
        img = nb.Cifti2Image(
            dataobj=new_data,
            header=parc_cifti_obj.header,
            file_map=parc_cifti_obj.file_map,
            nifti_header=parc_cifti_obj.nifti_header,
        )

        self._results["out_file"] = os.path.abspath(self.inputs.out_file)
        img.to_filename(self._results["out_file"])

        return runtime
