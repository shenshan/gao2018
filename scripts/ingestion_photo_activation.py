'''
This script ingests all the data for photo-activation experiments.
'''

import datajoint as dj
import scipy.io as sio
import numpy as np
import os, glob, re
from datetime import datetime
from pipeline import reference, subject, action, acquisition, behavior, ephys

# insert the meta data
files = glob.glob('/data/datafiles/meta_data*')
files2 = glob.glob('/data/datafiles 2/meta_data*')
files = np.hstack([files, files2])


for file in files:
    data = sio.loadmat(file, struct_as_record = False, squeeze_me = True)['meta_data']
    
    # ====== reference tables ======
    reference.AnimalSource.insert1([data.animalSource], skip_duplicates=True)
    reference.WhiskerConfig.insert1([data.whiskerConfig], skip_duplicates=True)
    reference.Experimenter.insert1([data.experimenters], skip_duplicates=True)
    reference.ReferenceAtlas.insert1([data.referenceAtlas], skip_duplicates=True)
    
    # ====== subject tables ======
    subject.Species.insert1([data.species], skip_duplicates=True)

    strains = data.animalStrain
    if type(strains) == str:
        subject.Strain.insert1([strains], skip_duplicates=True)
    else:
        for strain in data.animalStrain:
            subject.Strain.insert1([strain], skip_duplicates=True)
    
    animal = {
        'subject': data.animalID,
        'species': data.species,
        'sex': data.sex,
        'date_of_birth': data.dateOfBirth,
        'animal_source': data.animalSource
    }
    subject.Subject.insert1(animal, skip_duplicates=True)
    
    zygosity = {'subject': data.animalID}
    alleles = data.animalGeneModification
    if alleles.size > 0:
        for i_allele, allele in enumerate(alleles):
            subject.Allele.insert1([allele], skip_duplicates=True)
            zygosity['allele'] = allele
            copy = data.animalGeneCopy[i_allele]
            if copy == 0:
                zygosity['zygosity'] = 'Negative'
            elif copy == 1:
                zygosity['zygosity'] = 'Heterozygous'
            elif copy == 2:
                zygosity['zygosity'] = 'Homozygous'
            else:
                print('Invalid zygosity')
                continue
            subject.Zygosity.insert1(zygosity, skip_duplicates=True)
            
    # ====== action tables ======
    if data.weightBefore.size > 0 and data.weightAfter > 0:
        weighing = {
            'subject': data.animalID,
            'weight_before': data.weightBefore,
            'weight_after': data.weightAfter  
        }
        action.Weighing.insert1(weighing, skip_duplicates=True)
    
    whisker = {
        'subject': data.animalID,
        'whisker_config': data.whiskerConfig
    }
    action.SubjectWhiskerConfig.insert1(whisker, skip_duplicates=True)
    
    # virus related tables
    if hasattr(data, 'virus'):
        reference.VirusSource.insert1([data.virus.virusSource], skip_duplicates=True)
        virus = {
            'virus': data.virus.virusID,
            'virus_source': data.virus.virusSource   
        }
        reference.Virus.insert1(virus, skip_duplicates=True)
        
        location = data.virus.infectionLocation
        words = re.sub("[^\w]", " ", location).split()
        hemisphere = np.array(words)[np.array([(word in ['left', 'right']) for word in words])]
        loc = np.array(words)[np.array([(word in ['Fastigial', 'Dentate', 'DCN', 'ALM']) for word in words])]
        ref = np.array(words)[np.array([(word in ['lambda', 'bregma']) for word in words])]
        virus_injection = {
            'subject': data.animalID,
            'virus': data.virus.virusID,
            'brain_location': str(np.squeeze(loc)),
            'hemisphere': str(np.squeeze(hemisphere)),
            'injection_volume': data.virus.injectionVolume,
            'injection_date': datetime.strptime(data.virus.injectionDate, '%Y%m%d').date(),
            'injection_coordinate_ap': data.virus.infectionCoordinates[0],
            'injection_coordinate_ml': data.virus.infectionCoordinates[1],
            'injection_coordinate_dv': data.virus.infectionCoordinates[2],
            'coordinate_ref': str(np.squeeze(ref))
        }
        action.VirusInjection.insert1(virus_injection, skip_duplicates=True)
    
    # ExtraCellular recording related tables
    probe_sources = data.extracellular.probeSource
    probes = data.extracellular.probeType
    
    if type(probe_sources) == str:
        reference.ProbeSource.insert1([probe_sources], skip_duplicates=True)
        n_channels = int(np.squeeze(re.findall('\s\d{2}', probes)))
        probe_key = {
            'probe_type': probes,
            'probe_source': probe_sources,
            'channel_counts': n_channels
        }
        reference.Probe.insert1(probe_key, skip_duplicates=True)
    else:
        for iprobe, probe_source in enumerate(probe_sources):
            reference.ProbeSource.insert1([probe_source], skip_duplicates=True)
            probe = probes[iprobe]
            n_channels = int(np.squeeze(re.findall('\s\d{2}', probe)))
            probe_key = {
                'probe_type': probe,
                'probe_source': probe_source,
                'channel_counts': n_channels
            }
            reference.Probe.insert1(probe_key, skip_duplicates=True)

    # Photositim related tables
    
