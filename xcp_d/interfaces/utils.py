"""Miscellaneous utility interfaces."""

import json
import os

import h5py
import numpy as np
import pandas as pd
from nipype import logging
from nipype.interfaces.base import (
    BaseInterfaceInputSpec,
    File,
    OutputMultiObject,
    SimpleInterface,
    TraitedSpec,
    Undefined,
    isdefined,
    traits,
    traits_extension,
)

from xcp_d.utils.filemanip import fname_presuffix
from xcp_d.utils.modified_data import calculate_dof, downcast_to_32
from xcp_d.utils.qcmetrics import compute_dvars, compute_registration_qc
from xcp_d.utils.write_save import read_ndata

LOGGER = logging.getLogger('nipype.interface')


class _ConvertTo32InputSpec(BaseInterfaceInputSpec):
    bold_file = traits.Either(
        None,
        File(exists=True),
        desc='BOLD file',
        mandatory=False,
        usedefault=True,
    )
    boldref = traits.Either(
        None,
        File(exists=True),
        desc='BOLD reference file',
        mandatory=False,
        usedefault=True,
    )
    bold_mask = traits.Either(
        None,
        File(exists=True),
        desc='BOLD mask file',
        mandatory=False,
        usedefault=True,
    )
    t1w = traits.Either(
        None,
        File(exists=True),
        desc='T1-weighted anatomical file',
        mandatory=False,
        usedefault=True,
    )
    t2w = traits.Either(
        None,
        File(exists=True),
        desc='T2-weighted anatomical file',
        mandatory=False,
        usedefault=True,
    )


class _ConvertTo32OutputSpec(TraitedSpec):
    bold_file = traits.Either(
        None,
        File(exists=True),
        desc='BOLD file',
        mandatory=False,
    )
    boldref = traits.Either(
        None,
        File(exists=True),
        desc='BOLD reference file',
        mandatory=False,
    )
    bold_mask = traits.Either(
        None,
        File(exists=True),
        desc='BOLD mask file',
        mandatory=False,
    )
    t1w = traits.Either(
        None,
        File(exists=True),
        desc='T1-weighted anatomical file',
        mandatory=False,
    )
    t2w = traits.Either(
        None,
        File(exists=True),
        desc='T2-weighted anatomical file',
        mandatory=False,
    )


class ConvertTo32(SimpleInterface):
    """Downcast files from >32-bit to 32-bit if necessary."""

    input_spec = _ConvertTo32InputSpec
    output_spec = _ConvertTo32OutputSpec

    def _run_interface(self, runtime):
        self._results['bold_file'] = downcast_to_32(self.inputs.bold_file)
        self._results['boldref'] = downcast_to_32(self.inputs.boldref)
        self._results['bold_mask'] = downcast_to_32(self.inputs.bold_mask)
        self._results['t1w'] = downcast_to_32(self.inputs.t1w)
        self._results['t2w'] = downcast_to_32(self.inputs.t2w)

        return runtime


class _FilterUndefinedInputSpec(BaseInterfaceInputSpec):
    inlist = traits.List(
        traits.Either(
            traits.Str,
            None,
            Undefined,
        ),
        mandatory=True,
        desc='List of objects to filter.',
    )


class _FilterUndefinedOutputSpec(TraitedSpec):
    outlist = OutputMultiObject(
        traits.Str,
        desc='Filtered list of objects.',
    )


class FilterUndefined(SimpleInterface):
    """Extract timeseries and compute connectivity matrices."""

    input_spec = _FilterUndefinedInputSpec
    output_spec = _FilterUndefinedOutputSpec

    def _run_interface(self, runtime):
        inlist = self.inputs.inlist
        outlist = []
        for item in inlist:
            if item is not None and traits_extension.isdefined(item):
                outlist.append(item)
        self._results['outlist'] = outlist
        return runtime


