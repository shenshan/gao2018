'''
Schema of subject information.
'''
import datajoint as dj

schema = dj.schema('gao2018_reference')

@schema
class BrainLocation(dj.Lookup):
    definition = """
    brain_location_name: varchar(64)
    """

    contents = [['Fastigial'], ]

@schema
class Hemisphere(dj.Lookup):
    definition = """
    hemisphere_name: varchar(32)
    """
    contents = [['left'], ['right'], ['both']]

@schema
class CoordinateReference(dj.Lookup):
    definition = """
    coordinate_ref: varchar(32)
    """
    contents = [['lambda'], ['bregma']]


@schema
class Virus(dj.Lookup):
    definition = """
    virus_name: varchar(64) # name of the virus
    ---
    virus_source: enum('UNC', 'UPenn', 'MIT', 'Stanford', 'Homemade')
    virus_lot_number=null: varchar(128)  # lot numnber of the virus
    virus_titer=null: float     # x10^12GC/mL
    """
    contents = ['AAV-']

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
