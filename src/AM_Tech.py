# Code Description
# This script reads in a RepRap gcode file and exports an event series for a laser path and a wiper/roller as a .inp
# for use with Abaqus. A process parameter record file for L-PBF is also created as a txt for documentation.
# Event series generation can be leveraged for DED and WAAM as well. This script is intended to be used with Slic3r.
#######################################################################################################################
# Written by:
# David Failla
# dpf39@msstate.edu
# dpf39@cavs.msstate.edu
#######################################################################################################################
# Edit history:
# 08/30/2021 original coding - David Failla
# 09/01/2021 modified paths and corrected .csv to .inp output - David Failla
# 09/13/2021 Added a feature that creates a list of time points for the end of each layer build - David Failla
# 10/18/2021 Added ability to create an event series from multiple input gcodes for FGM processing - David Failla
# 02/02/2022 Corrected wiper event series to be within the in-situ dwell time - David Failla
# 02/16/2022 General Clean up - David Failla
# 03/02/2022 Corrected issue with Dwell Time implementation - David Failla
# 03/07/2022 Added comments and simplified variables for clarity - David Failla
# 03/17/2022 Added feature for parts with a single or multiple gcodes and output time at the end of scan - David Failla
# 03/21/2022 Added feature to control output times for increments during scanning - David Failla
# 03/24/2022 Added Switches for outputs and fixed an error that was erasing X and Y values for scanning - David Failla
# 03/25/2022 Added more outputs to Output Process Parameter file and added comments - David Failla
# 10/22/2022 Corrected incrementation by replacing step with interval method for both FGM and non - David Failla
#######################################################################################################################
# Code Usage
# Begin by populating all process parameters with known variables. This code is built around its in-situ process
# parameter variation capability. If you are modeling a functionally graded material case, have this script look into
# a directory with only the required gcodes. Do this by specifying a gcodes file path. You will also need to define
# a working directory. By default, the working directory is the directory this code is run in and the code assumes a
# directory labeled "gcodes" is present.
#
# The process parameters not listed here that need to be input during gcode development in Slic3r are scan strategy and
# and hatch spacing. Layer height is accepted within this script, but it is expected to align with the Slic3r input.
# Lastly, if an FGM build is being modeled, all subsquent parts in the build direction must be offset with the
# z-offset feature within Slic3r for the event series of the stacked parts to align

# Import necessary packages
import csv
import datetime
import os
import argparse
import yaml
import numpy as np
import shutil
import math
import re
from itertools import chain
from sys import exit

# Argument Parsing 
cwd = os.getcwd()
parser = argparse.ArgumentParser(prog="AM Tech", description="Reads a RepRap gcode file and outputs Abaqus compatible .inp files based off of it.")
parser.add_argument("-i", "--input_dir", help="Folder that contains the gcode file(s), defaults to <current working dir>/gcodes", default=os.path.join(cwd, "gcodes"))
parser.add_argument("-c", "--config", help="Config input YAML that will be used to initialize parameters, defaults to <current working dir>/input.yaml", default=os.path.join(cwd, "input.yaml"))
parser.add_argument("-d", "--output_dir", help="Directory to output files to, defaults to <current working dir>/output", default=os.path.join(cwd, "output"))
parser.add_argument("-o", "--outfile_name", help="Basename for the files that will be outputted, defaults to \"output\"", default="output")

args = parser.parse_args()

def perturb(input_arr, dev, type='gaussian'):
    """
    # This is a function to perturb an array of values by a given amount. Currently supports a gaussian/normal
    # distribution with type='gaussian', a strict +/- with type='strict', and uniform with type='uniform'.
    :param input_arr: array or list of power values
    :param dev: deviation to add or subtract from the laser power
    :param type: type of perturbation. options are gaussian/normal distribution around the dev value or strict
    for +/- dev value
    :return: perturbed array
    """
    arr = np.array(input_arr)
    vals = 0

    rng = np.random.default_rng()
    if type == 'gaussian':
        vals = rng.normal(scale=1.0, size=arr.shape)
        vals *= dev

    elif type == 'strict':
        vals = rng.integers(low=-1, high=2, size=arr.shape)
        vals *= dev

    elif type == 'uniform':
        vals = rng.uniform(low=-1, high=1.0, size=arr.shape)
        vals *= dev

    elif type == 'none':
        vals = np.zeros(arr.shape)

    return arr + vals

def get_idx_from_ranges(num: int, ranges: list):
    for i in range(len(ranges)):
        if num in ranges[i]:
            return i
    return False

