'''
Schema of session information.
'''
import datajoint as dj
from . import reference, acquisition, behavior
from . import get_trials, get_spk_times, get_spk_counts, get_psth
import scipy.io as sio
import scipy.stats as ss
import numpy as np
from numpy import random
import os
import glob
import re
from datetime import datetime

schema = dj.schema('gao2018_ephys')


@schema
class ProbeInsertion(dj.Manual):
    definition = """ # Description of probe insertion details during extracellular recording
    -> acquisition.Session
    -> reference.BrainLocation
    ---
    -> reference.Probe
    rec_coordinate_ap: float      # in mm, positive when more anterior relative to the reference point.
    rec_coordinate_ml: float      # in mm, larger when more lateral
    rec_coordinate_dv=null: float # in mm, larger when deeper
    ground_coordinate_ap: float   # in mm
    ground_coordinate_ml: float   # in mm
    ground_coordinate_dv: float   # in mm
    rec_marker: enum('stereotaxic')
    spike_sorting_method: enum('manual')
    ad_unit: varchar(12)
    -> reference.CoordinateReference
    penetration_num: tinyint      # the number of penetration a craniotomy has experienced.
    """


@schema
class Voltage(dj.Imported):
    definition = """
    -> ProbeInsertion
    ---
    voltage: longblob   # (mV)
    voltage_start_time: float # (second) first timepoint of voltage recording
    voltage_sampling_rate: float # (Hz) sampling rate of voltage recording
    """


@schema
class UnitSpikeTimes(dj.Imported):
    definition = """
    -> ProbeInsertion
    unit_id : smallint
    ---
    -> reference.Probe.Channel.proj(channel = 'channel_id')
    spike_times: longblob  # (s) time of each spike, with respect to the start of session
    spike_trials: longblob # which trial each spike belongs to.
    unit_cell_type='unknown': varchar(32)  # e.g. cell-type of this unit (e.g. wide width, narrow width spiking)
    spike_waveform: longblob  # waveform(s) of each spike at each spike time (spike_time x waveform_timestamps)
    unit_x=null: float  # (mm)
    unit_y=null: float  # (mm)
    unit_z=null: float  # (mm)
    """
    key_source = ProbeInsertion()

    def make(self, key):
        print(key)

        session_dir = (acquisition.Session & key).fetch1('session_directory')
        data = sio.loadmat(session_dir, struct_as_record=False,
                           squeeze_me=True)['obj']

        for iunit, unit in enumerate(data.eventSeriesHash.value):
            value = data.eventSeriesHash.value[iunit]

            # insert the channel entry into the table reference.Probe.Channel
            probe_type = (ProbeInsertion & key).fetch1('probe_type')
            channel = np.unique(value.channel)[0]
            probe_channel = {
                'probe_type': probe_type,
                'channel_id': channel
            }
            reference.Probe.Channel.insert1(probe_channel,
                                            skip_duplicates=True)

            key.update({
                'unit_id': iunit,
                'spike_times': value.eventTimes,
                'spike_trials': value.eventTrials,
                'probe_type': probe_type,
                'channel': channel,
                'spike_waveform': value.waveforms
            })

            if np.size(value.cellType):
                key['unit_cell_type'] = value.cellType

            self.insert1(key)