class _LINCQCInputSpec(BaseInterfaceInputSpec):
    name_source = File(
        exists=False,
        mandatory=True,
        desc=(
            'Preprocessed BOLD file. Used to find files. '
            'In the case of the concatenation workflow, '
            'this may be a nonexistent file '
            '(i.e., the preprocessed BOLD file, with the run entity removed).'
        ),
    )
    bold_file = File(
        exists=True,
        mandatory=True,
        desc='Preprocessed BOLD file, after dummy scan removal. Used in carpet plot.',
    )
    dummy_scans = traits.Int(mandatory=True, desc='Dummy time to drop')
    temporal_mask = traits.Either(
        File(exists=True),
        Undefined,
        desc='Temporal mask',
    )
    motion_file = File(
        exists=True,
        mandatory=True,
        desc='fMRIPrep confounds file, after dummy scans removal',
    )
    design_matrix = File(
        exists=True,
        mandatory=False,
        desc='Design matrix used in the denoising step.',
    )
    cleaned_file = File(
        exists=True,
        mandatory=True,
        desc='Processed file, after denoising and censoring.',
    )
    TR = traits.Float(mandatory=True, desc='Repetition time, in seconds.')
    head_radius = traits.Float(mandatory=True, desc='Head radius for FD calculation, in mm.')
    high_pass = traits.Float(
        mandatory=True,
        desc='High-pass filter cutoff, in Hz.',
    )
    low_pass = traits.Float(
        mandatory=True,
        desc='Low-pass filter cutoff, in Hz.',
    )

    # Inputs used only for nifti data
    anat_mask_anatspace = File(
        exists=True,
        mandatory=False,
        desc=(
            'Anatomically-derived brain mask in anatomical space. '
            'Used to calculate coregistration QC metrics.'
        ),
    )
    template_mask = File(
        exists=True,
        mandatory=False,
        desc=(
            "Template's official brain mask. "
            'This matches the space of bold_mask_stdspace, '
            'but does not necessarily match the space of bold_mask_inputspace. '
            'Used to calculate normalization QC metrics.'
        ),
    )
    bold_mask_anatspace = File(
        exists=True,
        mandatory=False,
        desc='BOLD mask in anatomical space. Used to calculate coregistration QC metrics.',
    )
    bold_mask_inputspace = traits.Either(
        None,
        File(exists=True),
        mandatory=True,
        desc=(
            'Mask file from NIfTI. May be None, for CIFTI processing. '
            'The mask is in the same space as the BOLD data, which may not be the same as the '
            'bold_mask_stdspace file. '
            'Used to load the masked BOLD data. Not used for QC metrics.'
        ),
    )
    bold_mask_stdspace = File(
        exists=True,
        mandatory=False,
        desc=(
            'BOLD mask in template space. '
            'This matches the space of template_mask, '
            'but does not necessarily match the space of bold_mask_inputspace. '
            'Used to calculate normalization QC metrics.'
        ),
    )


class _LINCQCOutputSpec(TraitedSpec):
    qc_file = File(exists=True, desc='QC TSV file.')
    qc_metadata = File(exists=True, desc='Sidecar JSON for QC TSV file.')


