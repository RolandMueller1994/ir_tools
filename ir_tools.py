from argparse import ArgumentParser
from pathlib import Path
from typing import List

import scipy
from scipy.io import wavfile
from scipy.signal import correlate
import numpy as np
import matplotlib.pyplot as plt
import shutil
import re

from signals.stimuli import create_chirp, write_wav, create_output_data
from signals.ir import plot_spectrum, apply_ir, calc_ir, create_window

import sounddevice as sd


def record(device_id: int, out_ch: int, ref_out_ch: int, ref_in: int, rec_ch: List[int], fs: int, f_start: int,
           f_end: int, output_dir: Path, trim_ir: bool = False, shape_ir: bool = False,
               start_offset: int = 32, ir_length: int = 2**13, fade_out: float = 0.1):
    dev = sd.query_devices()[device_id]
    sd.default.device = dev['name']

    channels = min(32, dev['max_input_channels'], dev['max_output_channels'])
    if channels == 0:
        raise ValueError(f'Device has to have input and output channels. Device {str(dev)}')
    print(f'Using {channels} channels')

    if ref_out_ch >= channels or out_ch >= channels or ref_in >= channels or max(rec_ch) >= channels:
        raise ValueError('Channel range exceeded!')

    if ref_out_ch < 0 or out_ch < 0 or ref_in < 0 or min(rec_ch) < 0:
        raise ValueError('Channel selection can\'t be negative!')

    sd.default.samplerate = fs
    sd.default.channels = channels

    sig = create_chirp(fs, f_start, f_end, outfile=output_dir / 'stimuli.wav')

    stim = create_output_data(sig, channels, out_ch, ref_out_ch)
    rec = sd.playrec(stim, fs, channels, blocking=True).T[...,2**20:]

    ref_in_data = rec[ref_in]
    ref_out_data = stim.T[ref_out_ch][2**20:]
    corr = scipy.signal.correlate(ref_in_data, ref_out_data, mode='same')

    corr_max = abs(corr.max())
    corr_min = abs(corr.min())

    # Recording might be inverted. If so, correlation point would be a negative value.
    if corr_max > corr_min:
        offset = np.argmax(corr)
    else:
        offset = np.argmin(corr)
    offset -= ref_in_data.shape[0] // 2 + start_offset
    print(f'Offset {offset}')

    output_file = output_dir / f'reference.wav'
    wavfile.write(output_file, fs, ref_in_data)


    for ch in rec_ch:
        plt.figure()
        rec_data = rec[ch][offset:]
        t = np.linspace(0, rec_data.shape[0] * 1 / fs, rec_data.shape[0])
        plt.plot(t, rec_data)
        plt.title(f'Channel {ch} Signal')
        plt.xlabel('Time [s]')
        plt.ylabel('Amplitude')
        plt.show()

        output_file = output_dir / f'channel_{ch}.wav'
        wavfile.write(output_file, fs, rec[ch][offset:])
        ir = calc_ir(output_dir / 'stimuli.wav', output_file, f_start, f_end)

        if trim_ir:
            length = ir_length
        else:
            length = ir.signal_vector()[1].shape[0]

        ir_vector = ir.signal_vector()[1][:length]

        if shape_ir:
            window = create_window(start_offset, length, fade_out)
            window_t = np.linspace(0, length, length) * 1/fs
            plt.figure()
            plt.plot(window_t, window)
            plt.xlabel('Time [s]')
            plt.ylabel('Amplitude')
            plt.title(f'Window Channel {ch}')
            plt.show()
            ir_vector *= window

        wavfile.write(output_dir / f'ir_channel_{ch}.wav', fs, ir_vector)

        plot_spectrum(ir.signal_vector()[1], fs, outfile=output_dir / f'spectrum_{ch}.png',
                      title=f'Spectrum channel {ch}', show_plots=True)