@schema
class ValidUnit(dj.Computed):
    definition = """
    -> UnitSpikeTimes
    ---
    is_valid:           bool      # check whether a unit is valid based on some criteria
    number_hit_r:       int       # number of hit r trials for this unit
    number_err_r:       int       # number of err r trials for this unit
    number_hit_l:       int       # number of hit l trials for this unit
    number_err_l:       int       # number of err l trials for this unit
    hit_r_ids=null:     blob      # trial_ids of hit r trials
    err_r_ids=null:     blob      # trial_ids of err r trials
    hit_l_ids=null:     blob      # trial_ids of hit l trials
    err_l_ids=null:     blob      # trial_ids of err l trials
    """

    def make(self, key):
        spike_trials = (UnitSpikeTimes & key).fetch1('spike_trials')
        min_trial = min(spike_trials)
        max_trial = max(spike_trials)
        hit_r_trials = get_trials(key, min_trial, max_trial, 'HitR')
        err_r_trials = get_trials(key, min_trial, max_trial, 'ErrR')
        hit_l_trials = get_trials(key, min_trial, max_trial, 'HitL')
        err_l_trials = get_trials(key, min_trial, max_trial, 'ErrL')

        is_valid = len(hit_r_trials) > 15 and len(hit_l_trials) > 15
        key.update({
            'hit_r_ids': hit_r_trials.fetch('trial_id'),
            'err_r_ids': err_r_trials.fetch('trial_id'),
            'hit_l_ids': hit_l_trials.fetch('trial_id'),
            'err_l_ids': err_l_trials.fetch('trial_id'),
            'number_hit_r': len(hit_r_trials),
            'number_err_r': len(err_r_trials),
            'number_hit_l': len(hit_l_trials),
            'number_err_l': len(err_l_trials),
            'is_valid': is_valid
        })
        self.insert1(key)


