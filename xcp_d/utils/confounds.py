# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""confound matrix selection based on Ciric et al 2007."""
import numpy as np
import pandas as pd
import os
from scipy.signal import firwin, iirnotch, filtfilt


def get_confounds_tsv(datafile):
    """Find path to confounds.tsv """
    '''
    datafile:
        real nifti or cifti file
    confounds_timeseries:
        confound tsv file
    '''
    if 'space' in os.path.basename(datafile):
        confounds_timeseries = datafile.replace("_space-" + datafile.split("space-")[1],
                                                "_desc-confounds_timeseries.tsv")
    else:
        confounds_timeseries = datafile.split(
            '_desc-preproc_bold.nii.gz')[0]+"_desc-confounds_timeseries.tsv"

    return confounds_timeseries


def load_confound(datafile):
    """`Load confound amd json."""
    '''
    datafile:
        real nifti or cifti file
    confoundpd:
        confound data frame
    confoundjs:
        confound json file
    '''
    if 'space' in os.path.basename(datafile):
        confounds_timeseries = datafile.replace(
            "_space-" + datafile.split("space-")[1],
            "_desc-confounds_timeseries.tsv")
        confounds_json = datafile.replace(
            "_space-" + datafile.split("space-")[1],
            "_desc-confounds_timeseries.json")
    else:
        confounds_timeseries = datafile.split(
            '_desc-preproc_bold.nii.gz')[0] + "_desc-confounds_timeseries.tsv"
        confounds_json = datafile.split(
            '_desc-preproc_bold.nii.gz')[0] + "_desc-confounds_timeseries.json"

    confoundpd = pd.read_csv(confounds_timeseries,
                             delimiter="\t",
                             encoding="utf-8")

    confoundjs = readjson(confounds_json)

    return confoundpd, confoundjs


def readjson(jsonfile):
    import json
    with open(jsonfile) as f:
        data = json.load(f)
    return data


def load_motion(confoundspd, TR, motion_filter_type, freqband, cutoff=0.1, motion_filter_order=4):
    """Load the 6 motion regressors."""
    rot_2mm = confoundspd[["rot_x", "rot_y", "rot_z"]]
    trans_mm = confoundspd[["trans_x", "trans_y", "trans_z"]]
    datay = pd.concat([rot_2mm, trans_mm], axis=1).to_numpy()

    if motion_filter_type == 'lp' or motion_filter_type == 'notch':
        datay = datay.T
        datay = motion_regression_filter(data=datay,
                                         TR=TR,
                                         motion_filter_type=motion_filter_type,
                                         freqband=freqband,
                                         cutoff=cutoff,
                                         motion_filter_order=motion_filter_order)
        datay = datay.T
    return pd.DataFrame(datay)


def load_globalS(confoundspd):
    """select global signal."""
    return confoundspd["global_signal"]


def load_WM_CSF(confoundspd):
    """select white matter and CSF nuissance."""
    return confoundspd[["csf", "white_matter"]]


def load_cosine(confoundspd):
    """select cosine for compcor"""
    cosine = []
    for key in confoundspd.keys():
        if 'cosine' in key:
            cosine.append(key)
    return confoundspd[cosine]


def load_acompcor(confoundspd, confoundjs):
    """ select WM and GM acompcor separately."""

    WM = []
    CSF = []
    for key, value in confoundjs.items():
        if 'comp_cor' in key and 't' not in key:
            if value['Mask'] == 'WM' and value['Retained']:
                WM.append([key, value['VarianceExplained']])
            if value['Mask'] == 'CSF' and value['Retained']:
                CSF.append([key, value['VarianceExplained']])
    # select the first five components
    csflist = []
    wmlist = []
    for i in range(0, 4):
        try:
            csflist.append(CSF[i][0])
        except Exception as exc:
            pass
            print(exc)
        try:
            wmlist.append(WM[i][0])
        except Exception as exc:
            pass
            print(exc)
    acompcor = wmlist + csflist
    return confoundspd[acompcor]


def load_tcompcor(confoundspd, confoundjs):
    """ select tcompcor."""

    tcomp = []
    for key, value in confoundjs.items():
        if 't_comp_cor' in key:
            if value['Method'] == 'tCompCor' and value['Retained']:
                tcomp.append([key, value['VarianceExplained']])
    # sort it by variance explained
    # select the first five components
    tcomplist = []
    for i in range(0, 6):
        tcomplist.append(tcomp[i][0])
    return confoundspd[tcomplist]


