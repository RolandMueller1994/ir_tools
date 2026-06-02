
from pathlib import Path
from scipy.io import wavfile
from typing import Union
from scene_rir import rir
import numpy as np


def write_wav(path, sig, fs):
    wavfile.write(str(path), fs, sig)


def create_chirp(fs:int, f_start: int, f_end: int, outfile: Union[Path, None]=None, level: float = -20) -> rir.SweptSineSignal:

    if fs not in [44100, 48000]:
        raise ValueError(f'Sample rate must be 44100 or 48000 but was {fs}!')

    sweep_params = {
        'smprteidx': 4 if fs == 44100 else 5,
        'sglszeidx': 5,
        'frqstt': f_start,
        'frqstp': f_end,
        'sgllvl': level
    }

    sig = rir.SweptSineSignal(sweep_params)
    sig.save(str(outfile))

    return sig


def create_output_data(sig: rir.SweptSineSignal, channels: int, out_ch, ref_out_ch):
    sig = sig.signal_vector()[1]

    # amp = max((abs(sig.max()), abs(sig.min())))
    # sig /= amp

    length = 2**20 + len(sig) + 2**19
    out_data = np.zeros(shape=(channels, length), dtype=float)

    out_data[out_ch][2**20:2**20 + sig.shape[0]] = sig
    out_data[ref_out_ch][2**20:2**20 + sig.shape[0]] = sig

    return out_data.T
