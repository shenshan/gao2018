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
class UnitSelectivity(dj.Computed):
    definition = """
    -> UnitSpikeTimes
    -> behavior.TrialCondition
    ---
    r_trial_number:             int         # trial number of right reports
    l_trial_number:             int         # trial number of left reports
    r_trial_ids:                blob        # trial ids of right report trials
    l_trial_ids:                blob        # trial ids of left report trials
    sample_selectivity:         boolean     # whether selectivity is significant during the sample period
    delay_selectivity:          boolean     # whether selectivity is significant during the delay period
    response_selectivity:       boolean     # whether selectivity is significant during the response period
    selectivity:                boolean     # whether any of the previous three is significant
    preference:                 enum('R', 'L', 'N')
    time_window:                blob        # time window of interest
    bins:                       longblob    # time bins
    trial_ids_screened_r:       blob        # trial ids that were screened to calculate the preference, for r trials
    trial_ids_screened_l:       blob        # trial ids that were screened to calculate the preference, for l trials
    mean_fr_r_all:              blob        # mean firing rate of right reporting trials in different stages
    mean_fr_l_all:              blob        # mean firing rate of left reporting trials in different stages
    mean_fr_diff_rl_all:        blob        # mean firing rate difference, right - left
    psth_r_test:                longblob    # psth for right report test trials
    psth_l_test:                longblob    # psth for left report test trials
    psth_prefer_test:           longblob    # psth on preferred test trials
    psth_non_prefer_test:       longblob    # psth on non-preferred test trials
    psth_diff_test:             longblob    # psth difference between preferred and non-preferred test trials
    preference:                 enum('R', 'L', 'No')
    """

    key_source = UnitSpikeTimes * behavior.TrialCondition - \
        (UnitSpikeTimes.proj() &
         (behavior.TrialSetType & 'trial_set_type="photo inhibition"')) * \
        (behavior.TrialCondition & 'trial_condition="Hit"')

    def make(self, key):

        selectivity = key.copy()
        key_no_stim = key.copy()
        key_no_stim['photo_stim_id'] = '0'

        spk_times, spk_trials = (UnitSpikeTimes & key).fetch1(
                'spike_times', 'spike_trials')

        min_trial = np.min(spk_trials)
        max_trial = np.max(spk_trials)

        r_trials = get_trials(key_no_stim, min_trial, max_trial, 'R')
        l_trials = get_trials(key_no_stim, min_trial, max_trial, 'L')

        if not (len(l_trials) > 8 and len(r_trials) > 8):
            return

        r_trial_ids = r_trials.fetch('trial_id')
        l_trial_ids = l_trials.fetch('trial_id')

        # spike times
        spk_times_r = get_spk_times(key, spk_times, spk_trials,
                                    r_trial_ids)
        spk_times_l = get_spk_times(key, spk_times, spk_trials,
                                    l_trial_ids)

        # spike counts in different stages
        spk_counts_r = np.array(get_spk_counts(key, spk_times_r, r_trial_ids))
        spk_counts_l = np.array(get_spk_counts(key, spk_times_l, l_trial_ids))

        mean_fr_r = np.mean(spk_counts_r, axis=0)
        mean_fr_l = np.mean(spk_counts_l, axis=0)

        # check selectivity
        result_sample = ss.ttest_ind(spk_counts_r[:, 0],
                                     spk_counts_l[:, 0])
        result_delay = ss.ttest_ind(spk_counts_r[:, 1],
                                    spk_counts_l[:, 1])
        result_response = ss.ttest_ind(spk_counts_r[:, 2],
                                       spk_counts_l[:, 2])
        sample_selectivity = int(result_sample.pvalue < 0.05)
        delay_selectivity = int(result_delay.pvalue < 0.05)
        response_selectivity = int(result_response.pvalue < 0.05)

        # screen size depends on the experimental type
        trial_set_type = (behavior.TrialSetType & key).fetch1('trial_set_type')
        if trial_set_type == "photo activation":
            screen_size = 10
        else:
            screen_size = 5

        random.shuffle(r_trial_ids)
        random.shuffle(l_trial_ids)

        spk_times_r_screen = get_spk_times(key, spk_times, spk_trials,
                                           r_trial_ids[:screen_size])
        mean_fr_r_screen = np.mean(get_spk_counts(key,
                                                  spk_times_r_screen,
                                                  r_trial_ids[:screen_size]),
                                   axis=0)

        spk_times_l_screen = get_spk_times(key, spk_times, spk_trials,
                                           l_trial_ids[:screen_size])
        mean_fr_l_screen = np.mean(get_spk_counts(key,
                                                  spk_times_l_screen,
                                                  l_trial_ids[:screen_size]),
                                   axis=0)

        spk_times_r_test = get_spk_times(key, spk_times, spk_trials,
                                         r_trial_ids[screen_size:])
        spk_counts_r_test = get_spk_counts(key, spk_times_r_test,
                                           r_trial_ids[screen_size:])

        spk_times_l_test = get_spk_times(key, spk_times, spk_trials,
                                         l_trial_ids[screen_size:])
        spk_counts_l_test = get_spk_counts(key, spk_times_l_test,
                                           l_trial_ids[screen_size:])

        # compute convoluted psth
        time_window = [-3.5, 2]
        bins = np.arange(time_window[0], time_window[1]+0.001, 0.001)

        psth_r_test = get_psth(spk_times_r_test, bins)
        psth_l_test = get_psth(spk_times_l_test, bins)
        if mean_fr_r_screen[3] > mean_fr_l_screen[3]:
            psth_prefer_test = psth_r_test
            psth_non_prefer_test = psth_l_test
            preference = 'R'
        else:
            psth_prefer_test = psth_l_test
            psth_non_prefer_test = psth_r_test
            preference = 'L'

        if not selectivity:
            preference = 'No'

        selectivity.update({
            'r_trial_number': len(r_trials),
            'l_trial_number': len(l_trials),
            'r_trial_ids': r_trial_ids,
            'l_trial_ids': l_trial_ids,
            'sample_selectivity': sample_selectivity,
            'delay_selectivity':  delay_selectivity,
            'response_selectivity': response_selectivity,
            'selectivity': int(np.any([sample_selectivity, delay_selectivity,
                                       response_selectivity])),
            'time_window': time_window,
            'bins': bins,
            'trial_ids_screened_r': r_trial_ids[:screen_size],
            'trial_ids_screened_l': l_trial_ids[:screen_size],
            'psth_r_test': psth_r_test,
            'psth_l_test': psth_l_test,
            'psth_prefer_test': psth_prefer_test,
            'psth_non_prefer_test': psth_non_prefer_test,
            'psth_diff_test': psth_prefer_test - psth_non_prefer_test,
            'mean_fr_r_all': mean_fr_r,
            'mean_fr_l_all': mean_fr_l,
            'mean_fr_diff_rl_all': mean_fr_r - mean_fr_l,
            'preference': preference
        })

        self.insert1(selectivity)