# Process Parameters
# All are set from the config provided as an argument

# Load in config yaml file.
with open(args.config, "r") as config_file:
    config = yaml.safe_load(config_file)

#TODO: Input verification

# load variables not defined in layer_groups
#step = 0.1  # time step in seconds - maybe exposure time
interval = config["interval"]
w_dwell = config["w_dwell"]
heatup_time = config["heatup_time"]
layer_height = config["layer_height"]
roller = config["roller"]
in_situ_dwell = config["in_situ_dwell"]
process_param_request = config["process_param_request"]
substrate = config["substrate"]
output_request = config["output_request"]
sample_point_count = config["sample_point_count"]
power_fluc = config["power_fluctuation"]
deviation = config["deviation"]
scheme = config["scheme"]
comment_event_series = config["comment_event_series"]
comment_string = config["comment_string"]

# load layer_groups variable
layer_groups = config["layer_groups"]
layer_group_keys = layer_groups.keys()
layer_group_list = list(layer_groups.values())
group_flag = False # boolean flag for if there is more than one group
if len(layer_group_list) > 1 or "layers" in layer_group_list[0].keys():
    # get ranges from the intervals in layer_groups
    group_flag = True 
    intervals = [range(layer_group["layers"][0]-1, layer_group["layers"][1]+1) for layer_group in layer_group_list]
else:
    # handles the case of a single layer group
    #TODO: Implement consistent behavior regarding layer intervals so that the user is able to truncate output
    layer_group = list(layer_groups.values())[0]
    infill_scan_speed = layer_group["infill"]["scan_speed"]
    contour_scan_speed = layer_group["contour"]["scan_speed"]
    infill_laser_power = layer_group["infill"]["laser_power"]
    contour_laser_power = layer_group["contour"]["laser_power"]
    interlayer_dwell = layer_group["interlayer_dwell"]

# org_shift used if event series origin is not the same as mesh origin
xorg_shift = config["xorg_shift"]
yorg_shift = config["yorg_shift"]
zorg_shift = config["zorg_shift"]

# used for recording time to completion
e = datetime.datetime.now()

# initializing arrays and variables
power_out = []
x_out = []
y_out = []
z_out = []
t_out = []
time = 0
z_roller = []
t_roller = []
t_wiper = []
z_wiper = []

# assign working directories. Your gcode should have information to the geometry in its title. Add variables as shown
# to add more description to the event series being developed.

basename = args.outfile_name
output_dir = args.output_dir
filename_start = os.path.join(output_dir, basename)
#TODO: Change this for layer groups.
Lfile = filename_start + '_' + "testing" + '_' + str(layer_height) + ".inp"
Rfile = filename_start + '_' + "testing" + '_' + str(layer_height) + "_roller.inp"
Tfile = filename_start + '_' + "testing" + '_' + str(layer_height) + "_process_parameter.csv"
Ofile = filename_start + '_' + "testing" + '_' + str(layer_height) + "_output_times.inp"

# update path + directory name to match your configuration. This configuration assumes you will have your gcode
# within a directory adjacent to where the code will be run called "gcodes" and that you would like your result files
# in a new directory named in accordance to the Lfile name
if not os.path.isdir(output_dir):
    os.mkdir(output_dir)
gcode_files_path = args.input_dir

# Variables needed for reading gcodes
gcode_count = 0
z_coord = 0.0
x_coord = 0.0
y_coord = 0.0
linestring = ''

# reading in gcode files for FGM part
pattern = re.compile(r"[XYZFE]-?\d+\.?\d*(e[\-\+]\d*)?") # matching pattern for coordinate strings
#TODO: Set up some values that are written into docs for these
infill_f_val = 60000 # expected gcode F value for infill region
contour_f_val = 30000 # expected gcode F value for contour region
gcode_file_list = os.listdir(gcode_files_path)
if not any("gcode" in file for file in gcode_file_list):
    # Check to see if a gcode file is in the given path
    print("Error: No gcode files found in input directory {}".format(gcode_files_path))
    exit(1)
