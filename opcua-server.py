"""An OPC UA server implementing a simple mixer unit.

To keep things simple and understandable the number of properties and variables is reduced to a minimum.
The dynamics of the 'device' is simulated.

Events are not implemented (yet?).

"""

from threading import Thread
import copy
import logging
from datetime import datetime
import time
from math import sin, cos
import sys
import os
import random

from IPython import embed

from opcua import Server, uamethod

endpoint = "opc.tcp://127.0.0.1:4840"
namespace = "hackathon"
data_spec = "opcserver.xml"

# Maps node ids to digital twins.
node_to_instance = {}


# ### Simulation Code

class VarUpdater(Thread):
    """Abstract variable updater."""

    def __init__(self, var):
        Thread.__init__(self)
        self._stopev = False
        self._is_enabled = False
        self.var = var

    def enable(self):
        """Enable updater."""
        self._is_enabled = True

    def disable(self):
        """Disable updater."""
        self._is_enabled = False

    def stop(self):
        """Stop the updater."""
        self._stopev = True

    def run(self):
        """Run the thread."""
        while not self._stopev:
            if self._is_enabled:
                v = self.update(time.time())
                self.var.set_value(v)
                time.sleep(0.001)

    def update(self, arg):
        """Updates the variable with a new value."""
        raise Exception('Not implemented')


class SinusUpdater(VarUpdater):
    """Updates with sine value."""

    def __init__(self, var):
        VarUpdater.__init__(self, var)

    def update(self, arg):
        print(f"SinusUpdater.update({arg})")
        return sin(arg)


class CosinusUpdater(VarUpdater):
    """Updates with cosine value."""

    def __init__(self, var):
        VarUpdater.__init__(self, var)

    def update(self, arg):
        # print(f"CosinusUpdater.update({arg})")
        return cos(arg)


class NoiseUpdater(VarUpdater):
    """Updates with some noise over a given value."""

    def __init__(self, var, base_value: float, noise_amplitude: float):
        VarUpdater.__init__(self, var)
        self.base_value = base_value
        self.noise_amplitude = noise_amplitude

    def update(self, arg):
        print(f"NoiseUpdater.update({arg})")
        return self.base_value + self.noise_amplitude * random.random()


class StateGraph():
    """An abstract state graph ."""
    def __init__(self):
        self.states = []

    def next_state(self):
        """Determine the next stae of the graph."""


class StateGraphUpdater(VarUpdater):
    """Updates state randomly based on state graph and probabilities."""

    def __init__(self, var, state_graph: StateGraph):
        VarUpdater.__init__(self, var)

        self.stateGraph = state_graph
        self.last_change = time.time()
        self.offset = random.randint(2, 4)

    def update(self, arg):
        print(f"StateGraphUpdater.update({arg})")
        if arg > self.last_change + self.offset:
            self.stateGraph.next_state()
            self.last_change = arg
            self.offset = random.randint(2, 4)
        return self.stateGraph.state

# ### End Simulation Code


# ### Mixer Objects

class MixerStateGraph(StateGraph):
    """A state graph working as Markov model."""
    def __init__(self):
        self.idle = "Idle"
        self.running = "Running"
        self.error = "Error"
        self.states = [self.idle, self.running, self.error]
        # Probabilities of next state: p_idle, p_running, p_error
        self.probs = {self.idle: (0.3, 0.6, 0.1),
                      self.running: (0.1, 0.7, 0.2),
                      self.error: (0.1, 0.8, 0.1),
                      }
        self.state = self.idle

    def next_state(self):
        event = random.random()
        min_prob = 1.0
        min_idx = -1
        for idx, prob in enumerate(self.probs[self.state]):
            if prob > event and prob <= min_prob:
                if prob == min_prob:
                    min_idx = random.choice([min_idx, idx])
                else:
                    min_prob = prob
                    min_idx = idx
        if min_idx >= 0:
            new_state = self.states[min_idx]
            print(f"{self.state} --( {event:.2f} )-> {new_state}")
            self.state = new_state


