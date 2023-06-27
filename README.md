# AMTech Script

**Authors**: David Failla, Matthew Dantin, CJ Nguyen, William Furr

**Emails**: (fill with emails)

This script reads in a RepRap gcode file and exports an event series for a laser path and a wiper/roller as a .inp for use with Abaqus. A process parameter record file for L-PBF is also created as a txt for documentation.
Event series generation can be leveraged for DED and WAAM as well. This script is intended to be used with Slic3r.

# Pipeline Architecture

*Architectural diagram for the intended pipeline from STL>GCode>EventSeries?*

# Requirements

Slic3r Version: \<is this necessary?\>

Python Version: 3.9

Python Packages:

* NumPy
* PyYaml

Dependencies can be installed using the included `requirements.txt` file by executing the following line:

```
pip install -r requirements.txt
```

# Usage 

## STL to Slic3r RepRap GCode

**To be filled**

## AMTech Overview

AMTech comes with several command-line arguments to assist in both ease of use and customization per run. Use 

```
python src/AM_Tech.py --help
```

to have a summary of these arguments printed out.

**Input Arguments**

* `-i`, `--input_dir` Directs to the folder that contains gcode files that will be converted into an event series. By default the script will search for these files in `<current working directory>/gcodes`
* `-c`, `--config` Directs to the YAML configuration file. This will attempt to load `<current working directory>/input.yaml` by default. For details refer to [the corresponding section](#input-yaml).

**Output Arguments**

* `-d`, `--ouput_dir` Directs to the folder that will hold the event series output. Will create if necessary and populate a `<current working directory>/output` directory by default.
* `-o`, `--outfile_name` Specifies the base name for the output filename format. For details refer to the [output files section](#outputs).

## Input YAML

AMTech configures parameters using a YAML format file with the following parameters:

---
* `scan_speed` \[`int`, `float`\]: defines the speed at which the laser will travel in **UNITS**
* `laser_power` \[`int`, `float`\]: defines the power of the laser in Watts
* `FGM` \[`boolean`\]: `true` if input directory has multiple files to use for an FGM event series, else `false`
* `scan_speed_FGM` \[`array`\[`int`, `float`\]\]: **TO BE FILLED**
* `laser_power_FGM` \[`array`\[`int`, `float`\]\]: **TO BE FILLED**

* `interval` \[`int`\]: the number of points to interpolate between start and end points within the gcode
* `layer_height` \[`int`, `float`\]: the height to increase z value by between every layer in mm
* `i_dwell` \[`int`, `float`\]: the initial dwell time that will be added to the start of the build
* `w_dwell` \[`int`, `float`\]: the inter-layer dwell time that will be added at every layer jump
* `roller` \[`boolean`\]: `true` if a separate roller event series should be generated, else `false`
* `in_situ_dwell` \[`boolean`\]: set to `false` to ignore the in-situ dwell times provided by `i_dwell` and `w_dwell`
* `process_param_request` \[`boolean`\]: `true` if process parameters used to generate the build should be outputted to the same output folder, else `false`
* `substrate` \[`float`\]: the height of the substrate in mm
* `output_request` \[`boolean`\]: `true` to output points based on the event series, else `false`
* `sample_point_count` \[`int`\]: the number of output points desired from scanning

**The following three variables are used if the event series origin should be offset from the mesh's origin**

* `xorg_shift` \[`int`, `float`\]
* `yorg_shift` \[`int`, `float`\]
* `zorg_shift` \[`int`, `float`\]
---

A simple example input YAML file configured for a non-FGM L-PBF event series output is provided at the root of this repository under `example_input.yaml`.

**Fill out with more example input YAML files for use with DED and WAAM**

## Outputs

Files created by AMTech will output to the directory provided to the `output_dir` argument or `<current working directory>/output` otherwise.

The files will be named after the parameters provided in the configuration input YAML in the following format, along with the value provided to the `outfile_name` argument which defaults to `output` if none is provided. Files will be named at the root with `<outfile_name>_<w_dwell>_<layer_height>` which will be referred to as `filename_root` for the remainder of the document.

**Output Files**

* `<filename_root>.inp`: the main event series containing the laser path
* `<filename_root>_roller.inp`: the roller event series created only if the configuration variable `roller` is true
* `<filename_root>_process_parameter.csv`: a csv file containing process parameter values provided in the input YAML configuration along with a date-of-generation created only if the configuration variable `output_request` is true

# License

This software falls under the MIT License.