for file in gcode_file_list:
    if file[-5:] == "gcode":
        print("Reading gcode file")
        # more variables needed for reading gcodes
        x = []
        y = []
        z = []
        f = []
        z_posl = []
        power = []
        z_pos = 0
        with open(os.path.join(gcode_files_path, file), 'r') as gcode_file:
            lines = []
            # removing white spaces on lines with G1 or G0
            for line in gcode_file:
                if line.startswith("G1") or line.startswith("G0"):  # only reads movement commands
                    lines.append(line.rstrip())
        # Replacing ; with single space and splitting into list
        for line in lines:
            line = line.replace(';', ' ').split()
            # Add coordinates to corresponding arrays # changed linestring here
            for item in line:
                if pattern.fullmatch(item):
                    if item[0] == "X":
                        x.append(float(item[1:]))
                        f.append(curr_f)
                        z_pos += 1
                    elif item[0] == "Y":
                        y.append(float(item[1:]))
                    elif item[0] == "Z":
                        z.append(float(item[1:]))
                        if group_flag:
                            group_idx = get_idx_from_ranges(len(z)-1, intervals)
                            if group_idx == -1:
                                # break at z value since we don't want to record past a layer jump outside of ranges
                                break
                        z_posl.append(z_pos)  # Count of z positions per layer
                    elif item[0] == "F":
                        curr_f = float(item[1:])
            if group_flag and group_idx == -1:
                break
            if "X" in "".join(line):
                #TODO: Investigate the extrusions at bridge speed and determine a solution to handling them
                # currently handling bridge speed extrusions by having them append 0 to power array
                if curr_f != 2524140 and "E" in "".join(line):
                    if group_flag:
                        infill_laser_power = layer_group_list[group_idx]["infill"]["laser_power"]
                        contour_laser_power = layer_group_list[group_idx]["contour"]["laser_power"]
                    if curr_f == infill_f_val:
                        power.append(infill_laser_power) 
                    elif curr_f == contour_f_val:
                        power.append(contour_laser_power) 
                    else:
                        print("ERROR: gcode contains unexpected F values. Verify that the speed used is {} for infill region and {} for contour region.".format(infill_f_val, contour_f_val))
                        exit(1)
                else:
                    power.append(0)

# Using the given velocity and time step, the velocity in each direction is calculated. This is used to determine
# the incremental movement in each direction and then added to the previous value to give the next coordinate. When
# the position command value is reached, it goes to the next value
z_coord = z[1]; j = 2
x_out = np.array([x[0]])
y_out = np.array([y[0]])
z_out = np.array([z[1]])
power_out = np.array([0])
t_out = np.array([time])
section_recorder = {"indexes": [], "type": []} # for commenting infill and contour sections
curr_sec = "" # tracks current section
print("Populating event series output")
for i in range(1, len(x)):
    if group_flag:
        group_idx = get_idx_from_ranges(j-2, intervals) 
        if group_idx == -1:
            break
        infill_scan_speed = layer_group_list[group_idx]["infill"]["scan_speed"]
        contour_scan_speed = layer_group_list[group_idx]["contour"]["scan_speed"]

    del_x = x[i] - x[i-1]  # incremental change in x
    del_y = y[i] - y[i-1]  # incremental change in y
    # determining time to move between points based on xy data and velocity
    
    del_d = math.sqrt(pow(del_x,2) + pow(del_y,2))

#    vel = infill_scan_speed if f[i] == infill_f_val else contour_scan_speed
    if f[i] == infill_f_val:
        vel = infill_scan_speed
        if comment_event_series and curr_sec != "infill":
            section_recorder["indexes"].append(len(x_out) - 1)
            section_recorder["type"].append("infill")
            curr_sec = "infill"
    elif f[i] == contour_f_val:
        vel = contour_scan_speed
        if comment_event_series and curr_sec != "contour":
            section_recorder["indexes"].append(len(x_out) - 1)
            section_recorder["type"].append("contour")
            curr_sec = "contour"
       
    del_t = del_d/vel

    # add interpolated values to output arrays
    tmp_x = np.linspace(x[i-1], x[i], interval+1)
    tmp_y = np.linspace(y[i-1], y[i], interval+1)
    tmp_z = [z_coord]*(interval+1)
    tmp_p = [power[i]]*(interval+1)
    tmp_t = np.linspace(time, time+del_t, interval+1)
    x_out = np.concatenate([x_out[:-1], tmp_x])
    y_out = np.concatenate([y_out[:-1], tmp_y])
    z_out = np.concatenate([z_out[:-1], tmp_z])
    power_out = np.concatenate([power_out[:-1], tmp_p])
    t_out = np.concatenate([t_out[:-1], tmp_t])

    time += del_t
    
    # Recording gcode converted values of x, y, z, power, and time to output arrays
    # This step occurs to assist the user for reading the output event series. The z-jump could take place with no points in between if desired
    if j < len(z_posl): #if j is less than the total number of layers in the build
        if i == z_posl[j]-1: #if i is equal to one less than the number of z positions of the jth layer
            # peform a z jump of layer_height distance
            del_z = layer_height

            # get current z, add height to it
            curr_z = z_out[-1]
            tmp_z = np.array([curr_z, curr_z + del_z])
            z_out = np.concatenate([z_out, tmp_z])
            # copy x-y values for the jump since it is stationary
            x_out = np.concatenate([x_out, [x_out[-1]]*2])
            y_out = np.concatenate([y_out, [y_out[-1]]*2])
            power_out = np.concatenate([power_out, [0]*2])
            t_out = np.concatenate([t_out, [t_out[-1]]*2])

            z_coord += layer_height
            j += 1
            