# ### Mixer Methods

# The decorator converts automatically to and from variants.
@uamethod
def start_mixer(parent):
    """ Method to start the mixer.

    It will be exposed through the server.
    """
    print("Start the mixer.")
    instance = node_to_instance[parent]
    instance.start()
    return


@uamethod
def stop_mixer(parent):
    """ Method to stop the mixer.

    It will be exposed through the server.
    """
    print("Stop the mixer.")
    instance = node_to_instance[parent]
    instance.stop()
    return

# ### End Mixer Methods


class MixerType():
    """Automated mixer Digital Twin."""
    def __init__(self, server: Server, ns_idx: int, device_id: str):
        """The mixer takes a server and namspace index required to construct an OPC-UA object type."""
        self.server = server
        self.ns_idx = ns_idx
        self.device_id = device_id
        self.dev = None
        self.state_updater = None
        self.sensor_updater = None
        self.is_first_call = True
        self.construct_object_type()

    def construct_object_type(self):
        """Construct the OPC-UA object type for mixers."""
        self.dev = server.nodes.base_object_type.add_object_type(self.ns_idx, "MixerType")

        self.sensor_var = self.dev.add_variable(self.ns_idx, "sensor", 1.0)
        self.sensor_var.set_modelling_rule(True)

        self.dev.add_property(self.ns_idx, "device_id", self.device_id).set_modelling_rule(True)

        ctrl = self.dev.add_object(self.ns_idx, "controller")
        ctrl.set_modelling_rule(True)
        self.state_var = ctrl.add_property(self.ns_idx, "state", "Idle")
        self.state_var.set_modelling_rule(True)

    def start(self):
        """Start mixer."""
        self.state_updater.enable()
        self.sensor_updater.enable()

    def stop(self):
        """Stop mixer."""
        self.state_updater.disable()
        self.sensor_updater.disable()

    def start_simulation(self):
        """Start the updaters for simulation."""
        if self.is_first_call:
            print(f"Starting simulation for {self.device_id}")
            self.state_updater.start()
            self.sensor_updater.start()
            self.is_first_call = False

    def stop_simulation(self):
        """Stop the updaters for simulation."""
        self.state_updater.stop()
        self.sensor_updater.stop()


def create_mixer(server: Server, ns_idx: int, identifier: str) -> MixerType:
    """Create an instance of MixerType."""
    mixer = MixerType(server, ns_idx, device_id=identifier)
    mixer_obj = server.nodes.objects.add_object(ns_idx, identifier, mixer.dev)

    state_var = mixer_obj.get_child([f"{ns_idx}:controller", f"{ns_idx}:state"])
    mixer.state_updater = StateGraphUpdater(state_var, MixerStateGraph())
    sensor_var = mixer_obj.get_child(f"{ns_idx}:sensor")
    mixer.sensor_updater = NoiseUpdater(sensor_var, 47.4, 2.0)

    mixer_obj.add_method(ns_idx, "start mixer", start_mixer)
    mixer_obj.add_method(ns_idx, "stop mixer", stop_mixer)
    node_to_instance[mixer_obj.nodeid] = mixer
    print(f"node id = {mixer_obj.nodeid}")
    return mixer


# ### End Mixer Objects



def setup_server(endpoint: str) -> Server:
    """Setup the server with endpoint."""
    server = Server()
    server.set_endpoint(endpoint)
    print("Starting server at " + endpoint)
    return server


def register_namespace(server: Server) -> int:
    """Create namespace and return its index."""
    return server.register_namespace(namespace)


if __name__ == "__main__":
    server = setup_server(endpoint)
    ns_idx = register_namespace(server)

    mixer1 = create_mixer(server, ns_idx, "Mixer 1")
    server.start()
    server.export_xml_by_ns(data_spec, [ns_idx])
    try:
        mixer1.start_simulation()
        embed()
    finally:
        print("Cleanup simulation threads ...")
        mixer1.stop_simulation()
    sys.exit(0)