@schema
class AlignedPsthStimOn(dj.Computed):
    definition = """
    -> UnitSelectivity
    -> behavior.PhotoStimType
    ---
    r_trial_number_on:    int         # trial number of right reports
    l_trial_number_on:    int         # trial number of left reports
    mean_fr_r_on:         longblob    # mean firing rate for right report trials
    mean_fr_l_on:         longblob    # mean firing rate for left report trials
    psth_r_on:            longblob    # psth for right report trials
    psth_l_on:            longblob    # psth for left report trials
    psth_prefer_on:       longblob    # psth on preferred trials
    psth_non_prefer_on:   longblob    # psth on non-preferred trials
    psth_diff_on:         longblob    # psth difference betweens preferred trials and non-preferred trials
    """

    def make(self, key):

        if key['photo_stim_id'] in ['NaN', '0']:
            return

        time_window, bins, preference, selectivity = \
            (UnitSelectivity & key).fetch1(
                'time_window', 'bins', 'preference', 'selectivity')

        if not selectivity:
            return

        aligned_psth = key.copy()

        spk_times, spk_trials = (UnitSpikeTimes & key).fetch1(
            'spike_times', 'spike_trials')
        min_trial = min(spk_trials)
        max_trial = max(spk_trials)
        r_trials = get_trials(key, min_trial, max_trial, 'R')
        l_trials = get_trials(key, min_trial, max_trial, 'L')

        if not (len(l_trials) > 2 and len(r_trials) > 2):
            return

        r_trial_ids = r_trials.fetch('trial_id')
        l_trial_ids = l_trials.fetch('trial_id')

        # spike times
        spk_times_r = get_spk_times(key, spk_times, spk_trials,
                                    r_trial_ids)
        spk_times_l = get_spk_times(key, spk_times, spk_trials,
                                    l_trial_ids)

        # spike counts in different stages
        spk_counts_r = np.array(get_spk_counts(key, spk_times_r, r_trial_ids))
        spk_counts_l = np.array(get_spk_counts(key, spk_times_l, l_trial_ids))

        # compute convoluted psth
        psth_r = get_psth(spk_times_r, bins)
        psth_l = get_psth(spk_times_l, bins)

        if preference == 'R':
            psth_prefer = psth_r
            psth_non_prefer = psth_l
        elif preference == 'L':
            psth_prefer = psth_l
            psth_non_prefer = psth_r

        aligned_psth.update({
            'r_trial_number_on': len(r_trials),
            'l_trial_number_on': len(l_trials),
            'mean_fr_r_on': np.mean(spk_counts_r, axis=0),
            'mean_fr_l_on': np.mean(spk_counts_l, axis=0),
            'psth_r_on': psth_r,
            'psth_l_on': psth_l,
            'psth_prefer_on': psth_prefer,
            'psth_non_prefer_on': psth_non_prefer,
            'psth_diff_on': psth_prefer - psth_non_prefer
        })

        self.insert1(aligned_psth)
