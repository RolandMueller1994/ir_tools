import numpy as np
import matplotlib.pyplot as plt
from typing import Union
from pathlib import Path
from scene_rir import rir


def apply_ir(ir: np.ndarray, signal: np.ndarray):
    return np.convolve(signal, ir, mode='full')


def calc_ir(stimuli_path: Path, recorded_path: Path, f_start, f_stop):
    params = {
        'rec_path': str(recorded_path),
        'ref_path': str(stimuli_path),
        'frqstt': f_start,
        'frqstp': f_stop,
    }
    irs = rir.ImpulseResponseSignal(params, sgllvl=0)
    return irs


def sigmoid(width: int, rising=True):

    x = np.linspace(-width // 2, width // 2, width)
    z = 1 / (1 + np.exp((-1 if rising else 1 ) * x / width * 16))

    return z

def create_window(start_offset, length, fade_out=0.1):
    window = np.ones(shape=length)
    fade_in = sigmoid(start_offset, rising=True)
    fade_out_length = int(length * fade_out)
    fade_out = sigmoid(fade_out_length, rising=False)
    window[0:start_offset] = fade_in
    window[-fade_out_length:] = fade_out

    return window


def plot_spectrum(signal: np.ndarray, fs, outfile: Union[Path, None]=None, title: str=None, show_plots: bool=False):
    spect = abs(np.fft.fft(signal))
    idx = spect.shape[0]//2

    f = np.linspace(0, idx, idx) * fs / 2/ idx

    i_20 = None
    i_20k = None

    for i, val in enumerate(f):
        if val > 20 and i_20 is None:
            i_20 = i
        if val > 20e3 and i_20k is None:
            i_20k = i

    amp = 20 * np.log(np.abs(spect[0:idx]))

    plt.figure()
    plt.plot(f[i_20:i_20k], amp[i_20:i_20k])
    plt.xscale('log')
    y_max = amp[i_20:i_20k].max()
    plt.ylim(y_max - 70, y_max + 5)
    plt.xlabel('Frequency [Hz]')
    plt.ylabel('Amplitude [dB]')
    plt.title('Spectrum' if title is None else title)
    if outfile is not None:
        plt.savefig(outfile, dpi=300)
    if show_plots:
        plt.show()

    return f[i_20:i_20k], amp[i_20:i_20k]
