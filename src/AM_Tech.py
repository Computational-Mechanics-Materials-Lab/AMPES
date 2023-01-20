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

# Argument Parsing 
cwd = os.getcwd()
parser = argparse.ArgumentParser(prog="AM Tech", description="Reads a RepRap gcode file and outputs Abaqus compatible .inp files based off of it.")
parser.add_argument("-i", "--input_dir", help="Folder that contains the gcode file(s), defaults to <current working dir>/gcodes", default=os.path.join(cwd, "gcodes"))
parser.add_argument("-c", "--config", help="Config input YAML that will be used to initialize parameters, defaults to <current working dir>/input.yaml", default=os.path.join(cwd, "input.yaml"))
parser.add_argument("-d", "--output_dir", help="Directory to output files to, defaults to <current working dir>/output", default=os.path.join(cwd, "output"))
parser.add_argument("-o", "--outfile_name", help="Basename for the files that will be outputted, defaults to \"output\"", default="output")

args = parser.parse_args()

# Process Parameters
# All are set from the config provided as an argument

# Load in config yaml file.
with open(args.config, "r") as config_file:
    config = yaml.safe_load(config_file)

#TODO: Input verification
FGM = config["FGM"]
# Load certain variables given FGM
if FGM:
    scan_speed_FGM = config["scan_speed_FGM"]
    laser_power_FGM = config["laser_power_FGM"]
else:
    scan_speed = config["scan_speed"]
    laser_power = config["laser_power"]
#step = 0.1  # time step in seconds - maybe exposure time
interval = config["interval"]
layer_height = config["layer_height"]
i_dwell = config["i_dwell"]
w_dwell = config["w_dwell"]
roller = config["roller"]
in_situ_dwell = config["in_situ_dwell"]
process_param_request = config["process_param_request"]
substrate = config["substrate"]
output_request = config["output_request"]
sample_point_count = config["sample_point_count"]

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
Lfile = filename_start + '_' + str(w_dwell) + '_' + str(layer_height) + ".inp"
Rfile = filename_start + '_' + str(w_dwell) + '_' + str(layer_height) + "_roller.inp"
Tfile = filename_start + '_' + str(w_dwell) + '_' + str(layer_height) + "_process_parameter.csv"
Ofile = filename_start + '_' + str(w_dwell) + '_' + str(layer_height) + "_output_times.inp"

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
if FGM:
    for gcodes in os.listdir(gcode_files_path):  # need to develop way to start from bot to top of part
        # more variables needed for reading gcodes. These will be reset for each gcode file read
        x = []
        y = []
        z = []
        z_posl = []
        power = []
        z_pos = 0
        if gcodes[-5:] == "gcode":
            # Assigning scan speed for current gcode
            vel = scan_speed_FGM[gcode_count]
            with open(os.path.join(gcode_files_path, gcodes), 'r') as file:
                lines = []
                # removing white spaces on lines with G1
                for line in file:
                    if line.startswith("G1"):  # only reads movement commands(G1 ...)
                        lines.append(line.rstrip())
            # Replacing ; with single space and splitting into list
            for line in lines:
                line = line.replace(';', ' ').split()
                p = 0
                while p < len(line):
                    linestring += line[p]
                    p += 1
                # If extrusion and movement command found, append power value
                if linestring.find("E") != -1 and linestring.find("X") != -1:
                    power.append(laser_power_FGM[gcode_count])
                # If movement but no extrusion, append power of zero
                elif linestring.find("X") != -1 and linestring.find("E") == -1:
                    power.append(0.0)

                # Add coordinates to corresponding arrays # changed linestring here
                for item in line:
                    item = ''.join(c for c in item if c.isdigit() or c == "-" or c == "." or c == "X" or
                                                                                    c == "Y" or c == "Z" or c == "E")
                    if item.startswith("X"):
                        x.append(float(item[1:]))
                        z_pos += 1
                        continue
                    if item.startswith("Y"):
                        y.append(float(item[1:]))
                        continue
                    if item.startswith("Z"):
                        z.append(float(item[1:]))
                        z_posl.append(z_pos)  # Count of z positions per layer
                        continue

    # Using the given velocity and time step, the velocity in each direction is calculated. This is used to determine
    # the incremental movement in each direction and then added to the previous value to give the next coordinate. When
    # the position command value is reached, it goes to the next value

            z_coord = z[1]; j = 2
            for i in range(1, len(x)):
                 del_x = x[i] - x[i-1]  # incremental change in x
                 del_y = y[i] - y[i-1]  # incremental change in y
                 # determining time to move between points based on xy data and velocity
                
                 del_d = math.sqrt(pow(del_x,2) + pow(del_y,2))
                 del_t = del_d/vel
         
                 inst = del_t / interval  # creating instant value to increase number of time points evenly
                 x_add = del_x / interval  # incremental point distance that will sum to del_x based on step
                 y_add = del_y / interval  # incremental point distance that will sum to del_y based on step
                 k = 0
        
                 while k <= interval:
                     if k == 0:
                         if i == 1:
                             x_coord = x[i - 1]
                             y_coord = y[i - 1]
                         else:
                             k += 1
                             continue
                     elif k != 0 and k != interval:
                         x_coord += x_add
                         y_coord += y_add
                     elif k == interval:
                         x_coord = x[i]
                         y_coord = y[i]
                     x_out.append(x_coord)
                     y_out.append(y_coord)
                     z_out.append(z_coord)
                     power_out.append(power[i])
                     time += inst
                     t_out.append(time)
                     k += 1
                 # Recording gcode converted values of x, y, z, power, and time to output arrays
                 if j < len(z_posl): #if j is less than the total number of layers in the build
                     if i == z_posl[j]-1: #if i is equal to one less than the number of z positions of the jth layer
                         del_z = layer_height
                         t = del_z / vel
                         inst = t / interval
                         z_add = del_z / interval

                         z_coord = z[j-1]
                         x_out.append(x_coord)
                         y_out.append(y_coord)
                         z_out.append(z_coord)
                         power_out.append(power[i])
                         time += inst
                         t_out.append(time)
                         
                         z_coord = z[j]
                         x_out.append(x_coord)
                         y_out.append(y_coord)
                         z_out.append(z_coord)
                         power_out.append(power[i])
                         time += inst
                         t_out.append(time)

                         j += 1
            gcode_count += 1

