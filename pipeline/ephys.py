'''
Schema of session information.
'''
import datajoint as dj
from . import reference, acquisition, behavior
import scipy.io as sio
import numpy as np
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
    """

    def make(self, key):
        spike_trials = (UnitSpikeTimes & key).fetch1('spike_trials')
        min_trial = min(spike_trials)
        max_trial = max(spike_trials)
        hit_r_trials = behavior.TrialSet.Trial & key & \
            'trial_response = "HitR"' & \
            'trial_id between {} and {}'.format(min_trial, max_trial)
        err_r_trials = behavior.TrialSet.Trial & key & \
            'trial_response = "ErrR"' & \
            'trial_id between {} and {}'.format(min_trial, max_trial)
        hit_l_trials = behavior.TrialSet.Trial & key & \
            'trial_response = "HitL"' & \
            'trial_id between {} and {}'.format(min_trial, max_trial)
        err_l_trials = behavior.TrialSet.Trial & key & \
            'trial_response = "ErrL"' & \
            'trial_id between {} and {}'.format(min_trial, max_trial)

        is_valid = len(hit_r_trials) > 15 and len(hit_l_trials) > 15
        key.update({
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
    -> UnitSpikeTimes
    ---
    time_window:            blob        # time window for spike times and psth, 0 is cue start time.
    spike_times_hit_r:      longblob    # list of spike times on each trial for hit r trials
    spike_times_err_r:      longblob    # list of spike times on each trial for err r trials
    spike_times_hit_l:      longblob    # list of spike times on each trial for hit l trials
    spike_times_err_l:      longblob    # mean firing rate of each stage of err l trials
    spike_counts_hit_r:     longblob    # mean firing rate of each trial for hit r trials
    spike_counts_err_r:     longblob    # mean firing rate of each trial for hit r trials
    spike_counts_hit_l:     longblob    # mean firing rate of each trial for hit r trials
    spike_counts_err_l:     longblob    # mean firing rate of each trial for hit r trials
    bins:                   longblob    # time bins for psth computation
    psth_hit_r:             longblob    # psth for hit r trials
    psth_err_r:             longblob    # psth for hit r trials
    psth_hit_l:             longblob    # psth for hit r trials
    psth_err_l:             longblob    # psth for hit r trials
    sample_selectivity:     tinyint     # whether selectivity is significant during the sample period
    delay_selectivity:      tinyint     # whether selectivity is significnat during the delay period
    response_selectivity:   tinyint     # whether selectivity is significant during the response period
    trial_ids_screened_hit_r: blob      # trial ids that were screened to calculate the preference, for hit r trials
    trial_ids_screened_hit_l: blob      # trial ids that were screened to calculate the preference, for hit l trials
    psth_prefer:            longblob    # psth on preferred hit trials
    psth_non_prefer:        longblob    # psth on non-preferred hit trials
    """

    def make(self, key):
        aligned_psth = key.copy()
        time_window = [-3.5, 2]
