import math

import json
from argparse import ArgumentParser
from pathlib import Path
from typing import List, Union

import scipy
from scipy.io import wavfile
from scipy.signal import correlate
import numpy as np
import matplotlib.pyplot as plt
import shutil
import re

from signals.stimuli import create_chirp, write_wav, create_output_data
from signals.ir import plot_spectrum, apply_ir, calc_ir, create_window, calibrate_rec

import sounddevice as sd


def _check_freq(fs: int, f_start, f_stop):
    if fs not in [44100, 48000]:
        raise ValueError('Sampling frequency must be 44100 or 48000!')
    if f_start < 1:
        raise ValueError('Start frequency must be greater than 0!')
    if f_stop >= fs // 2:
        raise ValueError('Stop frequency must be less than fs/2!')
    if f_start >= f_stop:
        raise ValueError('Start frequency must be less than stop frequency!')


def record(device_id: int, out_ch: int, ref_out_ch: int, ref_in: int, rec_ch: List[int], fs: int, f_start: int,
           f_end: int, level: float, output_dir: Path, trim_ir: bool = False, shape_ir: bool = False,
           start_offset: int = 32, ir_length: int = 2 ** 13, fade_out: float = 0.1, show_plots: bool = False,
           postfix: Union[str, None] = None, calibrate: Union[Path, None] = None, calibrate_ref: Union[Path, None] = None):
    _check_freq(fs, f_start, f_end)

    if level > 0:
        raise ValueError('Level should be less than or equal to 0 dB. 0 db would be full-scale output.')

    devices = sd.query_devices()
    if device_id >= len(devices):
        raise ValueError(f'Device {device_id} does not exist!')
    dev = devices[device_id]

    print(f'Using device: {str(json.dumps(dev, indent=4))}')

    sd.default.device = dev['name']

    channels = min(32, dev['max_input_channels'], dev['max_output_channels'])
    if channels == 0:
        raise ValueError(f'Device has to have input and output channels. Device {str(dev)}')
    print(f'Number of channels: {channels}')

    if ref_out_ch >= channels or out_ch >= channels or ref_in >= channels or max(rec_ch) >= channels:
        raise ValueError('Channel range exceeded!')

    if ref_out_ch < 0 or out_ch < 0 or ref_in < 0 or min(rec_ch) < 0:
        raise ValueError('Channel selection can\'t be negative!')

    sd.default.samplerate = fs
    sd.default.channels = channels

    if shape_ir:
        if start_offset < 0:
            raise ValueError('Start offset can\'t be negative!')

        if fade_out < 0 or fade_out > 1:
            raise ValueError('Fade out value must be between 0 and 1!')

    sig = create_chirp(fs, f_start, f_end, outfile=output_dir / 'stimuli.wav', level=level).signal_vector()[1]
    # sig = wavfile.read(Path('/home/roland/Projects/ir_tools/testdata/rew_stimuli_2.wav'))[1].astype(float)
    #sig /= max(sig.max(), abs(sig.min()))
    #sig *= 10**(level/20)

    stim = create_output_data(sig, channels, out_ch, ref_out_ch)
    print(f'Recording exponential sine-sweep of {stim.shape[0] * 1 / fs:.2f}s length.')
    rec = sd.playrec(stim, fs, channels, blocking=True).T[..., 2 ** 20:]

    if calibrate is not None or calibrate_ref is not None:
        rec = calibrate_rec(rec, calibrate, calibrate_ref, fs, ref_in, show_plots)

    ref_in_data = rec[ref_in] / (max(rec[ref_in].max(), abs(rec[ref_in].min())))
    ref_out_data = stim.T[ref_out_ch][2 ** 20:]
    corr = scipy.signal.correlate(ref_in_data, ref_out_data, mode='same')

    corr_max = abs(corr.max())
    corr_min = abs(corr.min())

    # Recording might be inverted. If so, correlation point would be a negative value.
    if corr_max > corr_min:
        offset = np.argmax(corr)
        inverted = False
    else:
        offset = np.argmin(corr)
        inverted = True
    offset -= ref_in_data.shape[0] // 2 + start_offset
    print(f'Removing initial offset from data: {offset} samples / {offset * 1 / fs * 1000:.2f}ms')

    output_file = output_dir / f'reference.wav'
    wavfile.write(output_file, fs,
                  (ref_in_data * (-1 if inverted else 1))[offset:offset + sig.shape[0]])

    if postfix is None:
        postfix = ''
    elif not postfix.startswith('_'):
        postfix = '_' + postfix

    for ch in [ref_in] + rec_ch:
        print(f'Analyzing data for channel {ch}')
        plt.figure()
        rec_data = (rec[ch] / max(rec[ch].max(), abs(rec[ch].min())))[offset:]
        t = np.linspace(0, rec_data.shape[0] * 1 / fs, rec_data.shape[0])
        if show_plots:
            plt.plot(t, rec_data)
            plt.title(f'Channel {ch} Signal')
            plt.xlabel('Time [s]')
            plt.ylabel('Amplitude')
            plt.show()

        output_file = output_dir / f'channel_{ch}{postfix}.wav'
        wavfile.write(output_file, fs, rec_data)
        ir = calc_ir(output_dir / 'stimuli.wav', output_file, f_start, f_end)

        if trim_ir:
            length = ir_length
        else:
            length = ir.signal_vector()[1].shape[0]

        if start_offset >= length:
            raise ValueError('Start offset can\'t be greater than the length of the IR!')
        if length >= ir.signal_vector()[1].shape[0]:
            raise ValueError('Specified ir_length is greater than the actual length of the IR!')

        ir_vector = ir.signal_vector()[1][:length]

        if shape_ir:
            window = create_window(start_offset, length, fade_out)
            window_t = np.linspace(0, length, length) * 1 / fs
            if show_plots:
                plt.figure()
                plt.plot(window_t, window)
                plt.xlabel('Time [s]')
                plt.ylabel('Amplitude')
                plt.title(f'Window Channel {ch}')
                plt.show()
            ir_vector *= window

        ir_file = output_dir / f'ir_channel_{ch}{postfix}.wav'
        wavfile.write(ir_file, fs, ir_vector)
        print(f'Recording written to: {output_file}')
        print(f'Impulse response written to: {ir_file}')

        plot_spectrum(ir.signal_vector()[1], fs, outfile=output_dir / f'spectrum_{ch}{postfix}.png',
                      title=f'Spectrum channel {ch}', show_plots=show_plots)