class LINCQC(SimpleInterface):
    """Calculate QC metrics used by the LINC lab."""

    input_spec = _LINCQCInputSpec
    output_spec = _LINCQCOutputSpec

    def _run_interface(self, runtime):
        # Load confound matrix and load motion without motion filtering
        motion_df = pd.read_table(self.inputs.motion_file)
        preproc_fd = motion_df['framewise_displacement'].to_numpy()
        rmsd = motion_df['rmsd'].to_numpy()
        if isdefined(self.inputs.design_matrix):
            design_matrix = pd.read_table(self.inputs.design_matrix)
            num_dof_used_by_denoising = design_matrix.shape[1] + 2  # intercept + linear detrend
        else:
            num_dof_used_by_denoising = np.nan

        # Determine number of dummy volumes and load temporal mask
        num_dummy_scans = self.inputs.dummy_scans  # not included in temporal mask
        if isdefined(self.inputs.temporal_mask):
            censoring_df = pd.read_table(self.inputs.temporal_mask)
            tmask_arr = censoring_df['framewise_displacement'].values
        else:
            tmask_arr = np.zeros(preproc_fd.size, dtype=int)

        num_censored_volumes = int(tmask_arr.sum())
        num_retained_volumes = int((tmask_arr == 0).sum())
        num_dof_lost_by_filter = calculate_dof(
            n_volumes=motion_df.shape[0],
            t_r=self.inputs.TR,
            high_pass=self.inputs.high_pass or 0,
            low_pass=self.inputs.low_pass or np.inf,
        )

        # Apply temporal mask to interpolated/full data
        rmsd_censored = rmsd[tmask_arr == 0]
        postproc_fd = preproc_fd[tmask_arr == 0]

        dvars_before_processing = compute_dvars(
            datat=read_ndata(
                datafile=self.inputs.bold_file,
                maskfile=self.inputs.bold_mask_inputspace,
            ),
        )[1]
        dvars_after_processing = compute_dvars(
            datat=read_ndata(
                datafile=self.inputs.cleaned_file,
                maskfile=self.inputs.bold_mask_inputspace,
            ),
        )[1]
        if preproc_fd.size != dvars_before_processing.size:
            raise ValueError(f'FD {preproc_fd.size} != DVARS {dvars_before_processing.size}\n')

        # Get the different components in the bold file name
        # eg: ['sub-colornest001', 'ses-1'], etc.
        _, bold_file_name = os.path.split(self.inputs.name_source)
        bold_file_name_components = bold_file_name.split('_')

        # Fill out dictionary with entities from filename
        qc_values_dict = {}
        for entity in bold_file_name_components[:-1]:
            qc_values_dict[entity.split('-')[0]] = entity.split('-')[1]

        # Calculate QC measures
        mean_fd = np.mean(preproc_fd)
        mean_fd_post_censoring = np.mean(postproc_fd)
        mean_relative_rms = np.nanmean(rmsd_censored)  # first value can be NaN if no dummy scans
        mean_dvars_before_processing = np.mean(dvars_before_processing)
        mean_dvars_after_processing = np.mean(dvars_after_processing)
        fd_dvars_correlation_initial = np.corrcoef(preproc_fd, dvars_before_processing)[0, 1]
        fd_dvars_correlation_final = np.corrcoef(postproc_fd, dvars_after_processing)[0, 1]
        rmsd_max_value = np.nanmax(rmsd_censored)

        # A summary of all the values
        qc_values_dict.update(
            {
                'mean_fd': [mean_fd],
                'mean_fd_post_censoring': [mean_fd_post_censoring],
                'mean_relative_rms': [mean_relative_rms],
                'max_relative_rms': [rmsd_max_value],
                'mean_dvars_initial': [mean_dvars_before_processing],
                'mean_dvars_final': [mean_dvars_after_processing],
                'num_dummy_volumes': [num_dummy_scans],
                'num_censored_volumes': [num_censored_volumes],
                'num_retained_volumes': [num_retained_volumes],
                'num_dof_used_by_denoising': [num_dof_used_by_denoising],
                'num_dof_used_by_filter': [num_dof_lost_by_filter],
                'fd_dvars_correlation_initial': [fd_dvars_correlation_initial],
                'fd_dvars_correlation_final': [fd_dvars_correlation_final],
            }
        )

        qc_metadata = {
            'mean_fd': {
                'LongName': 'Mean Framewise Displacement',
                'Description': (
                    'Average framewise displacement without any motion parameter filtering. '
                    'This value includes high-motion outliers, but not dummy volumes. '
                    'FD is calculated according to the Power definition.'
                ),
                'Units': 'mm',
                'Term URL': 'https://doi.org/10.1016/j.neuroimage.2011.10.018',
            },
            'mean_fd_post_censoring': {
                'LongName': 'Mean Framewise Displacement After Censoring',
                'Description': (
                    'Average framewise displacement without any motion parameter filtering. '
                    'This value does not include high-motion outliers or dummy volumes. '
                    'FD is calculated according to the Power definition.'
                ),
                'Units': 'mm',
                'Term URL': 'https://doi.org/10.1016/j.neuroimage.2011.10.018',
            },
            'mean_relative_rms': {
                'LongName': 'Mean Relative Root Mean Squared',
                'Description': (
                    'Average relative root mean squared calculated from motion parameters, '
                    'after removal of dummy volumes and high-motion outliers. '
                    "Relative in this case means 'relative to the previous scan'."
                ),
                'Units': 'arbitrary',
            },
            'max_relative_rms': {
                'LongName': 'Maximum Relative Root Mean Squared',
                'Description': (
                    'Maximum relative root mean squared calculated from motion parameters, '
                    'after removal of dummy volumes and high-motion outliers. '
                    "Relative in this case means 'relative to the previous scan'."
                ),
                'Units': 'arbitrary',
            },
            'mean_dvars_initial': {
                'LongName': 'Mean DVARS Before Postprocessing',
                'Description': (
                    'Average DVARS (temporal derivative of root mean squared variance over '
                    'voxels) calculated from the preprocessed BOLD file, after dummy scan removal.'
                ),
                'TermURL': 'https://doi.org/10.1016/j.neuroimage.2011.02.073',
            },
            'mean_dvars_final': {
                'LongName': 'Mean DVARS After Postprocessing',
                'Description': (
                    'Average DVARS (temporal derivative of root mean squared variance over '
                    'voxels) calculated from the denoised BOLD file.'
                ),
                'TermURL': 'https://doi.org/10.1016/j.neuroimage.2011.02.073',
            },
            'num_dummy_volumes': {
                'LongName': 'Number of Dummy Volumes',
                'Description': (
                    'The number of non-steady state volumes removed from the time series by XCP-D.'
                ),
            },
            'num_dof_used_by_denoising': {
                'LongName': 'Number of Degrees of Freedom Lost by Denoising',
                'Description': (
                    'The number of confounds used in the denoising step, plus intercept and '
                    'linear trend. '
                    'To estimate the degrees of freedom for bivariate correlations between '
                    'censored, denoised time series (ignoring the effect of autocorrelation), do '
                    'num_retained_volumes - (num_dof_used_by_denoising + num_dof_used_by_filter '
                    '+ 2).'
                ),
            },
            'num_dof_used_by_filter': {
                'LongName': 'Number of Degrees of Freedom Lost by Temporal Filter',
                'Description': (
                    'The degrees of freedom used up by the temporal filter. '
                    'To estimate the degrees of freedom for bivariate correlations between '
                    'censored, denoised time series (ignoring the effect of autocorrelation), do '
                    'num_retained_volumes - (num_dof_used_by_denoising + num_dof_used_by_filter '
                    '+ 2).'
                ),
            },
            'num_censored_volumes': {
                'LongName': 'Number of Censored Volumes',
                'Description': (
                    'The number of high-motion outlier volumes censored by XCP-D. '
                    'This does not include dummy volumes.'
                ),
            },
            'num_retained_volumes': {
                'LongName': 'Number of Retained Volumes',
                'Description': (
                    'The number of volumes retained in the denoised dataset. '
                    'This does not include dummy volumes or high-motion outliers. '
                    'To estimate the degrees of freedom for bivariate correlations between '
                    'censored, denoised time series (ignoring the effect of autocorrelation), do '
                    'num_retained_volumes - (num_dof_used_by_denoising + num_dof_used_by_filter '
                    '+ 2).'
                ),
            },
            'fd_dvars_correlation_initial': {
                'LongName': 'FD-DVARS Correlation Before Postprocessing',
                'Description': (
                    'The Pearson correlation coefficient between framewise displacement and DVARS '
                    '(temporal derivative of root mean squared variance over voxels), '
                    'after removal of dummy volumes, but before removal of high-motion outliers.'
                ),
            },
            'fd_dvars_correlation_final': {
                'LongName': 'FD-DVARS Correlation After Postprocessing',
                'Description': (
                    'The Pearson correlation coefficient between framewise displacement and DVARS '
                    '(temporal derivative of root mean squared variance over voxels), '
                    'after postprocessing. '
                    'The FD time series is unfiltered, but censored. '
                    'The DVARS time series is calculated from the denoised BOLD data.'
                ),
            },
        }

        if self.inputs.bold_mask_anatspace:  # If a bold mask in T1w is provided
            # Compute quality of registration
            registration_qc, registration_metadata = compute_registration_qc(
                bold_mask_anatspace=self.inputs.bold_mask_anatspace,
                anat_mask_anatspace=self.inputs.anat_mask_anatspace,
                bold_mask_stdspace=self.inputs.bold_mask_stdspace,
                template_mask=self.inputs.template_mask,
            )
            qc_values_dict.update(registration_qc)  # Add values to dictionary
            qc_metadata.update(registration_metadata)

        # Convert dictionary to df and write out the qc file
        df = pd.DataFrame(qc_values_dict)
        self._results['qc_file'] = fname_presuffix(
            self.inputs.cleaned_file,
            suffix='qc_bold.tsv',
            newpath=runtime.cwd,
            use_ext=False,
        )
        df.to_csv(self._results['qc_file'], index=False, header=True, sep='\t')

        # Write out the metadata file
        self._results['qc_metadata'] = fname_presuffix(
            self.inputs.cleaned_file,
            suffix='qc_bold.json',
            newpath=runtime.cwd,
            use_ext=False,
        )
        with open(self._results['qc_metadata'], 'w') as fo:
            json.dump(qc_metadata, fo, indent=4, sort_keys=True)

        return runtime


