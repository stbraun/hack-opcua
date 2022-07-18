"""A OPC UA server implementing a simple mixer unit."""

from threading import Thread
import copy
import logging
from datetime import datetime
import time
from math import sin, cos
import sys
import os
import random

from opcua import Server, uamethod

endpoint = "opc.tcp://127.0.0.1:4840"
data_spec = "server.xml"


# ### Simulation Code

class VarUpdater(Thread):
    """Abstract variable updater."""

    def __init__(self, var):
        Thread.__init__(self)
        self._stopev = False
        self.var = var

    def stop(self):
        """Stop updater."""
        self._stopev = True

    def run(self):
        """Run the thread."""
        while not self._stopev:
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
        return sin(arg)


class CosinusUpdater(VarUpdater):
    """Updates with cosine value."""

    def __init__(self, var):
        VarUpdater.__init__(self, var)

    def update(self, arg):
        return cos(arg)


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
    # TODO implement start and add to Mixer.
    return


@uamethod
def stop_mixer(parent):
    """ Method to stop the mixer.

    It will be exposed through the server.
    """
    print("Stop the mixer.")
    # TODO implement stop and add to Mixer.
    return

# ### End Mixer Methods


class MixerType():
    """Automated mixer Digital Twin."""
    def __init__(self, server: Server, ns_idx: int):
        """The mixer takes a server and namspace index required to construct an OPC-UA object type."""
        self.server = server
        self.ns_idx = ns_idx
        self.dev = self.construct_object_type()

    def construct_object_type(self):
        """Construct the OPC-UA object type for mixers."""
        dev = server.nodes.base_object_type.add_object_type(self.ns_idx, "MixerType")
        dev.add_variable(self.ns_idx, "sensor1", 1.0).set_modelling_rule(True)
        dev.add_property(self.ns_idx, "device_id", "xxxx").set_modelling_rule(True)
        ctrl = dev.add_object(self.ns_idx, "controller")
        ctrl.set_modelling_rule(True)
        ctrl.add_property(self.ns_idx, "state", "Idle").set_modelling_rule(True)
        return dev


def create_mixer(server: Server, ns_idx: int, identifier: str):
    """Create an instance of MixerType."""
    mt = MixerType(server, ns_idx)
    return server.nodes.objects.add_object(ns_idx, identifier, mt.dev)

# ### End Mixer Objects




def setup_server(endpoint: str) -> Server:
    server = Server()
    server.set_endpoint(endpoint)
    print("Starting server at " + endpoint)
    return server


def register_namespace(server: Server) -> int:
    """Create namespace and return its index."""
    return server.register_namespace("hackathon")


if __name__ == "__main__":
    server = setup_server(endpoint)
    ns_idx = register_namespace(server)
    mixer1 = create_mixer(server, ns_idx, "Mixer 1")
    mx1_state_var = mixer1.get_child([f"{ns_idx}:controller", f"{ns_idx}:state"])
    state_updater1 = StateGraphUpdater(mx1_state_var, MixerStateGraph())
    server.start()