def test(fs: int, f_start: int, f_stop: int, f: Path, out_dir: Path, show_plots=False):
    _check_freq(fs, f_start, f_stop)

    if not f.exists():
        raise ValueError(f'Input file {f} does not exist!')
    elif not f.is_file():
        raise ValueError(f'Input file {f} is not a file!')
    elif f.suffix not in ['.wav', 'wave']:
        raise ValueError('Input wave file have suffix .wav or .wave')

    wav = wavfile.read(str(f))
    if wav[0] != fs:
        raise ValueError('File has incorrect sampling frequency. File and specified fs must match!')

    ir = wav[1]

    f, spec_orig, phase_orig = plot_spectrum(ir, fs, out_dir / 'ir_spectrum.png', title='Impulse Response Spectrum Original',
                                 show_plots=show_plots)

    sig = create_chirp(fs, f_start, f_stop, out_dir / 'chirp.wav')

    plt.figure()
    plt.plot(sig.time_vector(), sig.signal_vector()[1])
    plt.xlabel('Time [s]')
    plt.ylabel('Amplitude')
    plt.title('Chirp')
    plt.savefig(out_dir / 'chirp.png', dpi=300)
    if show_plots:
        plt.show()

    out_sig = apply_ir(ir, sig.signal_vector()[1])
    write_wav(out_dir / 'response.wav', out_sig, fs)

    check_ir = calc_ir(out_dir / 'chirp.wav', out_dir / 'response.wav', f_start, f_stop)
    check_ir.save(out_dir / 'ir_calc.wav')
    f_calc, spec_calc, phase_calc = plot_spectrum(check_ir.signal_vector()[1][0:ir.shape[0]], fs, out_dir / 'ir_spectrum_calc.png',
                                      title='Impulse Response Spectrum Calculated', show_plots=show_plots)

    spec_diff = spec_calc - spec_orig
    fig, ax1 = plt.subplots()
    ax1.plot(f, spec_orig, label='Amplitude Original')
    ax1.plot(f, spec_calc, label='Amplitude Calculated')
    ax1.set_xscale('log')
    ax1.set_ylabel('Amplitude [dB]')
    ax1.set_xlabel('Frequency [Hz]')
    ax1.set_ylim(-70, 5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / 'spectrum_comparison.png', dpi=300)
    if show_plots:
        plt.show()

    fig, ax1 = plt.subplots()
    line1 = ax1.plot(f, spec_diff, label='Amplitude Difference')
    ax1.set_xscale('log')
    ax1.set_ylabel('Amplitude Difference [dB]')
    ax1.set_xlabel('Frequency [Hz]')
    ax1.set_ylim(-0.5, 0.5)
    ax2 = ax1.twinx()
    line2 = ax2.plot(f, phase_calc - phase_orig, label='Phase Difference', color='orange')
    ax2.set_ylim(-1, 1)
    ax2.set_ylabel('Phase Difference [deg]')
    ax2.legend(handles=line1 + line2)
    plt.tight_layout()
    plt.savefig(out_dir / 'spectrum_difference.png', dpi=300)
    if show_plots:
        plt.show()