# Adjust time output array by dwell time variables if option is set
if in_situ_dwell:
    print("Adjusting output times for in-situ dwell")
    # stores indices at which the z value jumps
    z_inc_arr = [(z_posl[i]-1)*interval+(i-1)*2 for i in range(2, len(z_posl))]
    t_out += heatup_time # increment whole t_out array by heatup time
    for i in range(len(z_inc_arr)):
        if group_flag:
            group_idx = get_idx_from_ranges(i, intervals)
            if group_idx == -1:
                break
            interlayer_dwell = layer_group_list[group_idx]["interlayer_dwell"]
        t_out[z_inc_arr[i]:] += interlayer_dwell
else:
    print("Skipping in-situ dwell")

# The following develops the wiper event series from laser position data and constructs the output power array. 
# The x and y are fixed to match the AM machine and will have the same wiper characteristics for any print
if roller:
    # initialize roller arrays
    t_roller = [t_out[0]]
    z_roller = list()
    for i in z_inc_arr:
            # when z increases, append the last item
            t_roller.append(t_out[i])
            z_roller.append(z_out[i+2])

    # end by appending the last item
    t_roller.append(t_out[i])
    z_roller = [z_out[0]] + z_roller

    if in_situ_dwell:
        # utilize itertools to produce flattened arrays transformed with the expected dwell times
        t_wiper = chain.from_iterable((t_roller[i]-w_dwell, t_roller[i]) if i < len(t_roller) - 1 else (None, None) for i in range(len(t_roller)))
        z_wiper = chain.from_iterable((z_roller[i], z_roller[i]) for i in range(len(z_roller)))
        # need to truncate extra values from above process
        t_wiper = list(t_wiper)[:-2]
        z_wiper = list(z_wiper)
else:
    print("Skipping roller output")

if power_fluc:
    print("Applying {} scheme to fluctuate power".format(scheme))
    power_out = perturb(power_out, deviation, type=scheme)
else:
    print("Skipping power fluctuation")

# exporting laser event series
with open(Lfile, 'w', newline='') as csvfile:
    print("Writing print path event series")
    position_writer = csv.writer(csvfile)
    rows = []
    for i in range(len(t_out)):
        row = [round(t_out[i], 6), round(x_out[i]+xorg_shift, 6), round(y_out[i]+yorg_shift, 6), round(z_out[i] -
                                                                                substrate+zorg_shift, 3), power_out[i]]
        rows.append(row) 
    if comment_event_series:
        # for adding comments that separate sections between contour and infill
        section_sep_idxs = np.array(section_recorder["indexes"])
        section_sep_types = np.array(section_recorder["type"])
        # iterate backwards in order to not mess up indexing while inserting values
        for i in range(len(section_sep_idxs)-1, -1, -1):
            rows.insert(section_sep_idxs[i], [" ".join([comment_string, section_sep_types[i], "section"])])
    position_writer.writerows(rows)

# exporting wiper/roller event series
if roller:
    print("Writing roller event series")
    with open(Rfile, 'w', newline='') as csvfile:
        position_writer = csv.writer(csvfile)
        for i in range(len(z_wiper)):
            if i % 2 == 0:
                row = [round(t_wiper[i], 6), -90, 180, round(z_wiper[i]-substrate+zorg_shift, 3), 1.0]
                position_writer.writerow(row)
            else:    
                row = [round(t_wiper[i], 6), 90, 180, round(z_wiper[i]-substrate+zorg_shift, 3), 0.0]
                position_writer.writerow(row)