def derivative(confound):
    dat = confound.to_numpy()
    return pd.DataFrame(np.diff(dat, prepend=0))


def confpower(confound, order=2):
    return confound**order


def load_confound_matrix(datafile,
                         TR,
                         original_file,
                         motion_filter_type,
                         custom_confounds=None,
                         confound_tsv=None,
                         cutoff=0.1,
                         motion_filter_order=4,
                         freqband=[0.1, 0.2],
                         params='27P'):
    """ extract confound """
    '''
    original_file:
       file used to find confounds
    datafile:
        boldfile
    confound_tsv:
        confound tsv
    params:
       confound requested based on Ciric et. al 2017
    '''

    confoundjson = load_confound(original_file)[1]
    confoundtsv = pd.read_table(confound_tsv)

    if params == '24P':
        motion = load_motion(confoundtsv,
                             TR,
                             motion_filter_type,
                             freqband,
                             cutoff=cutoff,
                             motion_filter_order=motion_filter_order)
        mm_dev = pd.concat([motion, derivative(motion)], axis=1)
        confound = pd.concat([mm_dev, confpower(mm_dev)], axis=1)
    elif params == '27P':
        motion = load_motion(confoundtsv,
                             TR,
                             motion_filter_type,
                             freqband,
                             cutoff=cutoff,
                             motion_filter_order=motion_filter_order)
        mm_dev = pd.concat([motion, derivative(motion)], axis=1)
        wmcsf = load_WM_CSF(confoundtsv)
        gs = load_globalS(confoundtsv)
        confound = pd.concat([mm_dev, confpower(mm_dev), wmcsf, gs], axis=1)
    elif params == '36P':
        motion = load_motion(confoundtsv,
                             TR,
                             motion_filter_type,
                             freqband,
                             cutoff=cutoff,
                             motion_filter_order=motion_filter_order)
        mm_dev = pd.concat([motion, derivative(motion)], axis=1)
        conf24p = pd.concat([mm_dev, confpower(mm_dev)], axis=1)
        gswmcsf = pd.concat(
            [load_WM_CSF(confoundtsv),
             load_globalS(confoundtsv)], axis=1)
        gwcs_dev = pd.concat([gswmcsf, derivative(gswmcsf)], axis=1)
        confound = pd.concat([conf24p, gwcs_dev, confpower(gwcs_dev)], axis=1)
    elif params == 'acompcor':
        motion = load_motion(confoundtsv,
                             TR,
                             motion_filter_type,
                             freqband,
                             cutoff=cutoff,
                             motion_filter_order=motion_filter_order)
        mm_dev = pd.concat([motion, derivative(motion)], axis=1)
        acompc = load_acompcor(confoundspd=confoundtsv,
                               confoundjs=confoundjson)
        cosine = load_cosine(confoundtsv)
        confound = pd.concat([mm_dev, acompc, cosine], axis=1)
    elif params == 'aroma':
        wmcsf = load_WM_CSF(confoundtsv)
        aroma = load_aroma(datafile=datafile)
        confound = pd.concat([wmcsf, aroma], axis=1)
    elif params == 'aroma_gsr':
        wmcsf = load_WM_CSF(confoundtsv)
        aroma = load_aroma(datafile=datafile)
        gs = load_globalS(confoundtsv)
        confound = pd.concat([wmcsf, aroma, gs], axis=1)
    elif params == 'acompcor_gsr':
        motion = load_motion(confoundtsv,
                             TR,
                             motion_filter_type,
                             freqband,
                             cutoff=cutoff,
                             motion_filter_order=motion_filter_order)
        mm_dev = pd.concat([motion, derivative(motion)], axis=1)
        acompc = load_acompcor(confoundspd=confoundtsv,
                               confoundjs=confoundjson)
        gs = load_globalS(confoundtsv)
        cosine = load_cosine(confoundtsv)
        confound = pd.concat([mm_dev, acompc, gs, cosine], axis=1)
    elif params == 'custom':
        # for custom confounds with no other confounds
        confound = pd.read_csv(custom_confounds, sep='\t', header=None)

    if params != 'custom':
        if custom_confounds is not None:
            custom = pd.read_csv(custom_confounds, sep='\t', header=None)
            confound = pd.concat([confound, custom], axis=1)

    return confound


