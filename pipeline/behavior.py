'''
Schema of behavior information.
'''
import datajoint as dj
from pipeline import reference, acquisition

schema = dj.schema('gao2018_behavior')
    
@schema
class PhotoStim(dj.Manual):
    definition = """
    -> acquisition.Session
    ---
    photo_stim_wavelength: int
    photo_stim_method: enum('fiber', 'laser')
    -> reference.BrainLocation
    -> reference.Hemisphere
    -> reference.CoordinateReference
    photo_stim_coordinate_ap: float    # in mm, anterior positive, posterior negative 
    photo_stim_coordinate_ml: float    # in mm, always postive, number larger when more lateral
    photo_stim_coordinate_dv: float    # in mm, always postive, number larger when more ventral (deeper)
    """

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
        dict(photo_stim_id = '0', photo_stim_notes = 'stimulus'), 
        ['1', 'Fastigial', 'right', 'sample', 'contralateral', 'activation', 500, '5ms pulse', 20, ''],
        ['2', 'Fastigial', 'right', 'delay', 'contralateral', 'activation', 500, '5ms pulse', 20, ''],
        ['3', 'Dentate', 'right', 'sample', 'contralateral', 'activation', 500, '5ms pulse', 20, ''],
        ['4', 'Dentate', 'right', 'delay', 'contralateral', 'activation', 500, '5ms pulse', 20, ''],
        ['5', 'DCN', 'right', 'delay', 'contralateral', 'inhibition', 500, 'cosine', 40, ''],
        ['6', 'DCN', 'right', 'delay', 'contralateral', 'inhibition', 500, 'cosine', 40, ''],
        dict(photo_stim_id = 'NaN', photo_stim_notes = 'stimulation configuration for other purposes, should not analyze')
    ]


@schema
class TrialSet(dj.Imported):
    definition = """
    -> acquisition.Session
    ---
    number_of_trials:   int         # number of trials in this session.
    sample_trial_idx:   longblob    # trial number for each sample in the time series.
    """

    def make(self, key):
            self.insert1(key)

    class Trial(dj.Part):
        definition = """
        -> master
        trial_id: int     # trial number to reference to the trials
        ---
        trial_time:             longblob        # in secs, trial time series in session time, time 0 is session start.
        trial_start_time:       float           # in secs, time referenced to session start
        trial_pole_in_time:     float           # in secs, the start of the sample period for each trial
        trial_pole_out_time:    float           # in secs, the end of the sample period and start of the delay period
        trial_cue_time:         float           # in secs, the end of the delay period, relative to the start of the trials
        trial_response:         enum('HitR', 'HitL', 'ErrR', 'ErrL', 'NoLickR', 'NoLickL')  # subject response to the stimulus
        trial_lick_early:       boolean         # whether the animal licks early
        -> PhotoStimType
        trial_pstim_waveform:   longblob        # waveform of photostimulation
        trial_pstim_laser_power: longblob       # laser power of photostimulation
        """

        
