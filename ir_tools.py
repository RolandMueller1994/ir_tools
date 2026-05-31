from argparse import ArgumentParser
from pathlib import Path
from scipy.io import wavfile
import matplotlib.pyplot as plt
import shutil

from signals.stimuli import create_chirp
from signals.ir import plot_spectrum, apply_ir


def test(length: int, fs: int, f_start, f_end, f: Path, out_dir: Path):

    wav = wavfile.read(str(f))
    if wav[0] != fs:
        raise ValueError('File has incorrect sampling frequency. File and specified fs must match!')

    ir = wav[1]
    plot_spectrum(ir, fs, out_dir / 'ir_spectrum.png')

    t, sig = create_chirp(length, fs, f_start, f_end, out_dir / 'chirp.wav')

    plt.figure()
    plt.plot(t, sig)
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

    args = arg_parser.parse_args()

    out_dir = Path(__file__).parent / 'results'
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == 'test':
        test(args.length, args.fs, args.f_start, args.f_stop, args.file, out_dir)