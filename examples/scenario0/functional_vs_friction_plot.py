''' An example that plots the power ouput of a single turbine for different fricition values. (see also test_optimal_friction_single_turbine) '''
import sys
import configuration 
import numpy
import matplotlib.pyplot as plt
from dolfin import *
from dolfin_adjoint import *
from reduced_functional import ReducedFunctional
from helpers import info, info_green, info_red, info_blue
set_log_level(ERROR)

basin_x = 640.
basin_y = 320.

# We set the perturbation_direction with a constant seed, so that it is consistent in a parallel environment.
config = configuration.ScenarioConfiguration("mesh.xml", inflow_direction = [1, 0])
config.params['automatic_scaling'] = False

# Place one turbine 
offset = 0.0
turbine_pos = [[basin_x/3 + offset, basin_y/2 + offset]] 
info_green("Turbine position: " + str(turbine_pos))
config.set_turbine_pos(turbine_pos)
config.params['controls'] = ['turbine_friction']

model = ReducedFunctional(config, scaling_factor = 10**-6)
m0 = model.initial_control()
m_list = [numpy.ones(len(m0))*i for i in numpy.linspace(0, 200, 100)]
info_green('Testing friction coefficients: ' + str([x[0] for x in m_list]))

# We already know that a zero friction leads to a zero power 
P = [0]
f = [0]
for m in m_list: 
  P.append(model.j(m))
  f.append(m[0])

# Plot the results
if MPI.process_number() == 0:
  plt.figure(1)
  plt.plot(f, P)
  info_green('The maximum functional value of ' + str(max(P)) + ' is achieved with a friction coefficient of ' + str(f[numpy.argmax(P)]) + '.')
  plt.ylabel('Power output [MW]')
  plt.xlabel('Turbine coefficient')
  plt.savefig('example_single_turbine_friction_vs_power_plot.pdf')