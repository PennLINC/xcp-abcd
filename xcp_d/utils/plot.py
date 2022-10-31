# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""Plotting tools."""
import tempfile

import matplotlib.cm as cm
import matplotlib.pyplot as plt
import nibabel as nb
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import gridspec as mgs
from matplotlib.colors import ListedColormap
from nilearn._utils import check_niimg_4d
from nilearn._utils.niimg import _safe_get_data
from nilearn.signal import clean

from xcp_d.utils.qcmetrics import compute_dvars
from xcp_d.utils.write_save import read_ndata, write_ndata


def _decimate_data(data, seg_data, size):
    """Decimate timeseries data.

    Parameters
    ----------
    data : ndarray
        2 element array of timepoints and samples
    seg_data : ndarray
        1 element array of samples
    size : tuple
        2 element for P/T decimation
    """
    p_dec = 1 + data.shape[0] // size[0]
    if p_dec:
        data = data[::p_dec, :]
        seg_data = seg_data[::p_dec]
    t_dec = 1 + data.shape[1] // size[1]
    if t_dec:
        data = data[:, ::t_dec]
    return data, seg_data


def plotimage(img, out_file):
    """Plot anatomical image and save to file."""
    from nilearn.plotting import plot_anat

    fig = plt.figure(constrained_layout=False, figsize=(25, 10))
    plot_anat(img, draw_cross=False, figure=fig)
    fig.savefig(out_file, bbox_inches="tight", pad_inches=None)
    return out_file


