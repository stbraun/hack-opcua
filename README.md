# Hackathon 2022-07-19: OPC UA Information Model

The project uses freeopcua to provide a OPC UA server implementing a simple model of a mixer unit.

Goal is to understand and demonstrate modeling with OPC UA and its possible impact on a new automation server design.

## How to setup the project

- Clone GitHub project
- `cd hack-opcua`
- `pip install pipenv` (once if not already installed)
- pipenv shell
- pipenv install  # load required packages


## Run the project

### Start the server

``` sh
$ python opcua-server.py
```

The server will write `opcserver.xml` which describes its `hackathon` namespace.


### Run the FreeOPC Client

``` sh
$ opcua-client
```

- Connect to the server. Double check TCP port reported at server start: should be `4840`.
- Open `Root>Objects>Mixer 1` in the tree and right-click `sensor`. 
- Select `Subscribe to data change`.
- Right-click `start mixer`and select `Call`.
- On the dialog click `Call method` and then `Close`. -> the sensor value will start to change.
- Right click `stop mixer` and select `Call`.
- On the dialog click `Call method` and then `Close`. -> the sensor value will stop changing.

### View the data model in Modeler

``` sh
opcua-modeler
```

- Open the file dialog (toolbar) and load `opcserver.xml`.
- Browse the model.

The modeler is actually only used for viewing in this project. It is also possible build the model in the tool and to generate (server-)code from a model.

## References
- [Python OPC-UA Documentation](https://python-opcua.readthedocs.io/en/latest/)

