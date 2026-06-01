from argparse import ArgumentParser
from pathlib import Path
from scipy.io import wavfile
import matplotlib.pyplot as plt
import shutil

from signals.stimuli import create_chirp, write_wav
from signals.ir import plot_spectrum, apply_ir, calc_ir


def test(length: int, fs: int, f_start, f_end, f: Path, out_dir: Path, show_plots=False):
    wav = wavfile.read(str(f))
    if wav[0] != fs:
        raise ValueError('File has incorrect sampling frequency. File and specified fs must match!')

    ir = wav[1]

    f, spec_orig = plot_spectrum(ir, fs, out_dir / 'ir_spectrum.png', title='Impulse Response Spectrum Original',
                                 show_plots=show_plots)

    sig = create_chirp(length, fs, f_start, f_end, out_dir / 'chirp.wav')

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

    check_ir = calc_ir(out_dir / 'chirp.wav', out_dir / 'response.wav')
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
    plt.tight_layout()
    plt.savefig(out_dir / 'spectrum_difference.png', dpi=300)
    if show_plots:
        plt.show()


if __name__ == '__main__':
    arg_parser = ArgumentParser()
    arg_parser.add_argument('length', type=int, help='The length of the log-sine in samples')
    arg_parser.add_argument('fs', type=int, help='The sampling frequency in Hz')
    arg_parser.add_argument('f_start', type=int, help='The starting frequency of the log-sine in Hz')
    arg_parser.add_argument('f_stop', type=int, help='The ending frequency of the log-sine in Hz')

    subparsers = arg_parser.add_subparsers(dest='mode', help='Mode selection', required=True)

    test_mode_parser = subparsers.add_parser('test', help='Test mode')
    test_mode_parser.add_argument('--file', type=Path,
                                  help='An impulse response wave-file. File fs must match parameter fs',
                                  default=Path(__file__).parent / Path('testdata/ir.wav'), required=False)
    test_mode_parser.add_argument('--show_plots', action='store_true', default=False, required=False)

    args = arg_parser.parse_args()

    out_dir = Path(__file__).parent / 'results'
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == 'test':
        test(args.length, args.fs, args.f_start, args.f_stop, args.file, out_dir, args.show_plots)
