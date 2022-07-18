#%matplotlib widget
import sys
sys.path.insert(0, "..")
import logging
import time
import math
import threading
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

fig, ax = plt.subplots(3, 1, sharex=True)
max_x = 10000
x = np.arange(0, max_x)
sin_index = 0
cos_index = 0
old_index = 0
sin_y = [0.0, ] * max_x
cos_y = [0.0, ] * max_x
x1 = []
y1 = []
interval = 200


def animate(i):
    # sine tag
    ax[0].clear()
    ax[0].set_ylim(-1.2, 1.2)
    ax[0].axhline(0, color='k')
    ax[0].plot(x, sin_y)

    # cosine tag
    ax[1].clear()
    ax[1].set_ylim(-1.2, 1.2)
    ax[1].axhline(0, color='k')
    ax[1].plot(x, cos_y, 'r')

    # Updates/second
    global sin_index, old_index, x1, y1
    if sin_index < old_index:
        old_index = 0
        x1 = []
        y1 = []
    x1.append(sin_index)
    y1.append((sin_index - old_index) * 1000 / interval)
    old_index = sin_index

    ax[-1].clear()
    ax[-1].set_ylim(250, 750)
    updates_per_second, = ax[-1].plot(x1, y1, color='tab:orange', label='Updates per second')
    # Create a legend
    legend = ax[-1].legend(handles=[updates_per_second], loc='upper right')

    # Add the legend manually to the current Axes.
    fig.gca().add_artist(legend)


try:
    from IPython import embed
except ImportError:
    print('ImportError')
    import code

    def embed():
        vars = globals()
        vars.update(locals())
        shell = code.InteractiveConsole(vars)
        shell.interact()


from opcua import Client
from opcua import ua


class Sin_SubHandler(object):

    """
    Subscription Handler. To receive events from server for a subscription
    data_change and event methods are called directly from receiving thread.
    Do not do expensive, slow or network operation there. Create another
    thread if you need to do such a thing
    """

    def datachange_notification(self, val):
        # print("Python: New data change event", val)
        global sin_index
        global sin_y
        global max_x
        # print(index, val)
        sin_y[sin_index] = val
        sin_index = (sin_index + 1) % max_x

class Cos_SubHandler(object):

    """
    Subscription Handler. To receive events from server for a subscription
    data_change and event methods are called directly from receiving thread.
    Do not do expensive, slow or network operation there. Create another
    thread if you need to do such a thing
    """

    def datachange_notification(self, val):
        # print("Python: New data change event", type(node), node, val)
        global cos_index
        global cos_y
        global max_x
        # print(index, val)
        cos_y[cos_index] = val
        cos_index = (cos_index + 1) % max_x

class ValueUpdater(object):
    def __init__(self, interval=1):
        self.interval = interval

        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True
        thread.start()

    def run(self):
        sin_handler = Sin_SubHandler()
        cos_handler = Cos_SubHandler()
        i = 0
        while True:
            sin_value = sin_var.get_value()
            cos_value = cos_var.get_value()
            sin_handler.datachange_notification(sin_value)
            cos_handler.datachange_notification(cos_value)
            i += 1
            # time.sleep(0)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARN)
    # logger = logging.getLogger("KeepAlive")
    # logger.setLevel(logging.DEBUG)

    client = Client("opc.tcp://localhost:4840/freeopcua/server/")

    # client = Client("opc.tcp://admin@localhost:4840/freeopcua/server/") #connect using a user
    try:
        client.connect()
        client.load_type_definitions()  # load definition of server specific structures/extension objects

        # Client has a few methods to get proxy to UA nodes that should always be in address space such as Root or Objects
        root = client.get_root_node()
        print("Root node is: ", root)
        objects = client.get_objects_node()
        print("Objects node is: ", objects)

        # Node objects have methods to read and write node attributes as well as browse or populate address space
        print("Children of root are: ", root.get_children())

        # get a specific node knowing its node id
        # var = client.get_node(ua.NodeId(1002, 2))
        # var = client.get_node("ns=3;i=2002")
        # print(var)
        # var.get_data_value() # get value of node as a DataValue object
        # var.get_value() # get value of node as a python builtin
        # var.set_value(ua.Variant([23], ua.VariantType.Int64)) #set node value using explicit data type
        # var.set_value(3.9) # set node value using implicit data type

        # gettting our namespace idx
        uri = "http://examples.freeopcua.github.io"
        idx = client.get_namespace_index(uri)

        # Now getting a variable node using its browse path
        sin_var = root.get_child(["0:Objects", "{}:MyObject".format(idx), "{}:MySin".format(idx)])
        print("sin_var is: ", sin_var)

        cos_var = root.get_child(["0:Objects", "{}:MyObject".format(idx), "{}:MyCos".format(idx)])
        print("cos_var is: ", cos_var)

        # subscribing to a variable node
        updater = ValueUpdater()
        ani = animation.FuncAnimation(fig, animate, interval=interval)
        plt.show()
        # embed()

    finally:
        client.disconnect()
        print('Client finally')
