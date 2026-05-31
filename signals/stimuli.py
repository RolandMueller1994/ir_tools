import numpy as np
from scipy.signal import chirp
from pathlib import Path
from scipy.io import wavfile
from typing import Union


def write_wav(path, sig, fs):
    wavfile.write(str(path), fs, sig)


def create_chirp(length: int, fs:int, f_start: int, f_end: int, outfile: Union[Path, None]=None):
    t_step = length / fs

    t = np.linspace(0, t_step, length)
    sig = chirp(t, f_start, t[-1], f_end, 'logarithmic', phi=90)

    if outfile is not None:
        write_wav(outfile, sig, fs)

    return t, sig