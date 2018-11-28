'''
Schema of subject information.
'''
import datajoint as dj

schema = dj.schema('gao2018_reference')

@schema
class BrainLocation(dj.Lookup):
    definition = """
    brain_location_name: varchar(64)
    ---
    brain_location_full_name: varchar(128)
    """
    contents = [
        ['Fastigial', 'Cerebellar fastigial nucleus'],
        ['ALM', 'Anteriror lateral motor cortex']
    ]

@schema
class Hemisphere(dj.Lookup):
    definition = """
    hemisphere_name: varchar(32)
    """
    contents = [['left'], ['right']]

@schema
class CoordinateReference(dj.Lookup):
    definition = """
    coordinate_ref: varchar(32)
    """
    contents = [['lambda'], ['bregma']]

@schema
class AnimalSource(dj.Lookup):
    definition = """
    animal_source_name: varchar(64)
    """
    contents = [['JAX'], ['Homemade']]

@schema
class VirusSource(dj.Lookup):
    definition = """
    virus_source_name: varchar(64)
    """
    contents = [['UNC'], ['UPenn'], ['MIT'], ['Stanford'], ['Homemade']]

@schema
class ProbeSource(dj.Lookup):
    definition = """
    probe_source_name: varchar(64)
    ---
    number_of_channels: int
    """
    contents = [
        ['Cambridge NeuroTech', 64],
        ['NeuroNexus', 32]
    ]

@schema
class Virus(dj.Lookup):
    definition = """
    virus_name: varchar(64) # name of the virus
    ---
    -> VirusSource
    virus_lot_number=null:  varchar(128)  # lot numnber of the virus
    virus_titer=null:       float     # x10^12GC/mL
    """
    contents = [
        {'virus_name': 'AAV2-hSyn-hChR2(H134R)-EYFP', 
         'virus_source_name': 'UNC'
        }
    ]

@schema
class Experimenter(dj.Lookup):
    definition = """
    experimenter_name: varchar(64)
    """
    contents = [['Nuo Li']]

@schema
class Whisker(dj.Lookup):
    definition = """
    whisker_config: varchar(32)
    """
    contents = [['full'], ['C2']]
