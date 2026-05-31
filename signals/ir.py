import numpy as np
import matplotlib.pyplot as plt
from typing import Union
from pathlib import Path


def apply_ir(ir: np.ndarray, signal: np.ndarray):
    return np.convolve(signal, ir, mode='valid')


def plot_spectrum(signal: np.ndarray, fs, outfile: Union[Path, None]=None):
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
    plt.xlabel('Frequency [Hz]')
    plt.ylabel('Amplitude [dB]')
    plt.title('Impulse Response Spectrum')
    if outfile is not None:
        plt.savefig(outfile, dpi=300)
    plt.show()