# creating temperature output write times for at the end of the print phase for each layer
#TODO: Refactor while loops into for loops in the proceeding functions
if output_request:
    print("Writing coordinate output")
    with open(Ofile, "w", newline='') as csvfile:
        position_writer = csv.writer(csvfile)
        # write out initial points from heatup time
        position_writer.writerow([round(t_wiper[0], 6)]) # first deposit
        position_writer.writerow([round(t_out[0], 6)]) # first power on

        for count, i in enumerate(range(z_inc_arr[0], 0, -1)):
                        if power_out[i] != 0:
                            break
        position_writer.writerow([round(t_out[z_inc_arr[0]-count+1], 6)]) # first scan complete

        for i in range(len(z_inc_arr)):
            # t_wiper uses *2 because it has two points per z jump and (i+1) means skip the first two
            #   since those do not correspond to a jump but rather the preheat time
            deposit_start = t_wiper[(i+1)*2]
            for count, j in enumerate(range(z_inc_arr[i], len(power_out))):
                # seek first non-zero value in power array after deposit
                if power_out[j] != 0:
                    break
            power_start = t_out[z_inc_arr[i]+count]
            # seek layer end using reverse search from next layer jump
            if i < len(z_inc_arr) - 1:
                # required to handle last scan block
                seek_from_ind = z_inc_arr[i+1]
            else:
                seek_from_ind = len(x_out) - 1

            for count, j in enumerate(range(seek_from_ind, 0, -1)):
                # seek first non-zero value in power array prior to next z jump
                            if power_out[j] != 0:
                                break
            power_end = t_out[seek_from_ind-count+1]

            # write out to file
            position_writer.writerow([round(deposit_start, 6)])
            position_writer.writerow([round(power_start, 6)])
            position_writer.writerow([round(power_end, 6)])
else:
    print("Skipping coordinate output")

# Exporting process parameters used in this run
if process_param_request:
    print("Outputting process parameter csv file")
    with open(Tfile, 'w', newline='') as csvfile:
        position_writer = csv.writer(csvfile)
        date_time = ["Developed {} at {}".format(e.strftime("%Y/%d/%m"), e.strftime("%H:%M"))]
        position_writer.writerow(date_time)
        header = ["Parameter", "Value", "Unit"]
        write_rows = []
        write_rows.append([])
        if not group_flag:
            write_rows.append(["##Print parameters"])
            write_rows.append(header)
            write_rows.append(["Infill Velocity", infill_scan_speed, "mm/s"])
            write_rows.append(["Infill Laser Power", infill_laser_power, "mW"])
            write_rows.append(["Contour Velocity", contour_scan_speed, "mm/s"])
            write_rows.append(["Contour Laser Power", contour_laser_power, "mW"])
            write_rows.append(["Interlayer Dwell Time", interlayer_dwell, "s"])
        else:
            for group_name, group_params in config["layer_groups"].items():
                write_rows.append([])
                write_rows.append(["##Layer group print parameters", group_name])
                write_rows.append(header)
                for key, value in group_params.items():
                        if key == "layers":
                            write_rows.append(["Layers in Group", value, "count"])
                        elif key == "infill":
                            write_rows.append(["Infill Velocity", value["scan_speed"], "mm/s"])
                            write_rows.append(["Infill Laser Power", value["laser_power"], "mW"])
                        elif key == "contour":
                            write_rows.append(["Contour Velocity", value["scan_speed"], "mm/s"])
                            write_rows.append(["Contour Laser Power", value["laser_power"], "mW"])
                        elif key == "interlayer_dwell":
                            write_rows.append(["Dwell Time", value, "s"])
                        else:
                            write_rows.append(["Unexpected item `{}`".format(key), value, "N/A"])
        
        if roller:
            write_rows.append([])
            write_rows.append(["##Roller parameters"])
            write_rows.append(header)
            write_rows.append(["Roller time", w_dwell, "s"])

        write_rows.append([])
        write_rows.append(["##Overall parameters"])
        write_rows.append(["Intervals", interval, "#"])
        write_rows.append(["Layer Height", layer_height, "mm"])
        write_rows.append(["Substrate Thickness", substrate, "mm"])
        write_rows.append(["Initial Heatup Time", heatup_time, "s"])
        write_rows.append(["Origin Shift in X", xorg_shift, "mm"])
        write_rows.append(["Origin Shift in Y", yorg_shift, "mm"])
        write_rows.append(["Origin Shift in Z", zorg_shift, "mm"])
        for row in write_rows:
            position_writer.writerow(row)
else:
    print("Skipping process parameter output")
        

print("Complete" + "\n")
