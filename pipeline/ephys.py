'''
Schema of session information.
'''
import datajoint as dj
from pipeline import reference, acquisition

schema = dj.schema('gao2018_ephys')

@schema
class ProbeInsertion(dj.Manual):
    definition = """ # Description of probe insertion details during extracellular recording
    -> acquisition.Session
    -> reference.Probe
    -> reference.BrainLocation
    ---
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

    def make(self, key):
        # this function implements the ingestion of raw extracellular data into the pipeline
        return None


@schema
class UnitSpikeTimes(dj.Imported):
    definition = """ 
    -> ProbeInsertion
    unit_id : smallint
    ---
    -> reference.Probe.Channel
    spike_times: longblob  # (s) time of each spike, with respect to the start of session 
    unit_cell_type: varchar(32)  # e.g. cell-type of this unit (e.g. wide width, narrow width spiking)
    unit_x: float  # (mm)
    unit_y: float  # (mm)
    unit_z: float  # (mm)
    spike_waveform: longblob  # waveform(s) of each spike at each spike time (spike_time x waveform_timestamps)
    """