def confoundplot(time_series,
                 grid_spec_ts,
                 gs_dist=None,
                 name=None,
                 units=None,
                 TR=None,
                 hide_x=True,
                 color='b',
                 cutoff=None,
                 ylims=None):
    """Create a time series plot for confounds.

    Adapted from niworkflows.

    Parameters
    ----------
    time_series : numpy.ndarray
       Time series to plot in the figure.
    grid_spec_ts : GridSpec
       The GridSpec object in which the time series plot will be stored.
    name :
      file name
    units :
      time_series unit
    TR : float or None, optional
      Repetition time for the time series. Default is None.

    Returns
    -------
    time_series_axis
    grid_specification
    """
    sns.set_style('whitegrid')
    # Define TR and number of frames
    no_repetition_time = False
    if TR is None:  # Set default Repetition Time
        no_repetition_time = True
        TR = 1.
    ntsteps = len(time_series)
    time_series = np.array(time_series)

    # Define nested GridSpec
    grid_specification = mgs.GridSpecFromSubplotSpec(1,
                                                     2,
                                                     subplot_spec=grid_spec_ts,
                                                     width_ratios=[1, 100],
                                                     wspace=0.0)

    time_series_axis = plt.subplot(grid_specification[1])
    time_series_axis.grid(False)

    # Set 10 frame markers in X axis
    interval = max((ntsteps // 10, ntsteps // 5, 1))
    xticks = list(range(0, ntsteps)[::interval])
    time_series_axis.set_xticks(xticks)

    # Set x_axis
    if not hide_x:
        if no_repetition_time:
            time_series_axis.set_xlabel('time (frame #)')
        else:
            time_series_axis.set_xlabel('time (s)')
            labels = TR * np.array(xticks)
            time_series_axis.set_xticklabels([f'{t:.02f}' for t in labels.tolist()])
    else:
        time_series_axis.set_xticklabels([])

    if name is not None:
        if units is not None:
            name += f' [{units}]'
    #   Formatting
        time_series_axis.annotate(name,
                                  xy=(0.0, 0.7),
                                  xytext=(0, 0),
                                  xycoords='axes fraction',
                                  textcoords='offset points',
                                  va='center',
                                  ha='left',
                                  color=color,
                                  size=16,
                                  bbox={
                                      'boxstyle': 'round',
                                      'fc': 'w',
                                      'ec': 'none',
                                      'color': 'none',
                                      'lw': 0,
                                      'alpha': 0.8
                                  })
    for side in ["top", "right"]:
        time_series_axis.spines[side].set_color('none')
        time_series_axis.spines[side].set_visible(False)

    if not hide_x:
        time_series_axis.spines["bottom"].set_position(('outward', 20))
        time_series_axis.xaxis.set_ticks_position('bottom')
    else:
        time_series_axis.spines["bottom"].set_color('none')
        time_series_axis.spines["bottom"].set_visible(False)

    time_series_axis.spines["left"].set_color('none')
    time_series_axis.spines["left"].set_visible(False)
    time_series_axis.set_yticks([])
    time_series_axis.set_yticklabels([])

    nonnan = time_series[~np.isnan(time_series)]
    if nonnan.size > 0:
        # Calculate Y limits
        valrange = (nonnan.max() - nonnan.min())
        def_ylims = [
            nonnan.min() - 0.1 * valrange,
            nonnan.max() + 0.1 * valrange
        ]
        if ylims is not None:
            if ylims[0] is not None:
                def_ylims[0] = min([def_ylims[0], ylims[0]])
            if ylims[1] is not None:
                def_ylims[1] = max([def_ylims[1], ylims[1]])

        # Add space for plot title and mean/SD annotation
        def_ylims[0] -= 0.1 * (def_ylims[1] - def_ylims[0])

        time_series_axis.set_ylim(def_ylims)

        # Annotate stats
        maxv = nonnan.max()
        mean = nonnan.mean()
        stdv = nonnan.std()
        p95 = np.percentile(nonnan, 95.0)
    else:
        maxv = 0
        mean = 0
        stdv = 0
        p95 = 0

    stats_label = (r'max: {max:.3f}{units} $\bullet$ mean: {mean:.3f}{units} '
                   r'$\bullet$ $\sigma$: {sigma:.3f}').format(max=maxv,
                                                              mean=mean,
                                                              units=units or '', sigma=stdv)
    time_series_axis.annotate(stats_label,
                              xy=(0.98, 0.7),
                              xycoords='axes fraction',
                              xytext=(0, 0),
                              textcoords='offset points',
                              va='center',
                              ha='right',
                              color=color,
                              size=14,
                              bbox={
                                  'boxstyle': 'round',
                                  'fc': 'w',
                                  'ec': 'none',
                                  'color': 'none',
                                  'lw': 0,
                                  'alpha': 0.8
                              })

    # Annotate percentile 95
    time_series_axis.plot((0, ntsteps - 1), [p95] * 2, linewidth=.1, color='lightgray')
    time_series_axis.annotate(f'{p95:.2f}',
                              xy=(0, p95),
                              xytext=(-1, 0),
                              textcoords='offset points',
                              va='center',
                              ha='right',
                              color='lightgray',
                              size=3)

    if cutoff is None:
        cutoff = []

    for threshold in enumerate(cutoff):
        time_series_axis.plot((0, ntsteps - 1), [threshold] * 2, linewidth=.2, color='dimgray')

        time_series_axis.annotate(f'{threshold:.2f}',
                                  xy=(0, threshold),
                                  xytext=(-1, 0),
                                  textcoords='offset points',
                                  va='center',
                                  ha='right',
                                  color='dimgray',
                                  size=3)

    time_series_axis.plot(time_series, color=color, linewidth=2.5)
    time_series_axis.set_xlim((0, ntsteps - 1))
    # Plotting
    if gs_dist is not None:
        ax_dist = plt.subplot(gs_dist)
        sns.distplot(time_series, vertical=True, ax=ax_dist)
        ax_dist.set_xlabel('Timesteps')
        ax_dist.set_ylim(time_series_axis.get_ylim())
        ax_dist.set_yticklabels([])

        return [time_series_axis, ax_dist], grid_specification
    return time_series_axis, grid_specification


def confoundplotx(time_series,
                  grid_spec_ts,
                  TR=None,
                  hide_x=True,
                  ylims=None,
                  ylabel=None,
                  FD=False,
                  work_dir=None):
    """Create confounds plot."""
    sns.set_style('whitegrid')

    # Define TR and number of frames
    no_repetition_time = False
    if TR is None:
        no_repetition_time = True
        TR = 1.0

    ntsteps = time_series.shape[0]
    # time_series = np.array(time_series)

    # Define nested GridSpec
    grid_specification = mgs.GridSpecFromSubplotSpec(1,
                                                     2,
                                                     subplot_spec=grid_spec_ts,
                                                     width_ratios=[1, 100],
                                                     wspace=0.0)

    time_series_axis = plt.subplot(grid_specification[1])
    time_series_axis.grid(False)

    # Set 10 frame markers in X axis
    interval = max((ntsteps // 10, ntsteps // 5, 1))
    xticks = list(range(0, ntsteps)[::interval])
    time_series_axis.set_xticks(xticks)

    # Set the x-axis labels
    if not hide_x:
        if no_repetition_time:
            time_series_axis.set_xlabel("Time (frame #)")
        else:
            time_series_axis.set_xlabel("Time (s)")
            labels = TR * np.array(xticks)
            labels = labels.astype(int)
            time_series_axis.set_xticklabels(labels)
    else:
        time_series_axis.set_xticklabels([])

    # Set y-axis labels
    if ylabel:
        time_series_axis.set_ylabel(ylabel)
    if work_dir is not None:
        time_series.to_csv(f'/{work_dir}/{ylabel}_tseries.npy')
    columns = time_series.columns
    maximum_value = []
    minimum_value = []

    if FD is True:
        for c in columns:
            time_series_axis.plot(time_series[c], label=c, linewidth=3, color='black')
            maximum_value.append(max(time_series[c]))
            minimum_value.append(min(time_series[c]))

            # Threshold fd at 0.1, 0.2 and 0.5 and plot
            time_series_axis.axhline(y=1, color='lightgray',
                                     linestyle='-', linewidth=10, alpha=0.5)
            fda = time_series[c].copy()
            FD_timeseries = time_series[c].copy()
            FD_timeseries[FD_timeseries > 0] = 1.05
            time_series_axis.plot(fda, '.', color='gray', markersize=40)
            time_series_axis.plot(FD_timeseries, '.', color='gray', markersize=40)

            time_series_axis.axhline(y=0.05, color='gray', linestyle='-', linewidth=10, alpha=0.5)
            fda[fda < 0.05] = np.nan
            FD_timeseries = time_series[c].copy()
            FD_timeseries[FD_timeseries >= 0.05] = 1.05
            FD_timeseries[FD_timeseries < 0.05] = np.nan
            time_series_axis.plot(fda, '.', color='gray', markersize=40)
            time_series_axis.plot(FD_timeseries, '.', color='gray', markersize=40)

            time_series_axis.axhline(y=0.1, color='#66c2a5',
                                     linestyle='-', linewidth=10, alpha=0.5)
            fda[fda < 0.1] = np.nan
            FD_timeseries = time_series[c].copy()
            FD_timeseries[FD_timeseries >= 0.1] = 1.05
            FD_timeseries[FD_timeseries < 0.1] = np.nan
            time_series_axis.plot(fda, '.', color='#66c2a5', markersize=40)
            time_series_axis.plot(FD_timeseries, '.', color='#66c2a5', markersize=40)

            time_series_axis.axhline(y=0.2, color='#fc8d62',
                                     linestyle='-', linewidth=10, alpha=0.5)
            fda[fda < 0.2] = np.nan
            FD_timeseries = time_series[c].copy()
            FD_timeseries[FD_timeseries >= 0.2] = 1.05
            FD_timeseries[FD_timeseries < 0.2] = np.nan
            time_series_axis.plot(fda, '.', color='#fc8d62', markersize=40)
            time_series_axis.plot(FD_timeseries, '.', color='#fc8d62', markersize=40)

            time_series_axis.axhline(y=0.5, color='#8da0cb',
                                     linestyle='-', linewidth=10, alpha=0.5)
            fda[fda < 0.5] = np.nan
            FD_timeseries = time_series[c].copy()
            FD_timeseries[FD_timeseries >= 0.5] = 1.05
            FD_timeseries[FD_timeseries < 0.5] = np.nan
            time_series_axis.plot(fda, '.', color='#8da0cb', markersize=40)
            time_series_axis.plot(FD_timeseries, '.', color='#8da0cb', markersize=40)

            #  Plot the good volumes, i.e: thresholded at 0.1, 0.2, 0.5
            good_vols = len(time_series[c][time_series[c] < 0.1])
            time_series_axis.text(1.01,
                                  .1,
                                  good_vols,
                                  c='#66c2a5',
                                  verticalalignment='top',
                                  horizontalalignment='left',
                                  transform=time_series_axis.transAxes,
                                  fontsize=30)
            good_vols = len(time_series[c][time_series[c] < 0.2])
            time_series_axis.text(1.01,
                                  .2,
                                  good_vols,
                                  c='#fc8d62',
                                  verticalalignment='top',
                                  horizontalalignment='left',
                                  transform=time_series_axis.transAxes,
                                  fontsize=30)
            good_vols = len(time_series[c][time_series[c] < 0.5])
            time_series_axis.text(1.01,
                                  .5,
                                  good_vols,
                                  c='#8da0cb',
                                  verticalalignment='top',
                                  horizontalalignment='left',
                                  transform=time_series_axis.transAxes,
                                  fontsize=30)
            good_vols = len(time_series[c][time_series[c] < 0.05])
            time_series_axis.text(1.01,
                                  .05,
                                  good_vols,
                                  c='grey',
                                  verticalalignment='top',
                                  horizontalalignment='left',
                                  transform=time_series_axis.transAxes,
                                  fontsize=30)
    else:  # If no thresholding
        for c in columns:
            time_series_axis.plot(time_series[c], label=c, linewidth=10, alpha=0.5)
            maximum_value.append(max(time_series[c]))
            minimum_value.append(min(time_series[c]))

    # Set limits and format
    minimum_x_value = [abs(x) for x in minimum_value]

    time_series_axis.set_xlim((0, ntsteps - 1))
    time_series_axis.legend(fontsize=40)
    if FD is True:
        time_series_axis.set_ylim(0, 1.1)
        time_series_axis.set_yticks([0, 0.05, .1, 0.2, .5, 1])
    elif ylims:
        time_series_axis.set_ylim(ylims)
    else:
        time_series_axis.set_ylim([-1.5 * max(minimum_x_value), 1.5 * max(maximum_value)])

    for item in ([time_series_axis.title, time_series_axis.xaxis.label,
                  time_series_axis.yaxis.label]
                 + time_series_axis.get_xticklabels() + time_series_axis.get_yticklabels()):
        item.set_fontsize(30)

    for axis in ['top', 'bottom', 'left', 'right']:
        time_series_axis.spines[axis].set_linewidth(4)
    sns.despine()
    return time_series_axis, grid_specification


def plot_svgx(rawdata,
              regressed_data,
              residual_data,
              tmask,
              dummyvols,
              filtered_motion,
              unprocessed_filename,
              processed_filename,
              mask=None,
              seg_data=None,
              TR=1,
              raw_dvars=None,
              regressed_dvars=None,
              filtered_dvars=None,
              work_dir=None):
    """Generate carpet plot with DVARS, FD, and WB.

    Parameters
    ----------
    rawdata :
        nifti or cifti before processing
    regressed_data :
        nifti or cifti after nuisance regression
    residual_data :
        nifti or cifti after regression and filtering
    mask :
        mask for nifti if available
    tmask :
       temporal censoring mask
    dummyvols :
        initial number of volumes to drop
    seg_data :
        3 tissues seg_data files
    TR : float, optional
        repetition times
    filtered_motion :
       Filtered motion parameters, including framewise displacement, in a TSV file.
    unprocessed_filename :
        output file svg before processing
    processed_filename :
        output file svg after processing
    """
    # Compute dvars correctly if not already done
    residual_data_file = residual_data
    raw_data_file = rawdata
    raw_data = read_ndata(datafile=rawdata, maskfile=mask)
    regressed_data = read_ndata(datafile=regressed_data, maskfile=mask)
    filtered_data = read_ndata(datafile=residual_data, maskfile=mask)
    tmask_df = pd.read_table(tmask)
    tmask_arr = tmask_df["framewise_displacement"].values
    tmask_bool = ~tmask_arr.astype(bool)
    # Let's remove dummy time from the raw_data if needed
    if dummyvols > 1:
        raw_data = raw_data[dummyvols:]
    # Let's censor the interpolated data and raw_data:
    if sum(tmask_arr) > 0:
        raw_data = raw_data[:, tmask_bool]
        filtered_data = filtered_data[:, tmask_bool]

    if type(raw_dvars) != np.ndarray:
        raw_dvars = compute_dvars(raw_data)
    if type(regressed_dvars) != np.ndarray:
        regressed_dvars = compute_dvars(regressed_data)
    if type(filtered_dvars) != np.ndarray:
        filtered_dvars = compute_dvars(filtered_data)
    # For ease of reference later

    # Formatting & setting of files
    sns.set_style('whitegrid')
    regressed_dvars_data = regressed_dvars
    residual_dvars_data = filtered_dvars
    raw_dvars_data = raw_dvars
    # Load files
    raw_data = read_ndata(datafile=raw_data_file, maskfile=mask)
    residual_data = read_ndata(datafile=residual_data_file, maskfile=mask)

    # Remove first N deleted from raw_data so it's same length as censored files
    if len(raw_dvars_data) > len(residual_dvars_data):
        # TODO: Should this be [-len(residual_dvars_data):] ?
        # ... Seems to grab first N, not last N.
        raw_dvars_data = raw_dvars_data[0:len(residual_dvars_data)]
        raw_data = raw_data[:, 0:len(residual_dvars_data)]
        # TODO: Figure out how to slice the regressed DVARS instead of just overwriting it
        regressed_dvars_data = raw_dvars_data

    # Create dataframes for the bold_data DVARS, FD
    DVARS_timeseries = pd.DataFrame({
        'Pre regression': raw_dvars_data,
        'Post regression': regressed_dvars_data,
        'Post all': residual_dvars_data
    })

    FD_timeseries = pd.DataFrame({
        'FD': pd.read_table(filtered_motion)["framewise_displacement"].values,
    })

    # The mean and standard deviation of raw data
    unprocessed_data_timeseries = pd.DataFrame({
        'Mean': np.nanmean(raw_data, axis=0),
        'Std': np.nanstd(raw_data, axis=0)
    })
    # The mean and standard deviation of filtered data
    processed_data_timeseries = pd.DataFrame({
        'Mean': np.nanmean(residual_data, axis=0),
        'Std': np.nanstd(residual_data, axis=0)
    })
    if seg_data is not None:
        atlaslabels = nb.load(seg_data).get_fdata()
    else:
        atlaslabels = None

    # The plot going to carpet plot will be rescaled to [-600,600]
    scaled_raw_data = read_ndata(datafile=raw_data_file, maskfile=mask, scale=600)
    scaled_residual_data = read_ndata(datafile=residual_data_file, maskfile=mask, scale=600)

    # Make a temporary file for niftis and ciftis
    if rawdata.endswith('.nii.gz'):
        scaledrawdata = tempfile.mkdtemp() + '/filex_raw.nii.gz'
        scaledresdata = tempfile.mkdtemp() + '/filex_red.nii.gz'
    else:
        scaledrawdata = tempfile.mkdtemp() + '/filex_raw.dtseries.nii'
        scaledresdata = tempfile.mkdtemp() + '/filex_red.dtseries.nii'

    # Write out the scaled data
    scaledrawdata = write_ndata(data_matrix=scaled_raw_data,
                                template=raw_data_file,
                                filename=scaledrawdata,
                                mask=mask,
                                TR=TR)
    scaledresdata = write_ndata(data_matrix=scaled_residual_data,
                                template=residual_data_file,
                                filename=scaledresdata,
                                mask=mask,
                                TR=TR)
    # Plot the data and confounds, plus the carpet plot
    plt.cla()
    plt.clf()
    unprocessed_figure = plt.figure(constrained_layout=True, figsize=(45, 60))
    grid = mgs.GridSpec(5,
                        1,
                        wspace=0.0,
                        hspace=0.05,
                        height_ratios=[1, 1, 0.2, 2.5, 1])
    confoundplotx(time_series=DVARS_timeseries,
                  grid_spec_ts=grid[0],
                  TR=TR,
                  ylabel='DVARS',
                  hide_x=True)
    confoundplotx(time_series=unprocessed_data_timeseries,
                  grid_spec_ts=grid[1], TR=TR, hide_x=True, ylabel='WB')
    plot_carpet(func=scaledrawdata,
                atlaslabels=atlaslabels,
                TR=TR,
                subplot=grid[3],
                legend=False)
    confoundplotx(time_series=FD_timeseries,
                  grid_spec_ts=grid[4],
                  TR=TR,
                  hide_x=False,
                  ylims=[0, 1],
                  ylabel='FD[mm]',
                  FD=True)
    # Save out the before processing file
    unprocessed_figure.savefig(unprocessed_filename, bbox_inches="tight", pad_inches=None, dpi=300)

    plt.cla()
    plt.clf()

    # Plot the data and confounds, plus the carpet plot
    processed_figure = plt.figure(constrained_layout=True, figsize=(45, 60))
    grid = mgs.GridSpec(5,
                        1,
                        wspace=0.0,
                        hspace=0.05,
                        height_ratios=[1, 1, 0.2, 2.5, 1])

    confoundplotx(time_series=DVARS_timeseries,
                  grid_spec_ts=grid[0],
                  TR=TR,
                  ylabel='DVARS',
                  hide_x=True,
                  work_dir=work_dir)
    confoundplotx(time_series=processed_data_timeseries,
                  grid_spec_ts=grid[1],
                  TR=TR,
                  hide_x=True,
                  ylabel='WB',
                  work_dir=work_dir)

    plot_carpet(func=scaledresdata,
                atlaslabels=atlaslabels,
                TR=TR,
                subplot=grid[3],
                legend=True)
    confoundplotx(time_series=FD_timeseries,
                  grid_spec_ts=grid[4],
                  TR=TR,
                  hide_x=False,
                  ylims=[0, 1],
                  ylabel='FD[mm]',
                  FD=True,
                  work_dir=work_dir)
    processed_figure.savefig(processed_filename, bbox_inches="tight", pad_inches=None, dpi=300)
    # Save out the after processing file
    return unprocessed_filename, processed_filename


class FMRIPlot:
    """Generates the fMRI Summary Plot."""

    __slots__ = ("func_file", "mask_data", "TR", "seg_data", "confounds",
                 "spikes")

    def __init__(
        self,
        func_file,
        mask_file=None,
        data=None,
        confound_file=None,
        seg_file=None,
        TR=None,
        usecols=None,
        units=None,
        vlines=None,
        spikes_files=None,
    ):
        #  Load in the necessary information
        func_img = nb.load(func_file)
        self.func_file = func_file
        self.TR = TR or _get_tr(func_img)
        self.mask_data = None
        self.seg_data = None
        sns.set_style("whitegrid")

        if not isinstance(func_img, nb.Cifti2Image):  # If Nifti
            self.mask_data = nb.fileslice.strided_scalar(
                func_img.shape[:3], np.uint8(1))
            if mask_file:
                self.mask_data = np.asanyarray(
                    nb.load(mask_file).dataobj).astype("uint8")
            if seg_file:
                self.seg_data = np.asanyarray(nb.load(seg_file).dataobj)

        if units is None:
            units = {}
        if vlines is None:
            vlines = {}
        self.confounds = {}
        if data is None and confound_file:
            data = pd.read_csv(confound_file,
                               sep=r"[\t\s]+",
                               usecols=usecols,
                               index_col=False)
        # Confounds information
        if data is not None:
            for name in data.columns.ravel():
                self.confounds[name] = {
                    "values": data[[name]].values.ravel().tolist(),
                    "units": units.get(name),
                    "cutoff": vlines.get(name),
                }
        #  Spike information
        self.spikes = []
        if spikes_files:
            for sp_file in spikes_files:
                self.spikes.append((np.loadtxt(sp_file), None, False))

    def plot(self, labelsize, figure=None):
        """Perform main plotting step."""
        # Layout settings
        sns.set_style("whitegrid")
        sns.set_context("paper", font_scale=1)

        if figure is None:
            figure = plt.gcf()

        n_confounds = len(self.confounds)
        n_spikes = len(self.spikes)
        n_rows = 1 + n_confounds + n_spikes

        # Create grid specification
        grid = mgs.GridSpec(n_rows,
                            1,
                            wspace=0.0,
                            hspace=0.05,
                            height_ratios=[1] * (n_rows - 1) + [5])

        grid_id = 0
        for _, name, _ in self.spikes:
            # RF: What is this?
            # spikesplot(tsz,
            #            title=name,
            #            outer_gs=grid[grid_id],
            #            TR=self.TR,
            #            zscored=iszs)
            grid_id += 1

        # Plot confounds
        if self.confounds:
            from seaborn import color_palette

            palette = color_palette("husl", n_confounds)

        for i, (name, kwargs) in enumerate(self.confounds.items()):
            time_series = kwargs.pop("values")
            confoundplot(time_series,
                         grid[grid_id],
                         TR=self.TR,
                         color=palette[i],
                         name=name,
                         **kwargs)
            grid_id += 1

        # Carpet plot
        plot_carpet(self.func_file,
                    atlaslabels=self.seg_data,
                    subplot=grid[-1],
                    TR=self.TR,
                    labelsize=labelsize)
        # spikesplot_cb([0.7, 0.78, 0.2, 0.008])
        return figure


def plot_carpet(
    func,
    atlaslabels=None,
    size=(950, 800),
    labelsize=30,
    subplot=None,
    output_file=None,
    legend=True,
    TR=None,
    lut=None,
):
    """Plot an image representation of voxel intensities across time.

    This is also known as the "carpet plot" or "Power plot".
    See Jonathan Power Neuroimage 2017 Jul 1; 154:150-158.

    Parameters
    ----------
    func : str
        Path to NIfTI or CIFTI BOLD image
    atlaslabels : numpy.ndarray, optional
        A 3D array of integer labels from an atlas, resampled into ``img`` space.
        Required if ``func`` is a NIfTI image.
    detrend : bool, optional
        Detrend and standardize the data prior to plotting.
    size : tuple, optional
        Size of figure.
    subplot : matplotlib Subplot, optional
        Subplot to plot figure on.
    title : str, optional
        The title displayed on the figure.
    output_file : str or None, optional
        The name of an image file to export the plot to. Valid extensions
        are .png, .pdf, .svg. If output_file is not None, the plot
        is saved to a file, and the display is closed.
    legend : bool
        Whether to render the average functional series with ``atlaslabels`` as
        overlay.
    TR : float, optional
        Specify the TR, if specified it uses this value. If left as None,
        # of frames is plotted instead of time.
    lut : numpy.ndarray, optional
        Look up table for segmentations
    """
    epinii = None
    segnii = None
    img = nb.load(func)
    sns.set_style("whitegrid")
    if isinstance(img, nb.Cifti2Image):  # Cifti
        assert (
            img.nifti_header.get_intent()[0] == "ConnDenseSeries"
        ), f"Not a dense timeseries: {img.nifti_header.get_intent()[0]}, {func}"

        # Get required information
        data = img.get_fdata().T
        matrix = img.header.matrix
        struct_map = {
            "LEFT_CORTEX": 1,
            "RIGHT_CORTEX": 2,
            "SUBCORTICAL": 3,
            "CEREBELLUM": 4,
        }
        seg_data = np.zeros((data.shape[0], ), dtype="uint32")
        # Get brain model information
        for brain_model in matrix.get_index_map(1).brain_models:
            if "CORTEX" in brain_model.brain_structure:
                lidx = (1, 2)["RIGHT" in brain_model.brain_structure]
            elif "CEREBELLUM" in brain_model.brain_structure:
                lidx = 4
            else:
                lidx = 3
            index_final = brain_model.index_offset + brain_model.index_count
            seg_data[brain_model.index_offset:index_final] = lidx
        assert len(seg_data[seg_data < 1]) == 0, "Unassigned labels"

        # Decimate data
        data, seg_data = _decimate_data(data, seg_data, size)
        # Preserve continuity
        order = seg_data.argsort(kind="stable")
        # Get color maps
        cmap = ListedColormap(
            [cm.get_cmap("Paired").colors[i] for i in (1, 0, 7, 3)])
        assert len(cmap.colors) == len(
            struct_map), "Mismatch between expected # of structures and colors"

        # ensure no legend for CIFTI
        legend = False

    else:  # Volumetric NIfTI
        img_nii = check_niimg_4d(
            img,
            dtype="auto",
        )  # Check the image is in nifti format
        func_data = _safe_get_data(img_nii, ensure_finite=True)
        ntsteps = func_data.shape[-1]
        data = func_data[atlaslabels > 0].reshape(-1, ntsteps)
        oseg = atlaslabels[atlaslabels > 0].reshape(-1)

        # Map segmentation
        if lut is None:
            lut = np.zeros((256, ), dtype="int")
            lut[1:11] = 1
            lut[255] = 2
            lut[30:99] = 3
            lut[100:201] = 4
        # Apply lookup table
        seg_data = lut[oseg.astype(int)]

        # Decimate data
        data, seg_data = _decimate_data(data, seg_data, size)
        # Order following segmentation labels
        order = np.argsort(seg_data)[::-1]
        # Set colormap
        cmap = ListedColormap(cm.get_cmap("tab10").colors[:4][::-1])

        if legend:
            epiavg = func_data.mean(3)
            epinii = nb.Nifti1Image(epiavg, img_nii.affine, img_nii.header)
            segnii = nb.Nifti1Image(lut[atlaslabels.astype(int)],
                                    epinii.affine, epinii.header)
            segnii.set_data_dtype("uint8")

    return _carpet(
        func,
        data,
        seg_data,
        order,
        cmap,
        labelsize,
        TR=TR,
        subplot=subplot,
        output_file=output_file,
    )


def _carpet(func,
            data,
            seg_data,
            order,
            cmap,
            labelsize,
            TR=None,
            detrend=True,
            subplot=None,
            legend=False,
            output_file=None):
    """Build carpetplot for volumetric / CIFTI plots."""
    if TR is None:
        TR = 1.0  # Default TR
    sns.set_style("whitegrid")
    # Detrend data
    v = (None, None)
    if detrend:
        data = clean(data.T, t_r=TR).T
        v = (-2, 2)

    # If subplot is not defined
    if subplot is None:
        subplot = mgs.GridSpec(1, 1)[0]

    # Define nested GridSpec
    wratios = [1, 100, 20]
    grid_specification = mgs.GridSpecFromSubplotSpec(
        1,
        2 + int(legend),
        subplot_spec=subplot,
        width_ratios=wratios[:2 + int(legend)],
        wspace=0.0,
    )

    # Segmentation colorbar
    ax0 = plt.subplot(grid_specification[0])
    ax0.set_xticks([])
    ax0.imshow(seg_data[order, np.newaxis],
               interpolation="none",
               aspect="auto",
               cmap=cmap)

    if func.endswith('nii.gz'):  # Nifti
        labels = ['Cortical GM', 'Subcortical GM', 'Cerebellum', 'CSF and WM']
    else:  # Cifti
        labels = ['Left Cortex', 'Right Cortex', 'Subcortical', 'Cerebellum']

    # Formatting the plot
    tick_locs = []
    for y in np.unique(seg_data[order]):
        tick_locs.append(np.argwhere(seg_data[order] == y).mean())

    ax0.set_yticks(tick_locs)
    ax0.set_yticklabels(labels,
                        fontdict={'fontsize': labelsize},
                        rotation=0,
                        va='center')
    ax0.grid(False)
    ax0.spines["left"].set_visible(False)
    ax0.spines["bottom"].set_color("none")
    ax0.spines["bottom"].set_visible(False)
    ax0.set_xticks([])
    ax0.set_xticklabels([])

    # Carpet plot
    ax1 = plt.subplot(grid_specification[1])
    ax1.imshow(
        data[order],
        interpolation="nearest",
        aspect="auto",
        cmap="gray",
        vmin=v[0],
        vmax=v[1],
    )

    ax1.grid(False)
    ax1.set_yticks([])
    ax1.set_yticklabels([])
    ax1.set_xticks([])
    ax1.set_xticklabels([])

    # Remove and redefine spines
    for side in ["top", "right"]:
        # Toggle the spine objects
        ax0.spines[side].set_color("none")
        ax0.spines[side].set_visible(False)
        ax1.spines[side].set_color("none")
        ax1.spines[side].set_visible(False)

    ax1.yaxis.set_ticks_position("left")
    ax1.xaxis.set_ticks_position("bottom")
    ax1.spines["bottom"].set_visible(False)
    ax1.spines["left"].set_color("none")
    ax1.spines["left"].set_visible(False)

    ax2 = None
    #  Write out file
    if output_file is not None:
        figure = plt.gcf()
        figure.savefig(output_file, bbox_inches="tight")
        plt.close(figure)
        figure = None
        return output_file

    return (ax0, ax1, ax2), grid_specification


def _get_tr(img):
    """Attempt to extract repetition time from NIfTI/CIFTI header.

    Examples
    --------
    _get_tr(nb.load(Path(test_data) /
    ...    'sub-ds205s03_task-functionallocalizer_run-01_bold_volreg.nii.gz'))
    2.2
     _get_tr(nb.load(Path(test_data) /
    ...    'sub-01_task-mixedgamblestask_run-02_space-fsLR_den-91k_bold.dtseries.nii'))
    2.0
    """
    if isinstance(img, str):
        img = nb.load(img)

    try:
        return img.header.matrix.get_index_map(0).series_step  # Get TR
    except AttributeError:  # Error out if not in cifti
        return img.header.get_zooms()[-1]
    raise RuntimeError("Could not extract TR - unknown data structure type")


def plot_alff_reho_volumetric(output_path, filename, bold_file):
    """Plot ALFF/ReHo mosaic plot for Niftis."""
    from bids.layout import parse_file_entities
    from nilearn import plotting as plott
    from templateflow.api import get as get_template

    space = str(parse_file_entities(bold_file)["space"])
    cohort = None
    if "infant" in space:
        cohort = str(parse_file_entities(bold_file)["cohort"])
    try:
        resolution = str(parse_file_entities(bold_file)["res"])
    except Exception:
        resolution = 1

    template = str(
        get_template(template=space, resolution=resolution, desc=None, cohort=cohort, suffix="T1w")
    )
    plott.plot_stat_map(filename,
                        bg_img=template,
                        display_mode='z',
                        cut_coords=8,
                        output_file=output_path)
    output_pathname = output_path
    return output_pathname


def surf_data_from_cifti(data, axis, surf_name):
    """From https://neurostars.org/t/separate-cifti-by-structure-in-python/17301/2.

    https://nbviewer.org/github/neurohackademy/nh2020-curriculum/blob/master/we-nibabel-markiewicz/NiBabel.ipynb
    """
    assert isinstance(axis, nb.cifti2.BrainModelAxis)
    for name, data_indices, model in axis.iter_structures():
        # Iterates over volumetric and surface structures
        if name == surf_name:  # Just looking for a surface
            data = data.T[data_indices]
            # Assume brainmodels axis is last, move it to front
            vtx_indices = model.vertex
            # Generally 1-N, except medial wall vertices
            surf_data = np.zeros((vtx_indices.max() + 1,) + data.shape[1:], dtype=data.dtype)
            surf_data[vtx_indices] = data
            return surf_data

    raise ValueError(f"No structure named {surf_name}")


def plot_alff_reho_surface(output_path, filename, bold_file):
    """Plot ReHo and ALFF for ciftis on surface."""
    import matplotlib.pyplot as plt
    import nibabel as nb
    from bids.layout import parse_file_entities
    from nilearn import plotting as plott
    from templateflow.api import get as get_template

    from xcp_d.utils.plot import surf_data_from_cifti

    func = filename
    try:
        density = str(parse_file_entities(bold_file)["den"])
    except Exception:
        density = "32k"

    rh = str(
        get_template(template="fsLR", hemi="L", density=density,
                     cohort=cohort, space=space, suffix="midthickness")
    )
    lh = str(
        get_template(template="fsLR", hemi="R", density=density, suffix="midthickness")
    )
    cifti = nb.load(func)
    cifti_data = cifti.get_fdata()
    cifti_axes = [cifti.header.get_axis(i) for i in range(cifti.ndim)]

    fig, axes = plt.subplots(figsize=(16, 16), ncols=2, nrows=2, subplot_kw={'projection': '3d'})

    lh_surf_data = surf_data_from_cifti(
        cifti_data,
        cifti_axes[1],
        'CIFTI_STRUCTURE_CORTEX_LEFT',
    )
    rh_surf_data = surf_data_from_cifti(
        cifti_data,
        cifti_axes[1],
        'CIFTI_STRUCTURE_CORTEX_RIGHT',
    )
    plott.plot_surf_stat_map(
        lh,
        lh_surf_data,
        hemi="left",
        view="lateral",
        engine="matplotlib",
        colorbar=False,
        axes=axes[0, 0],
        figure=fig,
    )
    plott.plot_surf_stat_map(
        lh,
        lh_surf_data,
        hemi="left",
        view="medial",
        engine="matplotlib",
        colorbar=False,
        axes=axes[1, 0],
        figure=fig,
    )
    plott.plot_surf_stat_map(
        rh,
        rh_surf_data,
        hemi="right",
        view="lateral",
        engine="matplotlib",
        colorbar=False,
        axes=axes[0, 1],
        figure=fig,
    )
    plott.plot_surf_stat_map(
        rh,
        rh_surf_data,
        hemi="right",
        view="medial",
        engine="matplotlib",
        colorbar=False,
        axes=axes[1, 1],
        figure=fig,
    )
    axes[0, 0].set_title("Left Hemisphere", fontsize=40)
    axes[0, 1].set_title("Right Hemisphere", fontsize=40)
    fig.tight_layout()
    fig.savefig(output_path)
    output_pathname = output_path
    return output_pathname