# reading in gcode files for non FGM part
else:
    # print ("here")
    pattern = re.compile(r"[XYZFE]-?\d+\.?\d*") # matching pattern for coordinate strings
    for gcodes in os.listdir(gcode_files_path):
        # more variables needed for reading gcodes
        x = []
        y = []
        z = []
        f = []
        z_posl = []
        power = []
        z_pos = 0
        curr_f = 0
        max_f = 54000 # TODO:REMOVE THIS LATER
        if gcodes[-5:] == "gcode":
            # Assigning scan speed for current gcode
            vel = scan_speed
            with open(os.path.join(gcode_files_path, gcodes), 'r') as file:
                lines = []
                # removing white spaces on lines with G1
                for line in file:
                    if line.startswith("G1"):  # only reads movement commands(G1 ...)
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
                            z_posl.append(z_pos)  # Count of z positions per layer
                        elif item[0] == "F":
                            curr_f = float(item[1:])
                if "X" in "".join(line):
                    if "E" in "".join(line):
                        power.append(laser_power * (curr_f/max_f)) # TODO:change this to reflect user input for contour and infil
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
            for i in range(1, len(x)):
                del_x = x[i] - x[i-1]  # incremental change in x
                del_y = y[i] - y[i-1]  # incremental change in y
                # determining time to move between points based on xy data and velocity
                
                del_d = math.sqrt(pow(del_x,2) + pow(del_y,2))

                vel = f[i]/60
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
                        t = del_z / vel

                        # tmp_z = np.linspace(z_coord, z_coord+layer_height, interval+1)
                        # tmp_t = np.linspace(time, time+t, interval+1)
                        # x_out = np.concatenate([x_out, [x_out[-1]]*interval])
                        # y_out = np.concatenate([y_out, [y_out[-1]]*interval])
                        # z_out = np.concatenate([z_out, tmp_z[1:]])
                        # power_out = np.concatenate([power_out, [0]*interval])
                        # t_out = np.concatenate([t_out, tmp_t[1:]])

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
                        
# The following develops the wiper event series from laser position data and constructs the output power array. 
# The x and y are fixed to match the AM machine and will have the same wiper characteristics for any print
if roller:
    # initialize roller arrays
    if in_situ_dwell:
        # tracker array for indices where z increases
        z_inc_arr = list()
    t_roller = [t_out[0]]
    z_roller = list()
    power_out[0] = 0.0
    for i in range(1, len(z_out)):
        if z_out[i-1] < z_out[i]:
            # when z increases, set power_out to 0 and append the last item
            if in_situ_dwell:
                z_inc_arr.append(i-1)
            t_roller.append(t_out[i-1])
            z_roller.append(z_out[i-1])
            power_out[i-2] = 0.0

    # end by appending the last item and a final 0 for power
    t_roller.append(t_out[i])
    z_roller.append(z_out[i])
    power_out[i-1] = 0.0

