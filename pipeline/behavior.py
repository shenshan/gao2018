'''
Schema of behavior information.
'''
import datajoint as dj
from pipeline import reference, acquisition
import scipy.io as sio
import numpy as np
import os
import glob
import re
from datetime import datetime

schema = dj.schema('gao2018_behavior')


@schema
class PhotoStimType(dj.Lookup):
    definition = """
    photo_stim_id: varchar(8)
    ---
    -> [nullable] reference.BrainLocation
    -> [nullable] reference.Hemisphere
    photo_stim_period='':               varchar(24)  # period during the trial
    photo_stim_relative_location='':    varchar(24)  # stimulus location relative to the recording.
    photo_stim_act_type='':             varchar(24)  # excitation or inihibition
    photo_stim_duration=0:              float        # in ms, stimulus duration
    photo_stim_shape='':                varchar(24)  # shape of photostim, cosine or pulsive
    photo_stim_freq=0:                  float        # in Hz, frequency of photostimulation
    photo_stim_notes='':                varchar(128)
    """
    contents = [
        dict(photo_stim_id='0', photo_stim_notes='stimulus'),
        ['1', 'Fastigial', 'right', 'sample', 'contralateral', 'activation',
            500, '5ms pulse', 20, ''],
        ['2', 'Fastigial', 'right', 'delay', 'contralateral', 'activation',
            500, '5ms pulse', 20, ''],
        ['3', 'Dentate', 'right', 'sample', 'contralateral', 'activation',
            500, '5ms pulse', 20, ''],
        ['4', 'Dentate', 'right', 'delay', 'contralateral', 'activation',
            500, '5ms pulse', 20, ''],
        ['5', 'DCN', 'right', 'delay', 'contralateral', 'inhibition',
            500, 'cosine', 40, ''],
        ['6', 'DCN', 'right', 'delay', 'contralateral', 'inhibition',
            500, 'cosine', 40, ''],
        dict(photo_stim_id='NaN', photo_stim_notes='stimulation configuration \
            for other purposes, should not analyze')
    ]


@schema
class TrialSet(dj.Imported):
    definition = """
    -> acquisition.Session
    ---
    number_of_trials:   int         # number of trials in this session.
    """

    def make(self, key):

        trial_result = key.copy()
        print(key)
        session_dir = (acquisition.Session & key).fetch1('session_directory')
        data = sio.loadmat(session_dir, struct_as_record=False,
                           squeeze_me=True)['obj']

        key.update({'number_of_trials': len(data.trialStartTimes)})
        self.insert1(key)

        trial_type_str = data.trialTypeStr[:-2]
        trial_idx = data.timeSeriesArrayHash.value.trial

        for idx, itrial in enumerate(data.trialIds):

            trial_type_vec = np.squeeze(data.trialTypeMat[:6, idx])
            trial_type = trial_type_str[np.array(trial_type_vec, dtype=bool)]

            if len(trial_type) == 0:
                trial_type = 'NoLickNoResponse'
            else:
                trial_type = trial_type[0]

            pole_in_time = data.trialPropertiesHash.value[0][idx]
            pole_out_time = data.trialPropertiesHash.value[1][idx]
            cue_time = data.trialPropertiesHash.value[2][idx]
            good_trial = data.trialPropertiesHash.value[3][idx]
            photo_stim_type = data.trialPropertiesHash.value[4][idx]

            if np.any(np.isnan([pole_in_time, pole_out_time, cue_time[0],
                                photo_stim_type])) or good_trial == 0:
                continue

            itrial_idx = np.squeeze(np.where(trial_idx == itrial))
            if not itrial_idx.size:
                return

            trial_result.update({
                'trial_id': itrial,
                'trial_start_time': data.trialStartTimes[idx],
                'trial_pole_in_time': pole_in_time,
                'trial_pole_out_time': pole_out_time,
                'trial_cue_time': cue_time[0],
                'trial_response': trial_type,
                'trial_lick_early': bool(data.trialTypeMat[7][idx]),
                'photo_stim_id': str(int(photo_stim_type)),
                'trial_start_idx': itrial_idx[0],
                'trial_end_idx': itrial_idx[-1]
            })
            self.Trial().insert1(trial_result)

    class Trial(dj.Part):
        definition = """
        -> master
        trial_id: int     # trial number to reference to the trials
        ---
        trial_start_time:       float           # in secs, time referenced to session start
        trial_pole_in_time:     float           # in secs, the start of the sample period for each trial, relative to the trial start
        trial_pole_out_time:    float           # in secs, the end of the sample period and start of the delay period, relative to the trial start
        trial_cue_time:         float           # in secs, the end of the delay period, relative to the start of the trials
        trial_response:         enum('HitR', 'HitL', 'ErrR', 'ErrL', 'NoLickR', 'NoLickL', 'NoLickNoResponse')  # subject response to the stimulus
        trial_lick_early:       boolean         # whether the animal licks early
        -> PhotoStimType
        trial_start_idx:        int             # first index for this trial, on the session recording series
        trial_end_idx:          int             # last index for this trial, on the session recording series
        """
