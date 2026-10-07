"""Explicit educational response model; no manufacturer performance constants."""
import json
import math
import numpy as np

# group, key, label, default, minimum, maximum, modelled
FIELDS = [
 ('Sampling inlet','flow_ml_min','Sample flow (mL/min)',100,0.1,10000,True),
 ('Sampling inlet','volume_ml','Inlet volume (mL)',1,0,1000,True),
 ('Sampling inlet','inlet_temperature_c','Inlet temperature (°C)',40,-50,400,False),
 ('Sampling inlet','dilution','Dilution factor',1,1,10000,True),
 ('Sampling inlet','loss_percent','Inlet loss (%)',0,0,100,True),
 ('Sampling inlet','carryover','Carryover signal (a.u.)',0,0,1e8,True),
 ('Sampling inlet','elapsed_s','Time since sample arrival at inlet (s)',10,0,10000,True),
 ('Sampling inlet','response_s','Response time constant (s)',1,0.01,1000,True),
 ('Reagent-ion source','reagent_signal','Reagent signal (relative to reference)',1,0,100,True),
 ('Reaction chamber','pressure_mbar','Reaction pressure (mbar)',2,0.001,2000,False),
 ('Reaction chamber','temperature_c','Reaction temperature (°C)',40,-50,400,False),
 ('Reaction chamber','reaction_ms','Reaction time (ms)',1,0.001,1000,False),
 ('Reaction chamber','field_td','Reduced field E/N (Td; PTR context)',100,0,1000,False),
 ('Reaction chamber','humidity_percent','Relative humidity (%)',45,0,100,False),
 ('Reaction chamber','response_factor','Empirical reaction response multiplier',1,0,100,True),
 ('Ion transfer & vacuum','vacuum_mbar','Analyzer vacuum (mbar)',0.000001,1e-12,1,False),
 ('Ion transfer & vacuum','transmission_percent','Ion transmission (%)',100,0,100,True),
 ('Ion transfer & vacuum','mass_rolloff','Transmission roll-off per 100 Th',0,0,10,True),
 ('TOF analyzer','mass_min','Minimum m/z (Th)',0.5,0.01,10000,True),
 ('TOF analyzer','mass_max','Maximum m/z (Th)',500,0.02,10000,True),
 ('TOF analyzer','resolving_power','Additional response kernel m/Δm (FWHM)',10000,100,100000,True),
 ('Detector & acquisition','integration_s','Integration time (s; reference = 1 s)',1,0.001,1000,True),
 ('Detector & acquisition','gain','Detector gain multiplier',1,0,100,True),
 ('Detector & acquisition','background','Added background (a.u.)',0,0,1e8,True),
 ('Detector & acquisition','noise','Added noise standard deviation (a.u.)',0,0,1e6,True),
 ('Detector & acquisition','saturation','Saturation ceiling (a.u.)',10000000,1,1e12,True),
 ('Calibration & instrument state','drift_ppm','Mass calibration drift (ppm)',0,-1000,1000,True),
]

def normalize(value):
    if not isinstance(value, dict):
        raise ValueError('Instrument configuration must be an object.')
    result = {}
    for _, key, label, default, low, high, _ in FIELDS:
        number = float(value.get(key, default))
        if not math.isfinite(number) or not low <= number <= high:
            raise ValueError(f'{label} must be between {low} and {high}.')
        result[key] = number
    result['reagent'] = str(value.get('reagent','I-'))
    if result['reagent'] not in ('I-','NO3-','H3O+','NH4+','NO+','O2+'):
        raise ValueError('Unsupported configuration reagent.')
    result['state'] = str(value.get('state','ready'))
    if result['state'] not in ('ready','standby','fault'):
        raise ValueError('Unknown instrument state.')
    if result['mass_min'] >= result['mass_max']:
        raise ValueError('Minimum m/z must be below maximum m/z.')
    return result

def transform(x, y, c):
    """Deterministic illustrative response applied to full data before windowing."""
    x = x * (1 + c['drift_ppm'] / 1e6)
    delay = 60 * c['volume_ml'] / c['flow_ml_min']
    response = 1 - math.exp(-max(0,c['elapsed_s']-delay)/c['response_s'])
    scale = ((1-c['loss_percent']/100)/c['dilution'] * response
             * c['reagent_signal'] * c['response_factor']
             * c['transmission_percent']/100 * c['integration_s'] * c['gain'])
    y = np.maximum(y,0) * scale * np.exp(-c['mass_rolloff']*np.maximum(x,0)/100)
    # Additional Gaussian response, never claim to recover native resolution.
    if len(x)>2 and np.all(np.diff(x)>0) and np.allclose(np.diff(x),np.median(np.diff(x)),rtol=0.02):
        step = np.median(np.diff(x))
        sigma = np.median(x)/(c['resolving_power']*2.35482*step)
        if sigma > 0.15:
            radius = min(len(x)-1, int(math.ceil(4*sigma)), 2000)
            kernel = np.exp(-0.5*(np.arange(-radius,radius+1)/sigma)**2)
            kernel /= kernel.sum()
            n = 1 << (len(y)+len(kernel)-2).bit_length()
            convolution = np.fft.irfft(np.fft.rfft(y,n)*np.fft.rfft(kernel,n),n)
            y = convolution[radius:radius+len(y)]
    y = y + c['background'] + c['carryover']
    y += np.random.default_rng(42).normal(0,c['noise'],len(y))
    y = np.clip(y,0,c['saturation'])
    if c['state'] != 'ready':
        y = np.zeros_like(y)
    keep = (x>=c['mass_min']) & (x<=c['mass_max'])
    return x[keep], y[keep], {'transport_delay_s':delay,'sample_response_fraction':response,
        'signal_multiplier':scale,'status':'ILLUSTRATIVE — NOT CALIBRATED',
        'context_only':[key for _,key,_,_,_,_,modelled in FIELDS if not modelled],
        'limitations':'Reagent selection changes newly generated Vocus chemistry only; it cannot re-ionize loaded spectra. Kernel uses median m/z and adds broadening. No physical chemistry, selectivity, concentration, or identification prediction.'}