if in_situ_dwell:
    # initialize wiper arrays
    t_wiper = [0.0]
    z_wiper = list()
    for i in range(len(t_roller)):
        if i == len(t_roller) - 1:
            # required since we're using index + 1
            break
        t_wiper.append(t_roller[i]+i_dwell+w_dwell*(i))
        t_wiper.append(t_roller[i+1]+w_dwell+w_dwell*(i))
        z_wiper.append(z_roller[i])
        z_wiper.append(z_roller[i])
    del (t_wiper[-1])

    # adding dwell time to time array
    t_out += i_dwell # increment whole t_out array by i_dwell
    for ind in z_inc_arr:
        # at all places where z increases, add w_dwell to whole array including and proceeding that position
        t_out[ind:] += w_dwell

# exporting laser event series##
with open(Lfile, 'w', newline='') as csvfile:
    position_writer = csv.writer(csvfile)
    for i in range(len(t_out)):
        row = [round(t_out[i], 6), round(x_out[i]+xorg_shift, 6), round(y_out[i]+yorg_shift, 6), round(z_out[i] -
                                                                                substrate+zorg_shift, 3), power_out[i]]
        position_writer.writerow(row)

# exporting wiper/roller event series
if roller:
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
    in_time = i_dwell
    output_scan = []
    increment_sample_points = 0
    q = 1
    temp = []
    for i in range(len(t_out)):
        if t_out[i] - in_time <= 5.0:
            temp.append(t_out[i])
        elif t_out[i] - in_time > 5.0 or i + 1 == len(t_out):
            increment_sample_points = int(len(temp) / sample_point_count)
            if len(temp) % sample_point_count == 0:
                while q < sample_point_count:
                    output_scan.append(str(round(temp[int(q*increment_sample_points)], 5)))
                    q += 1
            else:
                while q + 1 < sample_point_count:
                    output_scan.append(str(round(temp[int(q*increment_sample_points)], 5)))
                    q += 1
                output_scan.append(str(round(t_out[i - 1], 6)))
            temp = []
        in_time = t_out[i]
        q = 0

    increment_sample_points = int(len(temp) / sample_point_count)
    if len(temp) % sample_point_count == 0:
        while q < sample_point_count:
            output_scan.append(str(round(temp[int(q*increment_sample_points)], 5)))
            q += 1
    elif len(temp) % sample_point_count != 0:
        while q + 1 < sample_point_count:
            output_scan.append(str(round(temp[int(q*increment_sample_points)], 5)))
            q += 1
        output_scan.append(str(round(t_out[k - 1], 6)))

    with open(Ofile, 'w', newline='') as csvfile:
        position_writer = csv.writer(csvfile)
        p = 0
        counter = 0
        for i in range(len(t_wiper)):
            if i % 2 == 0:
                row = [(round(t_wiper[i], 6))]
                position_writer.writerow(row)
            elif i % 2 != 0:
                for j in range(sample_point_count):
                    row = [output_scan[p]]
                    position_writer.writerow(row)
                    p += 1

# Exporting process parameters used in this run
if process_param_request:
    with open(Tfile, 'w', newline='') as csvfile:
        position_writer = csv.writer(csvfile)
        date_time = ["Developed {} at {}".format(e.strftime("%Y/%d/%m"), e.strftime("%H:%M"))]
        position_writer.writerow(date_time)
        header = ["Parameter", "Value", "Unit"]
        position_writer.writerow(header)
        if not FGM:
            row1 = ["velocity", scan_speed, "mm/s"]
            row2 = ["Laser Power", laser_power, "mW"]
            position_writer.writerow(row1)
            position_writer.writerow(row2)
        else:
            for i in range(gcode_count):
                row1 = []
                row2 = []
                row1.append("velocity " + str(i+1))
                row2.append("Laser Power " + str(i+1))
                row1.append(scan_speed_FGM[i])
                row2.append(laser_power_FGM[i])
                row1.append("mm/s")
                row2.append("mW")
                position_writer.writerow(row1)
                position_writer.writerow(row2)
        row3 = ["Intervals", interval, "#"]
        position_writer.writerow(row3)
        row4 = ["Layer Height", layer_height, "mm"]
        position_writer.writerow(row4)
        row5 = ["Substrate Thickness", substrate, "mm"]
        position_writer.writerow(row5)
        row6 = ["Initial Dwell Time", i_dwell, "s"]
        position_writer.writerow(row6)
        row7 = ["Dwell Time", w_dwell, "s"]
        position_writer.writerow(row7)
        row8 = ["Origin Shift in X", xorg_shift, "mm"]
        position_writer.writerow(row8)
        row9 = ["Origin Shift in Y", yorg_shift, "mm"]
        position_writer.writerow(row9)
        row10 = ["Origin Shift in Z", zorg_shift, "mm"]
        position_writer.writerow(row10)

print("Complete" + "\n")