def check_rec_channels(val: str, parser):
    pattern = re.compile(r'\[((?:\s*\d+\s*,?)+\s*)]')
    match = re.match(pattern, val)
    if not match:
        parser.error('List is not matching required pattern. Should be in the format "[1, 3, 5]"')
    lst = match.group(1).replace(' ', '').replace('\t', '').split(',')
    return [int(i) for i in lst]


if __name__ == '__main__':
    arg_parser = ArgumentParser()
    arg_parser.add_argument('--fs', type=int, help='The sampling frequency in Hz', default=48000, required=False)
    arg_parser.add_argument('--f_start', type=int, help='The starting frequency of the log-sine in Hz', default=20,
                            required=False)
    arg_parser.add_argument('--f_stop', type=int, help='The ending frequency of the log-sine in Hz', default=20000,
                            required=False)
    arg_parser.add_argument('--output_dir', type=Path, help='The directory to store the output files', required=False,
                            default=Path(__file__).parent / 'results')
    arg_parser.add_argument('--show_plots', action='store_true', default=False, required=False, help='Display plots')

    subparsers = arg_parser.add_subparsers(dest='mode', help='Mode selection', required=True)

    test_mode_parser = subparsers.add_parser('test', help='Test mode')
    test_mode_parser.add_argument('--file', type=Path,
                                  help='An impulse response wave-file. File fs must match parameter fs',
                                  default=Path(__file__).parent / Path('testdata/ir.wav'), required=False)

    rec_mode_parser = subparsers.add_parser('record', help='Record mode')
    rec_mode_parser.add_argument('device_id', type=int, help='The device id of the recording device')
    rec_mode_parser.add_argument('output_channel', type=int, help='The output channel of the recording device')
    rec_mode_parser.add_argument('reference_output_channel', type=int,
                                 help='The reference output channel of the recording device')
    rec_mode_parser.add_argument('reference_input_channel', type=int,
                                 help='The reference input channel of the recording device')
    rec_mode_parser.add_argument('record_channels', type=lambda val: check_rec_channels(val, arg_parser),
                                 help='A list of input channels that should be recorded. Format: "[3, 4]"')
    rec_mode_parser.add_argument('--level', type=float, help='The output level during recording in dB', default=-20,
                                 required=False)
    rec_mode_parser.add_argument('--trim_ir', action='store_true', default=False, help='Trim the IR signal to length')
    rec_mode_parser.add_argument('--shape_ir', action='store_true', default=False,
                                 help='Shape the IR signal by fade-in and fade-out')
    rec_mode_parser.add_argument('--fade_out', type=float, help='Relative length of fade-out', default=0.1,
                                 required=False)
    rec_mode_parser.add_argument('--start_offset', type=int, help='The number of samples before the start of the IR',
                                 default=32, required=False)
    rec_mode_parser.add_argument('--ir_length', type=int, help='The length of the IR in samples', default=8192,
                                 required=False)
    rec_mode_parser.add_argument('--postfix', type=str, help='Postfix to be added to end of the file name',
                                 default=None, required=False)
    rec_mode_parser.add_argument('--calibrate', type=Path,
                                 help='Path to an impulse response used for calibration. This can be obtained from a measurement without a speaker/before a speaker.',
                                 default=None)
    rec_mode_parser.add_argument('--calibrate_ref', type=Path,
                                 help='Path to the impulse response of the reference channel used for calibration.',
                                 default=None)

    args = arg_parser.parse_args()

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == 'test':
        test(args.fs, args.f_start, args.f_stop, args.file, out_dir, args.show_plots)
    elif args.mode == 'record':
        record(args.device_id, args.output_channel, args.reference_output_channel, args.reference_input_channel,
               args.record_channels, args.fs, args.f_start, args.f_stop, args.level, out_dir, args.trim_ir,
               args.shape_ir, args.start_offset, args.ir_length, args.fade_out, args.show_plots, args.postfix,
               args.calibrate, args.calibrate_ref)
    else:
        raise ValueError('Invalid mode')
