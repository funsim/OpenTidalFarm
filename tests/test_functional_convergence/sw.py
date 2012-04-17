'''Tests the convergence of the power output with increasing resolution.
   It also checks that the power output is independent of minimal movement of its position,
   to ensure that no numerical effects influence its value.'''
import sys
import configuration 
import shallow_water_model as sw_model
import helpers
import finite_elements
import numpy
from mini_model import *
from functionals import DefaultFunctional
from turbines import *
from dolfin import *
from dolfin_adjoint import *
# There are multiple options on how to project the analytical expression of the turbine friction function onto the computational function space, see below.

# Option 1: Use a high order quadrature rule
#parameters["form_compiler"]["quadrature_degree"] = 10

set_log_level(PROGRESS)
myid = MPI.process_number()

def run_model(nx, ny, turbine_model, turbine_pos):
  '''This routine runs the forward model with the specified resolution and turbine type/positions 
     and returns the power output'''

  # Model specific settings
  config = configuration.DefaultConfiguration(nx, ny, finite_element = finite_elements.p1dgp2)
  period = 1.24*60*60 # Wave period
  config.params["dt"] = 1.0
  config.params["dump_period"]=100000

  # Turbine settings
  config.params["turbine_pos"] = turbine_pos 
  config.params["turbine_friction"] = 12./config.params["depth"]*numpy.ones(len(config.params["turbine_pos"]))

  config.params["turbine_x"] = 200
  config.params["turbine_y"] = 200
  config.params["functional_turbine_scaling"] = 0.5

  state=Function(config.function_space)
  state.interpolate(Constant((2.0, 0.0, 0.0)))

  # Option 2: Interpolate the turbine field onto a high order function space and then project it to the computational function space 
  #config2 = configuration.DefaultConfiguration(nx, ny)
  #Uh = FunctionSpace(config.mesh, "DG", 10)
  #tfh = Function(Uh)
  #tfh.interpolate(turbine_model(config))
  #U = W.split()[0].sub(0)
  #U = U.collapse() # Recompute the DOF map
  #tf = project(tfh, U)

  # Option 3: Interpolate the turbine field onto a high resolution meshand then project it to the computational mesh.  
  # Related bug reports: https://bugs.launchpad.net/dolfin/+bug/901069 and https://answers.launchpad.net/dolfin/+question/186413
  #fine = refine(refine(config.mesh))
  #Uh = FunctionSpace(fine, "DG", 1)
  #tfh = project(turbine_model(config), Uh)
  #U = W.split()[0].sub(0)
  #U = U.collapse() # Recompute the DOF map
  #tf = project(tfh, U)

  # Option 4: Interpolate the turbine expression to the computation function space
  U = config.function_space.split()[0].sub(0)
  U = U.collapse() # Recompute the DOF map
  tf = Function(U)
  config.params["turbine_model"] = turbine_model
  tf.interpolate(Turbines(config.params))

  # Output some diagnostics about the resulting turbine field
  tf_norm = norm(tf, "L2")
  if myid == 0:
    print "L2 Norm of turbine function: ", tf_norm 
  helpers.save_to_file_scalar(tf, turbine_model+"_"+str(nx)+"x"+str(ny)+"_turbine_pos="+str(turbine_pos))

  functional = DefaultFunctional(config.function_space, config.params)
  j, djdm = mini_model_solve(config, state, tf, functional)
  return j

def refine_res(nx, ny, level=0.66):
  ''' A helper function that increases the number of nodes along each axis by the provided percentage ''' 
  return int(float(nx)/level), int(float(ny)/level)


# Run test functional convergence tests
turbine_pos = [[1500., 500.]]
nx_orig = 60
ny_orig = 20

if myid == 0:
  print "Turbine size: 200x200"

# The types of turbines to be tested and their tolerances
#turbine_types = {"RectangleTurbine": RectangleTurbines, "GaussianTurbine": GaussianTurbines}
turbine_types = ["BumpTurbine", "GaussianTurbine"]
turbine_types_tol_ref = {"GaussianTurbine": 0.1, "BumpTurbine": 0.2}
turbine_types_tol_mov = {"GaussianTurbine": 0.2, "BumpTurbine": 0.5}
results = {}
for turbine_type in turbine_types:
  results[turbine_type] = {True: [], False: []}

# Run the forward model for different resolutions and with (un)perturbed turbine positions
for shift in [False, True]:
  if shift and myid ==0:
    print "\nShifting turbines half an element to the top right..."

  for model in turbine_types:
    if myid == 0:
      print '\n', model 
    nx, ny = (nx_orig, ny_orig)

    for level in range(3):
      # If requested, shift the turbine positions by half an element size
      if shift:
        turbine_pos_shift = [[t[0] + 3000.0/nx/2, t[1] + 1000.0/ny/2] for t in turbine_pos] 
      else:
        turbine_pos_shift = turbine_pos

      j = run_model(nx, ny, model, turbine_pos_shift)
      results[model][shift].append(j)
      if myid == 0:
        print "%i x %i \t\t| J = %.4g " % (nx, ny, j)

      nx, ny = refine_res(nx, ny)

# Calculate the relative changes due to mesh refinement
for t in turbine_types:
  for shift in [True, False]:
    r = results[t][shift]
    relative_change = [(r[i+1]-r[i]) / min(r[i+1], r[i]) for i in range(len(r)-1)]
    if myid == 0:
      print "Relative change for ", t, " and shifted ", shift, " is due to mesh refinement: ", relative_change 

    # Test that the relative change of the highest resolution run is smaller than the allowed tolerance
    if abs(relative_change[-1]) > turbine_types_tol_ref[t]:
      if myid == 0:
        print "Relative change exceeds tolerance"
      sys.exit(1)

# Calculate the relative changes due to turbine movement 
for t in turbine_types:
  r = results[t][False]
  rs = results[t][True]
  relative_change = [(r[i]-rs[i]) / min(r[i], rs[i]) for i in range(len(r))]
  if myid == 0:
    print "Relative change for ", t, " due to shifting is: ", relative_change 

  # Test that the relative change of the highest resolution run is smaller than the allowed tolerance
  if abs(relative_change[-1]) > turbine_types_tol_mov[t]:
    if myid == 0:
      print "Relative change exceeds tolerance"
    sys.exit(1)