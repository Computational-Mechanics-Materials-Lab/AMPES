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
