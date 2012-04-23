''' This test checks the correct implemetation of the turbine derivative terms.
    For that, we apply the Taylor remainder test on functional J(u, m) = <turbine_friction(m), turbine_friction(m)>,
    where m contains the turbine positions and the friction magnitude. 
'''

import sys
import configuration 
import numpy
import finite_elements
from dolfin import *
from helpers import test_gradient_array
from reduced_functional import ReducedFunctional 
from turbines import *
from initial_conditions import SinusoidalInitialCondition
set_log_level(PROGRESS)

def default_config():
  numpy.random.seed(21) 
  config = configuration.DefaultConfiguration(nx=40, ny=20, finite_element = finite_elements.p1dgp2)
  config.params["dump_period"] = 1000
  config.params["verbose"] = 0

  # Turbine settings
  config.params["turbine_pos"] = [[1000., 500.], [1600, 300], [2500, 700]]
  # The turbine friction is the control variable 
  config.params["turbine_friction"] = 12.0*numpy.random.rand(len(config.params["turbine_pos"]))
  config.params["turbine_x"] = 200
  config.params["turbine_y"] = 400

  return config

def j_and_dj(m, forward_only = None):
  # Change the control variables to the config parameters
  config.params["turbine_friction"] = m[:len(config.params["turbine_friction"])]
  mp = m[len(config.params["turbine_friction"]):]
  config.params["turbine_pos"] = numpy.reshape(mp, (-1, 2))

  # Get initial conditions
  state=Function(config.function_space, name = "current_state")
  state.interpolate(SinusoidalInitialCondition(config)())

  # Set the control values
  U = config.function_space.split()[0].sub(0) # Extract the first component of the velocity function space 
  U = U.collapse() # Recompute the DOF map
  tf = Function(U, name = "turbine") # The turbine function
  tfd = Function(U, name = "turbine_derivative") # The derivative turbine function

  # Set up the turbine friction field using the provided control variable
  tf.interpolate(Turbines(config.params))
  v = tf.vector()
  # The functional of interest is simply the l2 norm of the turbine field
  j = v.inner(v)  

  if not forward_only:
      dj = []
      # Compute the derivatives with respect to the turbine friction
      for n in range(len(config.params["turbine_friction"])):
        tfd.interpolate(Turbines(config.params, derivative_index_selector=n, derivative_var_selector='turbine_friction'))
        dj.append( 2 * v.inner(tfd.vector()) )

      # Compute the derivatives with respect to the turbine position
      for n in range(len(config.params["turbine_pos"])):
        for var in ('turbine_pos_x', 'turbine_pos_y'):
          tfd.interpolate(Turbines(config.params, derivative_index_selector=n, derivative_var_selector=var))
          dj.append( 2 * v.inner(tfd.vector()) )
      dj = numpy.array(dj)  
      
      return j, dj 
  else:
      return j, None 


j = lambda m, forward_only = False: j_and_dj(m, forward_only)[0]
dj = lambda m: j_and_dj(m, forward_only = False)[1]

# run the taylor remainder test 
config = default_config()
m0 = ReducedFunctional(config).initial_control()

# We set the perturbation_direction with a constant seed, so that it is consistent in a parallel environment.
p = numpy.random.rand(len(m0))

# Run with a functional that does not depend on m directly
for turbine_model, s in {'GaussianTurbine': {'seed': 100.0, 'tol': 1.9}, 'BumpTurbine': {'seed': 0.001, 'tol': 1.99}}.items():
  info("************* %s ********************" % turbine_model)
  config.params["turbine_model"] = turbine_model 
  minconv = test_gradient_array(j, dj, m0, s['seed'], perturbation_direction=p)

  if minconv < s['tol']:
    info_red("The turbine test failed")
    sys.exit(1)
info_green("Test passed")    