def load_aroma(datafile):
    """ extract aroma confound."""
    # _AROMAnoiseICs.csv
    # _desc-MELODIC_mixing.tsv

    if 'space' in os.path.basename(datafile):
        aroma_noise = datafile.replace("_space-" + datafile.split("space-")[1],
                                       "_AROMAnoiseICs.csv")
        melodic_ts = datafile.replace("_space-" + datafile.split("space-")[1],
                                      "_desc-MELODIC_mixing.tsv")
    else:
        aroma_noise = datafile.split(
            '_desc-preproc_bold.nii.gz')[0] + "_AROMAnoiseICs.csv"
        melodic_ts = datafile.split(
            '_desc-preproc_bold.nii.gz')[0] + "_desc-MELODIC_mixing.tsv"

    aroma_noise = np.genfromtxt(
        aroma_noise,
        delimiter=',',
    )
    aroma_noise = [np.int(i) - 1
                   for i in aroma_noise]  # change to 0-based index
    melodic = pd.read_csv(melodic_ts,
                          header=None,
                          delimiter="\t",
                          encoding="utf-8")
    aroma = melodic.drop(aroma_noise, axis=1)

    return aroma


def motion_regression_filter(data,
                             TR,
                             motion_filter_type,
                             freqband,
                             cutoff=.1,
                             motion_filter_order=4):
    """
    apply motion filter to 6 motion.
    """

    LP_freq_min = cutoff
    fc_RR_min, fc_RR_max = freqband

    TR = float(TR)
    order = float(order)
    LP_freq_min = float(LP_freq_min)
    fc_RR_min = float(fc_RR_min)
    fc_RR_max = float(fc_RR_max)

    if motion_filter_type == 'lp':
        hr_min = LP_freq_min
        hr = hr_min
        fs = 1. / TR
        fNy = fs / 2.
        fa = np.abs(hr - (np.floor((hr + fNy) / fs)) * fs)
        # cutting frequency normalized between 0 and nyquist
        Wn = np.amin(fa) / fNy
        b_filt = firwin(int(order) + 1, Wn, pass_zero='lowpass')
        a_filt = 1.
        num_f_apply = 1.
    else:
        if motion_filter_type == 'notch':
            fc_RR_bw = np.array([fc_RR_min, fc_RR_max])
            rr = fc_RR_bw
            fs = 1. / TR
            fNy = fs / 2.
            fa = np.abs(rr - (np.floor((rr + fNy) / fs)) * fs)
            W_notch = fa / fNy
            Wn = np.mean(W_notch)
            Wd = np.diff(W_notch)
            bw = np.abs(Wd)
            b_filt, a_filt = iirnotch(Wn, Wn / bw)
            num_f_apply = np.int(np.floor(order / 2))
        for j in range(num_f_apply):
            for k in range(data.shape[0]):
                data[k, :] = filtfilt(b_filt, a_filt, data[k, :])
    return data

    # def lowpassfilter_coeff(cutoff, fs, order=4):

    #     nyq = 0.5 * fs
    #     fa = np.abs( cutoff - np.floor((cutoff + nyq) / fs) * fs)
    #     normalCutoff = fa / nyq
    #     b = firwin(order, cutoff=normalCutoff, window='hamming')
    #     a = 1
    #     return b, a

    # def iirnortch_coeff(freqband,fs):
    #     nyq = 0.5*fs
    #     fa = np.abs(freqband - np.floor((np.add(freqband,nyq) / fs) * fs))
    #     w0 = np.mean(fa)/nyq
    #     bw = np.diff(fa)/nyq
    #     qf = w0 / bw
    #     b, a = iirnotch( w0, qf )
    #     return b,a

    # if motion_filter_type == 'lp':
    #     b,a = lowpassfilter_coeff(cutoff,fs,order=4)
    # elif motion_filter_type =='notch':
    #     b,a = iirnortch_coeff(freqband,fs=fs)

    # order_apply = np.int(np.floor(order/2))

    # for j in range(order_apply):
    #     for k in range(data.shape[0]):
    #         data[k,:] = filtfilt(b,a,data[k,:])
    #     j=j+1

    # return data
