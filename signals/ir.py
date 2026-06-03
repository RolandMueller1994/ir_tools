import numpy as np
import matplotlib.pyplot as plt
from typing import Union
from pathlib import Path

import scipy
from scene_rir import rir
from scipy.io import wavfile
import math
import pyfar as pf


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
    z = 1 / (1 + np.exp((-1 if rising else 1) * x / width * 16))

    return z


def create_window(start_offset, length, fade_out=0.1):
    window = np.ones(shape=length)
    fade_in = sigmoid(start_offset, rising=True)
    fade_out_length = int(length * fade_out)
    fade_out = sigmoid(fade_out_length, rising=False)
    window[0:start_offset] = fade_in
    window[-fade_out_length:] = fade_out

    return window


def get_f_index(f, f_start=20, f_stop=20):
    i_start = None
    i_stop = None

    for i, val in enumerate(f):
        if val > f_start and i_start is None:
            i_start = i
        if val > f_stop and i_stop is None:
            i_stop = i

    if i_start is None:
        i_start = f[0]
    if i_stop is None:
        i_stop = f[-1]

    return i_start, i_stop


def plot_spectrum(signal: np.ndarray, fs, outfile: Union[Path, None] = None, title: str = None,
                  show_plots: bool = False, f_start: int = 20, f_stop: int=20e3):
    spect = np.fft.fft(signal)
    idx = spect.shape[0] // 2

    f = np.linspace(0, idx, idx) * fs / 2 / idx

    i_start, i_stop = get_f_index(f, f_start, f_stop)

    amp = 20 * np.log10(np.abs(spect[0:idx]))
    phase = np.angle(spect[0:idx]) / math.pi * 180
    amp -= amp.max()

    plt.figure()
    plt.plot(f[i_start:i_stop], amp[i_start:i_stop])
    plt.xscale('log')
    y_max = amp[i_start:i_stop].max()
    y_min = amp[i_start:i_stop].min()
    if y_max - y_min > 60:
        y_min = y_max - 60
    plt.ylim(y_min - 5, y_max + 5)
    plt.xlabel('Frequency [Hz]')
    plt.ylabel('Amplitude [dB]')
    plt.title('Spectrum' if title is None else title)
    if outfile is not None:
        plt.savefig(outfile, dpi=300)
    if show_plots:
        plt.show()

    return f[i_start:i_stop], amp[i_start:i_stop], phase[i_start: i_stop]


def invert_response(ir: np.ndarray, fs):
    sig = pf.Signal(ir, fs)
    sig = pf.dsp.minimum_phase(sig, truncate=True)
    target = pf.dsp.filter.butterworth(pf.signals.impulse(sig.n_samples, sampling_rate=fs), 4, [20, 20e3], 'bandpass')
    regularization = pf.dsp.filter.low_shelf(
        pf.signals.impulse(sig.n_samples, sampling_rate=fs), 18e3, -40, 2, 'II')
    inv = pf.dsp.RegularizedSpectrumInversion.from_magnitude_spectrum(sig, regularization, beta=0.1, target=target)
    inverted: pf.Signal = inv.invert
    return inverted.time


def calibrate_rec(data: np.ndarray, calibration_ir: Path, fs: int, ref_in_ch: int, show_plots: bool = False,
                  output_dir: Union[Path, None] = None, suffix: Union[None, str] = None):
    ir = wavfile.read(str(calibration_ir))
    fs_ir = ir[0]
    ir = ir[1]

    if ir is not None and fs != fs_ir:
        raise ValueError('Calibration IR and recording must have same sampling rate!')

    spectrum = np.fft.fft(ir)
    spectrum /= np.abs(spectrum).max()

    inv_ir = invert_response(ir, fs)[0]
    inv_ir = np.real(inv_ir)

    if show_plots:
        plt.figure()
        plt.plot(abs(inv_ir))
        plt.show()
        spectrum_size = spectrum.shape[0] // 2
        f = np.linspace(0, fs / 2, spectrum_size)
        plt.figure()
        plt.plot(f, 20 * np.log10(np.abs(spectrum[:spectrum_size])), label='Original')
        inv_spectrum = np.fft.fft(inv_ir)
        f = np.linspace(0, fs / 2, inv_spectrum.shape[0] // 2)
        plt.plot(f, 20 * np.log10(np.abs(inv_spectrum[:inv_spectrum.shape[0] // 2])), label='Inverted')
        plt.xlabel('Frequency [Hz]')
        plt.ylabel('Amplitude [dB]')
        plt.xscale('log')
        plt.xlim(1, 20e3)
        plt.legend()
        plt.tight_layout()
        plt.show()

        plt.figure()
        plt.plot(f, np.angle(inv_spectrum[:inv_spectrum.shape[0] // 2]) / math.pi * 180)
        plt.xscale('log')
        plt.xlim(1, 20e3)
        plt.xlabel('Frequency [Hz]')
        plt.ylabel('Phase [Deg]')
        plt.show()

    inv_ir /= max(abs(inv_ir))
    if output_dir is not None:
        if suffix is None:
            file_name = 'ir_correction.wav'
        else:
            file_name = f'ir_correction_{suffix}.wav'
        wavfile.write(output_dir / file_name, fs, inv_ir)
    out_data = None
    for ch in range(data.shape[0]):
        if ch == ref_in_ch:
            filtered = data[ch]
        else:
            filtered = scipy.signal.convolve(data[ch], inv_ir, mode='full')[:data.shape[1]]
        if out_data is None:
            out_data = np.zeros(shape=(data.shape[0], filtered.shape[0]))
        out_data[ch] = filtered
    return out_data