class _ABCCQCInputSpec(BaseInterfaceInputSpec):
    motion_file = File(
        exists=True,
        mandatory=True,
        desc='',
    )
    TR = traits.Float(mandatory=True, desc='Repetition Time')


class _ABCCQCOutputSpec(TraitedSpec):
    qc_file = File(exists=True, desc='ABCC QC HDF5 file.')


class ABCCQC(SimpleInterface):
    """Create an HDF5-format file containing a DCAN-format dataset.

    Notes
    -----
    The metrics in the file are:

    -   ``FD_threshold``: a number >= 0 that represents the FD threshold used to calculate
        the metrics in this list.
    -   ``frame_removal``: a binary vector/array the same length as the number of frames
        in the concatenated time series, indicates whether a frame is removed (1) or not (0)
    -   ``format_string`` (legacy): a string that denotes how the frames were excluded.
        This uses a notation devised by Avi Snyder.
    -   ``total_frame_count``: a whole number that represents the total number of frames
        in the concatenated series
    -   ``remaining_frame_count``: a whole number that represents the number of remaining
        frames in the concatenated series
    -   ``remaining_seconds``: a whole number that represents the amount of time remaining
        after thresholding
    -   ``remaining_frame_mean_FD``: a number >= 0 that represents the mean FD of the
        remaining frames
    """

    input_spec = _ABCCQCInputSpec
    output_spec = _ABCCQCOutputSpec

    def _run_interface(self, runtime):
        TR = self.inputs.TR

        self._results['qc_file'] = fname_presuffix(
            self.inputs.motion_file,
            suffix='qc_bold.hdf5',
            newpath=runtime.cwd,
            use_ext=False,
        )

        # Load filtered framewise_displacement values from file
        motion_df = pd.read_table(self.inputs.motion_file)
        if 'framewise_displacement_filtered' in motion_df.columns:
            fd = motion_df['framewise_displacement_filtered'].values
        else:
            fd = motion_df['framewise_displacement'].values

        with h5py.File(self._results['qc_file'], 'w') as dcan:
            for thresh in np.linspace(0, 1, 101):
                thresh = np.around(thresh, 2)

                dcan.create_dataset(
                    f'/dcan_motion/fd_{thresh}/skip',
                    data=0,
                    dtype='float',
                )
                dcan.create_dataset(
                    f'/dcan_motion/fd_{thresh}/binary_mask',
                    data=(fd > thresh).astype(int),
                    dtype='float',
                )
                dcan.create_dataset(
                    f'/dcan_motion/fd_{thresh}/threshold',
                    data=thresh,
                    dtype='float',
                )
                dcan.create_dataset(
                    f'/dcan_motion/fd_{thresh}/total_frame_count',
                    data=len(fd),
                    dtype='float',
                )
                dcan.create_dataset(
                    f'/dcan_motion/fd_{thresh}/remaining_total_frame_count',
                    data=len(fd[fd <= thresh]),
                    dtype='float',
                )
                dcan.create_dataset(
                    f'/dcan_motion/fd_{thresh}/remaining_seconds',
                    data=len(fd[fd <= thresh]) * TR,
                    dtype='float',
                )
                dcan.create_dataset(
                    f'/dcan_motion/fd_{thresh}/remaining_frame_mean_FD',
                    data=(fd[fd <= thresh]).mean(),
                    dtype='float',
                )

        return runtime
