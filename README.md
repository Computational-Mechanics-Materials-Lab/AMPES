# AMTech Script

**Authors**: David Failla, Matthew Dantin, CJ Nguyen, William Furr

This script reads in a RepRap gcode file and exports an event series for a laser path and a wiper/roller as a .inp for use with Abaqus. A process parameter record file for L-PBF is also created as a txt for documentation.
Event series generation can be leveraged for DED and WAAM as well. This script is intended to be used with Slic3r.

# Pipeline Architecture

*Architectural diagram for the intended pipeline from STL>GCode>EventSeries?*

# Requirements

Slic3r Version: 1.3

Python Version: 3.10

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

* `-i`, `--input_dir` Directs to the folder that contains gcode files that will be converted into an event series. If unspecified the script will search for these files in `<current working directory>/gcodes`
* `-c`, `--config` Directs to the YAML configuration file. This will attempt to load `<current working directory>/input.yaml` if unspecified. For setting up this file refer to [its corresponding section](#input-yaml).

**Output Arguments**

* `-d`, `--ouput_dir` Directs to the folder that will hold the event series output. Will create if necessary and populate a `<current working directory>/output` directory by default.
* `-o`, `--outfile_name` Specifies the base name for the output filename format. For further details refer to the [output files section](#outputs).

## Input YAML

AMTech interprets print parameters using a YAML format file with the following common parameters:

* `layer_height` \[`int`, `float`\]: the height to increase z value by between every layer in mm
* `roller` \[`boolean`\]: `true` if a separate roller event series should be generated, else `false`
* `process_param_request` \[`boolean`\]: `true` if process parameters used to generate the build should be outputted to the same output folder, else `false`
* `substrate` \[`float`\]: the height of the substrate in mm
* `output_request` \[`boolean`\]: `true` to output points based on the event series, else `false`
* `sample_point_count` \[`int`\]: the number of output points desired from scanning

### Input YAML Subsections

The following describes different sections of the input YAML file where variables directly relate to each other.

Simple example input YAML files configured for L-PBF event series output are provided at the root of this repository under `fgm_input_one_group.yaml` and `fgm_input_two_group.yaml`, which show the use for one set of parameters for a whole job and two groups for specific layers of a job respectively.

### Layer Groups

AMTech handles functionally graded material (FGM) printing using "layer groups" which are nested YAML variables that allow for the setting of print parameters for different sets of layers.

The parent `layer_groups` variable can contain a number of groups that configure how individual intervals of layers will be handled. An example of a `layer_groups` section configured for two groups of layers is shown below.

```yaml
layer_groups: 
  group_one:
    layers: [1, 95]
    infill:
      scan_speed: 1000
      laser_power: 4000000
    contour:
      scan_speed: 500
      laser_power: 2000000
    interlayer_dwell: 10.0
  group_two:
    layers: [96, 128]
    infill:
      scan_speed: 1000
      laser_power: 2000000
    contour:
      scan_speed: 500
      laser_power: 1000000
    interlayer_dwell: 10.0
```

The group names are irrelevant to the functionality of AMTech and for the purpose of example the groups are named `group_one` and `group_two`. Each group should have a `layers` variable containing a continuous interval of layers which should be included within the group. AMTech treats the interval as an inclusive interval and treats the layers as starting with one rather than zero.

Both the `infill` and `contour` sections of each layer group section will require a `scan_speed` and `laser_power` variable that dictates the values in mm/s and Watts respectively for that section.

The `interlayer_dwell` variable sets the amount of time in seconds waited for between layers until the next section starts printing. This variable is ignored if the general `in_situ_dwell` boolean variable is set to `false`.

If one wishes to set print parameters for an entire job and not for specific sections of the print, the user can specify a single layer group with no `layers` variable. Single groups with an included `layers` interval can still be used to print specific layer intervals with set print parameters.

### Dwell

The following parameters relate to dwell time. 

* `in_situ_dwell` \[`boolean`\]: set to `false` to ignore the in-situ dwell times provided by `interlayer_dwell` and `w_dwell`
* `heatup_time` \[`int`, `float`\]: the initial dwell time that will be added to the start of the build
* `w_dwell` \[`int`, `float`\]: the amount of time it takes for the roller to finish laying down material for the next layer
* `interval` \[`int`\]: the number of points to interpolate between start and end points within the gcode
* 
Regardless of value, all variables relating to dwell time are ignored if the `in_situ_dwell` variable is set to `false` and the event series will be generated assuming that all dwell-related variables are set to the value 0.

### Origin Shift

The following three variables can be used if the event series origin should be offset from the mesh's origin. If no shifting is required, set the values of these to 0.

* `xorg_shift` \[`int`, `float`\]
* `yorg_shift` \[`int`, `float`\]
* `zorg_shift` \[`int`, `float`\]

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