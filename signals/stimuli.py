import numpy as np
from scipy.signal import chirp
from pathlib import Path
from scipy.io import wavfile
from typing import Union
from scene_rir import rir


def write_wav(path, sig, fs):
    wavfile.write(str(path), fs, sig)


def create_chirp(length: int, fs:int, f_start: int, f_end: int, outfile: Union[Path, None]=None) -> rir.SweptSineSignal:
    t_step = length / fs

    t = np.linspace(0, t_step, length)
    sig = chirp(t, f_start, t[-1], f_end, 'logarithmic', phi=90)

    if fs not in [44100, 48000]:
        raise ValueError(f'Sample rate must be 44100 or 48000 but was {fs}!')

    sweep_params = {
        'smprteidx': 4 if fs == 44100 else 5,
        'sglszeidx': 5,
        'frqstt': f_start,
        'frqstp': f_end
    }

    sig = rir.SweptSineSignal(sweep_params)
    sig.save(str(outfile))

    return sig