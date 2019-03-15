'''
Schema of session information.
'''
import datajoint as dj
from pipeline import reference, acquisition
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
