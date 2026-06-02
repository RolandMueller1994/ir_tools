# ir_tools

Python command line tool to record speaker impulse responses from multiple channels.

## Prerequisites

The tool needs a Python environment with the correct libraries installed. 
Tests were executed with a conda environment using Python3.13 and these [requirements](conda_requirements.yaml).

To create a suiting Python environment install conda (e.g. [miniforge](https://github.com/conda-forge/miniforge)) first.
Afterwards, create the environment and activate it:

```shell
conda env create -n ir-tools -f conda_requirements.yaml
conda activate ir-tools
```

## CLI

General arguments: 
```shell
usage: ir_tools.py [-h] [--fs FS] [--f_start F_START] [--f_stop F_STOP] {test,record} ...

positional arguments:
  {test,record}      Mode selection
    test             Test mode
    record           Record mode

options:
  -h, --help         show this help message and exit
  --fs FS            The sampling frequency in Hz
  --f_start F_START  The starting frequency of the log-sine in Hz
  --f_stop F_STOP    The ending frequency of the log-sine in Hz
```

### Test Mode

```shell
usage: ir_tools.py test [-h] [--file FILE] [--show_plots]

options:
  -h, --help    show this help message and exit
  --file FILE   An impulse response wave-file. File fs must match parameter fs
  --show_plots
```

### Record Mode

```shell
usage: ir_tools.py record [-h] [--trim_ir] [--shape_ir] [--fade_out FADE_OUT] [--start_offset START_OFFSET] [--ir_length IR_LENGTH] device_id output_channel reference_output_channel reference_input_channel record_channels

positional arguments:
  device_id             The device id of the recording device
  output_channel        The output channel of the recording device
  reference_output_channel
                        The reference output channel of the recording device
  reference_input_channel
                        The reference input channel of the recording device
  record_channels       A list of input channels that should be recorded. Format: "[3, 4]"

options:
  -h, --help            show this help message and exit
  --trim_ir             Trim the IR signal to length
  --shape_ir            Shape the IR signal by fade-in and fade-out
  --fade_out FADE_OUT   Relative length of fade-out
  --start_offset START_OFFSET
                        The number of samples before the start of the IR
  --ir_length IR_LENGTH
                        The length of the IR in samples
```