def test(fs: int, f_start, f_end, f: Path, out_dir: Path, show_plots=False):
    wav = wavfile.read(str(f))
    if wav[0] != fs:
        raise ValueError('File has incorrect sampling frequency. File and specified fs must match!')

    ir = wav[1]

    f, spec_orig = plot_spectrum(ir, fs, out_dir / 'ir_spectrum.png', title='Impulse Response Spectrum Original',
                                 show_plots=show_plots)

    sig = create_chirp(fs, f_start, f_end, out_dir / 'chirp.wav')

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

    check_ir = calc_ir(out_dir / 'chirp.wav', out_dir / 'response.wav', f_start, f_end)
    check_ir.save(out_dir / 'ir_calc.wav')
    f_calc, spec_calc = plot_spectrum(check_ir.signal_vector()[1][0:ir.shape[0]], fs, out_dir / 'ir_spectrum_calc.png',
                                      title='Impulse Response Spectrum Calculated', show_plots=show_plots)

    spec_diff = spec_calc - spec_orig
    plt.figure()
    plt.plot(f, spec_orig, label='Original')
    plt.plot(f, spec_calc, label='Calculated')
    plt.xscale('log')
    plt.legend()
    plt.ylabel('Amplitude [dB]')
    plt.xlabel('Frequency [Hz]')
    plt.tight_layout()
    plt.savefig(out_dir / 'spectrum_comparison.png', dpi=300)
    if show_plots:
        plt.show()

    plt.figure()
    plt.plot(f, spec_diff)
    plt.xscale('log')
    plt.ylabel('Amplitude Difference [dB]')
    plt.xlabel('Frequency [Hz]')
    plt.ylim(-10, 10)
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
    arg_parser.add_argument('--f_start', type=int, help='The starting frequency of the log-sine in Hz', default=20, required=False)
    arg_parser.add_argument('--f_stop', type=int, help='The ending frequency of the log-sine in Hz', default=20000, required=False)

    subparsers = arg_parser.add_subparsers(dest='mode', help='Mode selection', required=True)

    test_mode_parser = subparsers.add_parser('test', help='Test mode')
    test_mode_parser.add_argument('--file', type=Path,
                                  help='An impulse response wave-file. File fs must match parameter fs',
                                  default=Path(__file__).parent / Path('testdata/ir.wav'), required=False)
    test_mode_parser.add_argument('--show_plots', action='store_true', default=False, required=False)

    rec_mode_parser = subparsers.add_parser('record', help='Record mode')
    rec_mode_parser.add_argument('device_id', type=int, help='The device id of the recording device')
    rec_mode_parser.add_argument('output_channel', type=int, help='The output channel of the recording device')
    rec_mode_parser.add_argument('reference_output_channel', type=int, help='The reference output channel of the recording device')
    rec_mode_parser.add_argument('reference_input_channel', type=int, help='The reference input channel of the recording device')
    rec_mode_parser.add_argument('record_channels', type=lambda val: check_rec_channels(val, arg_parser), help='A list of input channels that should be recorded')
    rec_mode_parser.add_argument('--trim_ir', action='store_true', default=False, help='Trim the IR signal to length')
    rec_mode_parser.add_argument('--shape_ir', action='store_true', default=False, help='Shape the IR signal by fade-in and fade-out')
    rec_mode_parser.add_argument('--fade_out', type=float, help='Relative length of fade-out', default=0.1, required=False)
    rec_mode_parser.add_argument('--start_offset', type=int, help='The number of samples before the start of the IR', default=32, required=False)
    rec_mode_parser.add_argument('--ir_length', type=int, help='The length of the IR in samples', default=8192, required=False)


    args = arg_parser.parse_args()

    if args.f_start < 1:
        raise ValueError('f_start must be greater than 0')
    if args.f_stop > args.fs // 2:
        raise ValueError('f_stop must be less than fs/2')
    if args.f_start > args.f_stop:
        raise ValueError('f_start must be less than f_stop')

    if args.start_offset < 0:
        raise ValueError('start_offset must be greater than 0')

    out_dir = Path(__file__).parent / 'results'
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == 'test':
        test(args.fs, args.f_start, args.f_stop, args.file, out_dir, args.show_plots)
    elif args.mode == 'record':
        record(args.device_id, args.output_channel, args.reference_output_channel, args.reference_input_channel,
               args.record_channels, args.fs, args.f_start, args.f_stop, out_dir, args.trim_ir, args.shape_ir,
               args.start_offset, args.ir_length, args.fade_out)
    else:
        raise ValueError('Invalid mode')
