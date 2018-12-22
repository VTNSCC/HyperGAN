#From https://gist.github.com/EndingCredits/b5f35e84df10d46cfa716178d9c862a3
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from tensorflow.python.ops import control_flow_ops
from tensorflow.python.ops import math_ops
from tensorflow.python.ops import state_ops
from tensorflow.python.framework import ops
from tensorflow.python.training import optimizer
import tensorflow as tf
import hyperchamber as hc
import inspect

class SocialOptimizer(optimizer.Optimizer):
  def __init__(self, learning_rate=0.001, p=0.1, gan=None, config=None, use_locking=False, name="SocialOptimizer", optimizer=None, rho=1, beta=1, gamma=1):
    """https://arxiv.org/pdf/1803.03021.pdf"""
    super().__init__(use_locking, name)
    self.gan = gan
    self.config = config
    self._lr_t = learning_rate

    self.optimizer = self.gan.create_optimizer(optimizer)
 
  def _prepare(self):
    super()._prepare()
    self.optimizer._prepare()

  def _create_slots(self, var_list):
    super()._create_slots(var_list)
    self.optimizer._create_slots(var_list)

  def _apply_dense(self, grad, var):
    return self.optimizer._apply_dense(grad, var)

  def apply_gradients(self, grads_and_vars, global_step=None, name=None):
    var_list = [ v for _,v in grads_and_vars]
    d_vars = []
    g_vars = []
    for grad,var in grads_and_vars:
        if var in self.gan.d_vars():
            d_vars += [var]
        elif var in self.gan.g_vars():
            g_vars += [var]
        else:
            raise("Couldn't find var in g_vars or d_vars")
    w = [tf.Variable(0.5), tf.Variable(0.5)]

    Vidv = [self.gan.trainer.d_loss, self.gan.trainer.g_loss]
    Vsoc = [1/2. * self.gan.trainer.d_loss + 1/2.* self.gan.trainer.g_loss for _ in range(2)]

    wlr = self.config.w_learn_rate or 0.1
    wt1 = [w[0] - wlr * (Vidv[0] - Vsoc[0]), w[1] - wlr * (Vidv[1] - Vsoc[1])]


    self._prepare()

    op1 = tf.group(*[tf.assign(w, v) for w,v in zip(w, wt1)]) # store variables
    self.gan.add_metric('w-0', w[0])
    self.gan.add_metric('w-1', w[1])
    w = [tf.nn.sigmoid(w[0]),tf.nn.sigmoid(w[1])]
    self.gan.add_metric('w0', w[0])
    self.gan.add_metric('w1', w[1])

    with tf.get_default_graph().control_dependencies([op1]):
        Vi = [(1. - w[0]) * Vidv[0] + w[0] * Vsoc[0],
              (1. - w[1]) * Vidv[1] + w[1] * Vsoc[1]]

        new_grads = tf.gradients(Vi[0], d_vars) + tf.gradients(Vi[1], g_vars)
        new_grads_and_vars = list(zip(new_grads, var_list)).copy()
        op3 = self.optimizer.apply_gradients(new_grads_and_vars.copy(), global_step=global_step, name=name)
        with tf.get_default_graph().control_dependencies([op3]):
            return tf.no_op()

  def _apply_sparse(self, grad, var):
    raise NotImplementedError("Sparse gradient updates are not supported.")
  def variables(self):
      return self.optimizer.variables()
