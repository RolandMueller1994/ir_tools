import numpy as np
import matplotlib.pyplot as plt
from typing import Union
from pathlib import Path

import scipy
from scene_rir import rir
from scipy.io import wavfile
import math
import pyfar


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

def get_f_index(f):
    i_20 = None
    i_20k = None

    for i, val in enumerate(f):
        if val > 20 and i_20 is None:
            i_20 = i
        if val > 20e3 and i_20k is None:
            i_20k = i
    return i_20, i_20k


def plot_spectrum(signal: np.ndarray, fs, outfile: Union[Path, None]=None, title: str=None, show_plots: bool=False):
    spect = np.fft.fft(signal)
    idx = spect.shape[0]//2

    f = np.linspace(0, idx, idx) * fs / 2/ idx

    i_20, i_20k = get_f_index(f)

    amp = 20 * np.log(np.abs(spect[0:idx]))
    phase = np.angle(spect[0:idx])/math.pi * 180
    amp -= amp.max()

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

    return f[i_20:i_20k], amp[i_20:i_20k], phase[i_20: i_20k]


def calibrate_rec(data: np.ndarray, calibration_ir: Path, calibration_ref_ir: Path, fs: int, ref_in_ch: int, show_plots: bool = False):
    if calibration_ir is not None:
        ir = wavfile.read(str(calibration_ir))
        fs_ir = ir[0]
        ir = ir[1]
    else:
        ir = None
        fs_ir = None
    if calibration_ref_ir is not None:
        ir_ref = wavfile.read(str(calibration_ref_ir))
        fs_ir_ref = ir_ref[0]
        ir_ref = ir_ref[1]
        ir_ref = scipy.signal.minimum_phase(ir_ref)
    else:
        ir_ref = None
        fs_ir_ref = None

    if ir is not None and ir_ref is not None:
        if ir.max() > abs(ir.min()):
            offset_ir = np.argmax(ir)
        else:
            offset_ir = np.argmin(ir)

        if ir_ref.max() > abs(ir_ref.min()):
            offset_ir_ref = np.argmax(ir_ref)
        else:
            offset_ir_ref = np.argmin(ir_ref)

        if offset_ir_ref < offset_ir:
            shift_val = offset_ir - offset_ir_ref
            if shift_val != 0:
                ir[0:-shift_val] = ir[shift_val:]
        else:
            shift_val = offset_ir_ref - offset_ir
            if shift_val != 0:
                ir_ref[0:-shift_val] = ir_ref[shift_val:]

    if ir is not None and fs != fs_ir:
        raise ValueError('Calibration IR and recording must have same sampling rate!')
    if ir_ref is not None and fs != fs_ir_ref:
        raise ValueError('Calibration reference IR and recording must have same sampling rate!')

    if ir is not None:
        spectrum = np.fft.fft(ir)
        spectrum /= np.abs(spectrum).max()
    else:
        spectrum = None
    if ir_ref is not None:
        spectrum_ref = np.fft.fft(ir_ref)
    elif spectrum is not None:
        spectrum_ref = np.ones_like(spectrum)
    else:
        spectrum_ref = None

    if spectrum_ref is not None and spectrum is None:
        spectrum = np.ones_like(spectrum_ref)

    if spectrum is not None and spectrum_ref is not None:
        inv_ir = np.fft.ifft(spectrum_ref/spectrum)
    elif spectrum is not None:
        inv_ir = np.fft.ifft(1/spectrum)
    else:
        inv_ir = np.fft.ifft(spectrum_ref)
    # inv_ir = np.fft.ifft(spectrum_ref * np.conjugate(spectrum) / (np.abs(spectrum) ** 2 + 10**(-20/20)))
    inv_ir = np.real(inv_ir)


    if show_plots and spectrum is not None and spectrum_ref is not None:
        plt.figure()
        plt.plot(abs(inv_ir))
        plt.show()
        spectrum_size = spectrum.shape[0] // 2
        f = np.linspace(0, fs/2, spectrum_size)
        i_20, i_20k = get_f_index(f)
        plt.figure()
        plt.plot(f, 20*np.log10(np.abs((spectrum/spectrum_ref)[:spectrum_size])), label='Original')
        inv_spectrum = np.fft.fft(inv_ir)
        plt.plot(f, 20*np.log10(np.abs(inv_spectrum[:spectrum_size])), label='Inverted')
        plt.xlabel('Frequency [Hz]')
        plt.ylabel('Amplitude [dB]')
        plt.xscale('log')
        plt.xlim(1, 20e3)
        plt.legend()
        plt.tight_layout()
        plt.show()

        plt.figure()
        plt.plot(f, np.angle(inv_spectrum[:spectrum_size])/math.pi * 180)
        plt.xscale('log')
        plt.xlim(1, 20e3)
        plt.show()

    inv_ir = np.concat((inv_ir[-128:], inv_ir[:-128]))
    inv_ir /= max(abs(inv_ir))
    wavfile.write('/home/roland/Projects/ir_tools/results/ir_correction.wav', fs, inv_ir)
    out_data = None
    for ch in range(data.shape[0]):
        if ch == ref_in_ch:
            filtered = data[ch]
        else:
            filtered = scipy.signal.convolve(data[ch], inv_ir, mode='full')[:data.shape[1]]
        # filtered = scipy.signal.deconvolve(data[ch], ir[1])[0]
        if out_data is None:
            out_data = np.zeros(shape=(data.shape[0], filtered.shape[0]))
        out_data[ch] = filtered
    return out_data
