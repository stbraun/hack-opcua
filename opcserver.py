import uuid
from threading import Thread
import copy
import logging
from datetime import datetime
import time
from math import sin, cos
import sys
import os
import random

import opcua
from opcua.ua import NodeId, NodeIdType

try:
    from IPython import embed
except ImportError:
    import code

    def embed():
        myvars = globals()
        myvars.update(locals())
        shell = code.InteractiveConsole(myvars)
        shell.interact()

from opcua import ua, uamethod, Server


class SubHandler(object):
    """Subscription Handler. To receive events from server for a subscription."""

    def datachange_notification(self, node, val, data):
        print(f"Python: New data change event for node={node} with value={val} and data={data}")

    def event_notification(self, event):
        print(f"Python: New event={event}")


# method to be exposed through server

def func(parent, variant):
    ret = False
    if variant.Value % 2 == 0:
        ret = True
    return [ua.Variant(ret, ua.VariantType.Boolean)]


# method to be exposed through server
# uses a decorator to automatically convert to and from variants

@uamethod
def multiply(parent, x, y):
    print("multiply method call with parameters: ", x, y)
    return x * y


class EventUpdater(Thread):
    """Abstract event updater."""

    def __init__(self, evt):
        Thread.__init__(self)
        self._stopev = False
        self.evt = evt

    def stop(self):
        """Stop updater."""
        self._stopev = True

    def run(self):
        """Run the thread."""
        while not self._stopev:
            new_evt = self.update(time.time())
            if new_evt is not None:
                # print(f"{self.evt} - {new_evt}")
                self.evt.trigger(message=new_evt)
            time.sleep(0.001)

    def update(self, arg):
        """Updates the event with a new value or None for no event."""
        raise Exception('Not implemented')


class MyEventUpdater(EventUpdater):
    """Updates with random value."""

    def __init__(self, evt):
        EventUpdater.__init__(self, evt)
        self.last_change = time.time()
        self.offset = random.randint(2, 15)

    def update(self, arg):
        if arg > self.last_change + self.offset:
            new_evt = f"event: {self.offset}"
            self.last_change = arg
            self.offset = random.randint(2, 15)
            return new_evt
        return None


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


class StateUpdater(VarUpdater):
    """Updates state based on random time."""

    def __init__(self, var):
        VarUpdater.__init__(self, var)
        self.states = ["Idle", "Running", "Error"]
        self.state = 0
        self.last_change = time.time()
        self.offset = random.randint(2, 15)

    def update(self, arg):
        if arg > self.last_change + self.offset:
            self.state = (self.state + 1) % len(self.states)
            self.last_change = arg
            self.offset = random.randint(2, 15)
        return self.states[self.state]


class StateGraph():
    """A simple state graph."""
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


class StateGraphUpdater(VarUpdater):
    """Updates state based on state graph and probabilities."""

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


def create_ot_device(ns_idx, server):
    """ Create a new object type we can instantiate in our address space. """
    dev = server.nodes.base_object_type.add_object_type(ns_idx, "MyDevice")
    dev.add_variable(ns_idx, "sensor1", 1.0).set_modelling_rule(True)
    dev.add_property(ns_idx, "device_id", "0340").set_modelling_rule(True)
    ctrl = dev.add_object(ns_idx, "controller")
    ctrl.set_modelling_rule(True)
    ctrl.add_property(ns_idx, "state", "Idle").set_modelling_rule(True)
    return dev


def create_object(ns_idx: int):
    """ Create an objects with some variables and methods. """

    # First a folder to organize our nodes
    server.nodes.objects.add_folder(ns_idx, "myEmptyFolder")

    myobj = server.nodes.objects.add_object(ns_idx, "MyObject")

    myvar = myobj.add_variable(ns_idx, "MyVariable", 6.7)
    myvar.set_writable()    # Set MyVariable to be writable by clients

    mystringvar = myobj.add_variable(ns_idx, "MyStringVariable", "Really nice string")
    mystringvar.set_writable()  # Set MyVariable to be writable by clients

    myobj.add_variable(NodeId(uuid.UUID('1be5ba38-d004-46bd-aa3a-b5b87940c698'), ns_idx, NodeIdType.Guid),
                       'MyStringVariableWithGUID', 'NodeId type is guid')

    mydtvar = myobj.add_variable(ns_idx, "MyDateTimeVar", datetime.utcnow())
    mydtvar.set_writable()    # Set MyVariable to be writable by clients

    myarrayvar = myobj.add_variable(ns_idx, "myarrayvar", [6.7, 7.9])
    myarrayvar = myobj.add_variable(ns_idx, "myStronglytTypedVariable", ua.Variant([], ua.VariantType.UInt32))

    myobj.add_property(ns_idx, "myproperty", "I am a property")

    myobj.add_method(ns_idx, "is_even", func, [ua.VariantType.Int64], [ua.VariantType.Boolean])
    myobj.add_method(ns_idx, "multiply", multiply, [ua.VariantType.Int64, ua.VariantType.Int64], [ua.VariantType.Int64])
    return myobj, myvar, myarrayvar