@schema
class AlignedPsth(dj.Computed):
    definition = """
    -> ValidUnit
    ---
    mean_fr_hit_r:          longblob    # mean firing rate of each trial for hit r trials
    mean_fr_err_r=null:     longblob    # mean firing rate of each trial for err r trials
    mean_fr_hit_l:          longblob    # mean firing rate of each trial for hit l trials
    mean_fr_err_l=null:     longblob    # mean firing rate of each trial for err l trials
    time_window:            blob        # time window for spike times and psth, 0 is cue start time.
    bins:                   longblob    # time bins for psth computation
    psth_hit_r:             longblob    # psth for hit r trials
    psth_err_r=null:        longblob    # psth for err r trials
    psth_hit_l:             longblob    # psth for hit l trials
    psth_err_l=null:        longblob    # psth for err l trials
    sample_selectivity:     boolean     # whether selectivity is significant during the sample period
    delay_selectivity:      boolean     # whether selectivity is significnat during the delay period
    response_selectivity:   boolean     # whether selectivity is significant during the response period
    trial_ids_screened_hit_r: blob      # trial ids that were screened to calculate the preference, for hit r trials
    trial_ids_screened_hit_l: blob      # trial ids that were screened to calculate the preference, for hit l trials
    psth_prefer:            longblob    # psth on preferred hit trials
    psth_non_prefer:        longblob    # psth on non-preferred hit trials
    """

    key_source = ValidUnit & 'is_valid = 1'

    def make(self, key):
        print(key)
        aligned_psth = key.copy()
        hit_r_ids, err_r_ids, hit_l_ids, err_l_ids = (ValidUnit & key).fetch1(
            'hit_r_ids', 'err_r_ids', 'hit_l_ids', 'err_l_ids'
        )

        spk_times, spk_trials = (UnitSpikeTimes & key).fetch1(
            'spike_times', 'spike_trials')

        photo_stim_type = '0'
        # spike times
        spk_times_hit_r = get_spk_times(key, spk_times, spk_trials, hit_r_ids,
                                        photo_stim_type)
        spk_times_err_r = get_spk_times(key, spk_times, spk_trials, err_r_ids)
        spk_times_hit_l = get_spk_times(key, spk_times, spk_trials, hit_l_ids)
        spk_times_err_l = get_spk_times(key, spk_times, spk_trials, err_l_ids)

        # spike counts in different stages
        spk_counts_hit_r = get_spk_counts(key, spk_times_hit_r, hit_r_ids)
        spk_counts_err_r = get_spk_counts(key, spk_times_err_r, err_r_ids)
        spk_counts_hit_l = get_spk_counts(key, spk_times_hit_l, hit_l_ids)
        spk_counts_err_l = get_spk_counts(key, spk_times_err_l, err_l_ids)

        # compute convoluted psth
        time_window = [-3.5, 2]
        bins = np.arange(time_window[0], time_window[1]+0.001, 0.001)

        psth_hit_r = get_psth(spk_times_hit_r, bins)
        if np.size(spk_times_err_r):
            psth_err_r = get_psth(spk_times_err_r, bins)
            aligned_psth.update({
                'mean_fr_err_r': np.mean(spk_counts_err_r, axis=0),
                'psth_err_r': psth_err_r
            })
        psth_hit_l = get_psth(spk_times_hit_l, bins)
        if np.size(spk_times_err_l):
            psth_err_l = get_psth(spk_times_err_l, bins)
            aligned_psth.update({
                'mean_fr_err_l': np.mean(spk_counts_err_l, axis=0),
                'psth_err_l': psth_err_l
            })

        # check selectivity
        result_sample = ss.ttest_ind(spk_counts_hit_r[:][0],
                                     spk_counts_hit_l[:][0])
        result_delay = ss.ttest_ind(spk_counts_hit_r[:][1],
                                    spk_counts_hit_l[:][1])
        result_response = ss.ttest_ind(spk_counts_hit_r[:][2],
                                       spk_counts_hit_l[:][2])

        # prefered psth
        random.shuffle(hit_r_ids)
        random.shuffle(hit_l_ids)

        spk_times_hit_r_screen = get_spk_times(key, spk_times, spk_trials,
                                               hit_r_ids[:10])
        mean_fr_hit_r_screen = np.mean(get_spk_counts(key,
                                                      spk_times_hit_r_screen,
                                                      hit_r_ids[:10]),
                                       axis=0)

        spk_times_l_screen = get_spk_times(key, spk_times, spk_trials,
                                           hit_l_ids[:10])
        mean_fr_hit_l_screen = np.mean(get_spk_counts(key,
                                                      spk_times_hit_r_screen,
                                                      hit_l_ids[:10]),
                                       axis=0)

        spk_times_hit_r_test = get_spk_times(key, spk_times, spk_trials,
                                             hit_r_ids[10:])
        spk_counts_hit_r_test = get_spk_counts(key, spk_times_hit_r_test,
                                               hit_r_ids[10:])

        spk_times_hit_l_test = get_spk_times(key, spk_times, spk_trials,
                                             hit_l_ids[10:])
        spk_counts_hit_l_test = get_spk_counts(key, spk_times_hit_l_test,
                                               hit_l_ids[10:])

        psth_hit_r_test = get_psth(spk_times_hit_r_test, bins)
        psth_hit_l_test = get_psth(spk_times_hit_l_test, bins)
        if mean_fr_hit_r_screen[3] > mean_fr_hit_r_screen[3]:
            psth_prefer = psth_hit_r_test
            psth_non_prefer = psth_hit_l_test
        else:
            psth_prefer = psth_hit_l_test
            psth_non_prefer = psth_hit_r_test

        aligned_psth.update({
            'mean_fr_hit_r': np.mean(spk_counts_hit_r, axis=0),
            'mean_fr_hit_l': np.mean(spk_counts_hit_l, axis=0),
            'time_window': time_window,
            'bins': bins,
            'psth_hit_r': psth_hit_r,
            'psth_hit_l': psth_hit_l,
            'sample_selectivity': bool(result_sample.pvalue < 0.05),
            'delay_selectivity':  bool(result_delay.pvalue < 0.05),
            'response_selectivity': bool(result_delay.pvalue < 0.05),
            'trial_ids_screened_hit_r': hit_r_ids[:10],
            'trial_ids_screened_hit_l': hit_l_ids[:10],
            'psth_prefer': psth_prefer,
            'psth_non_prefer': psth_non_prefer
        })

        self.insert1(aligned_psth)