def init_server():
    print("Setup our server ...")
    server = Server()
    # server.disable_clock()
    # server.set_endpoint("opc.tcp://localhost:4840/freeopcua/server/")
    server.set_endpoint("opc.tcp://0.0.0.0:4841/freeopcua/server/")
    server.set_server_name("FreeOpcUa Example Server")
    # set all possible endpoint policies for clients to connect through
    server.set_security_policy([
        ua.SecurityPolicyType.NoSecurity,
        ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt,
        ua.SecurityPolicyType.Basic256Sha256_Sign])
    return server


if __name__ == "__main__":
    # optional: setup logging
    logging.basicConfig(level=logging.WARN)
    # logger = logging.getLogger("opcua.address_space")
    # logger.setLevel(logging.DEBUG)
    # logger = logging.getLogger("opcua.internal_server")
    # logger.setLevel(logging.DEBUG)
    # logger = logging.getLogger("opcua.binary_server_asyncio")
    # logger.setLevel(logging.DEBUG)
    # logger = logging.getLogger("opcua.uaprocessor")
    # logger.setLevel(logging.DEBUG)

    server = init_server()

    # setup our own namespace
    uri = "http://examples.freeopcua.github.io"
    ns_idx = server.register_namespace(uri)

    print("Populating our namespace ...")

    # create a new object type we can instantiate in our address space
    dev = create_ot_device(ns_idx, server)

    dev_sensor1 = dev.get_child(f"{ns_idx}:sensor1")
    dev_sensor1_updater = SinusUpdater(dev_sensor1)

    # instantiate one instance of our device
    mydevice = server.nodes.objects.add_object(ns_idx, "Device0001", dev)
    # get proxy to our device state variable
    mydevice_state_var = mydevice.get_child([f"{ns_idx}:controller", f"{ns_idx}:state"])

    # import some nodes from xml
    config_xml = "custom_nodes.xml"
    print(f"Loading nodes from {config_xml}...")
    server.import_xml(config_xml)

    # Creating a default event object
    # The event object automatically will have members for all events properties
    # you probably want to create a custom event type, see other examples
    myevgen = server.get_event_generator()
    myevgen.event.Severity = 300

    myobj, myvar, myarrayvar = create_object(ns_idx)
    mysin = myobj.add_variable(ns_idx, "MySin", 0, ua.VariantType.Float)
    mycos = myobj.add_variable(ns_idx, "MyCos", 1, ua.VariantType.Float)

    print("Available loggers are: ", logging.Logger.manager.loggerDict.keys())

    print("Starting the server ...")
    server.start()

    sin_updater = SinusUpdater(mysin)
    cos_updater = CosinusUpdater(mycos)
    state_updater = StateGraphUpdater(mydevice_state_var, StateGraph())
    myevgen_updater = MyEventUpdater(myevgen)

    server.export_xml_by_ns("opcserver.xml")

    try:
        sin_updater.start()
        cos_updater.start()
        state_updater.start()
        myevgen_updater.start()

        dev_sensor1_updater.start()

        # enable following if you want to subscribe to nodes on server side
        # handler = SubHandler()
        # sub = server.create_subscription(500, handler)
        # handle = sub.subscribe_data_change(myvar)

        # return a ref to value in db server side! not a copy!
        var = myarrayvar.get_value()
        # WARNING: we need to copy before writting again
        # otherwise no data change event will be generated
        var = copy.copy(var)
        var.append(9.3)
        myarrayvar.set_value(var)

        # Server side write method which is a bit faster than using set_value
        server.set_attribute_value(myvar.nodeid, ua.DataValue(9.9))

        embed()
    finally:
        sin_updater.stop()
        cos_updater.stop()
        state_updater.stop()
        myevgen_updater.stop()
        server.stop()
